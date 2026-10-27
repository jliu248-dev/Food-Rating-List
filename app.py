import os
import sqlite3
from functools import wraps

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")
app.config["DATABASE"] = os.path.join(app.root_path, "food.db")

MAX_REVIEW_LENGTH = 500
MAX_ITEM_NAME_LENGTH = 80
AREAS = {"on": "On campus", "off": "Off campus"}

# Places and dishes are rated the same way; each has its own ratings table.
RATING_TABLES = {
    "place": ("ratings", "place_id"),
    "item": ("item_ratings", "item_id"),
}


# ---------- Database helpers ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    # Databases created before places had an area column need it added.
    columns = {row["name"] for row in db.execute("PRAGMA table_info(places)")}
    if "area" not in columns:
        db.execute("ALTER TABLE places ADD COLUMN area TEXT")
    with app.open_resource("seed.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    db.commit()


@app.cli.command("init-db")
def init_db_command():
    """Create missing tables and add/update the places. Keeps users and ratings."""
    init_db()
    click.echo("Database ready.")


@app.cli.command("reset-db")
@click.confirmation_option(prompt="This deletes ALL users, dishes and ratings. Continue?")
def reset_db_command():
    """Delete everything and start over with an empty database."""
    db = get_db()
    for table in ("item_ratings", "items", "ratings", "places", "users"):
        db.execute(f"DROP TABLE IF EXISTS {table}")
    init_db()
    click.echo("Database reset.")


# ---------- Login helpers ----------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = get_db().execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()


# A global (not a context processor) so imported macros in _macros.html can see it.
app.jinja_env.globals["AREAS"] = AREAS


# ---------- Rating helpers (shared by places and dishes) ----------

def rating_summary(kind, target_id):
    """Average, count, and how many of each score (1-5) a place or dish got."""
    table, column = RATING_TABLES[kind]
    dist = {score: 0 for score in range(1, 6)}
    for row in get_db().execute(
        f"SELECT score, COUNT(*) AS n FROM {table} WHERE {column} = ? GROUP BY score",
        (target_id,),
    ):
        dist[row["score"]] = row["n"]
    count = sum(dist.values())
    avg = sum(score * n for score, n in dist.items()) / count if count else None
    return {"avg": avg, "count": count, "dist": dist}


def rating_reviews(kind, target_id):
    table, column = RATING_TABLES[kind]
    return get_db().execute(
        f"""
        SELECT r.score, r.review, u.username,
               date(r.created_at, 'localtime') AS created_on,
               date(r.updated_at, 'localtime') AS updated_on
        FROM {table} r JOIN users u ON u.id = r.user_id
        WHERE r.{column} = ?
        ORDER BY COALESCE(r.updated_at, r.created_at) DESC
        """,
        (target_id,),
    ).fetchall()


def my_rating(kind, target_id):
    if g.user is None:
        return None
    table, column = RATING_TABLES[kind]
    return get_db().execute(
        f"SELECT score, review FROM {table} WHERE user_id = ? AND {column} = ?",
        (g.user["id"], target_id),
    ).fetchone()


def handle_rate(kind, target_id, heading, subheading, back_url):
    """Show the rating form, or save it. Creates the rating or updates the user's existing one."""
    existing = my_rating(kind, target_id)

    if request.method == "POST":
        review = request.form.get("review", "").strip()
        error = None
        try:
            score = int(request.form.get("score", ""))
        except ValueError:
            score = None
        if score not in range(1, 6):
            error = "Please choose a rating from 1 to 5 stars."
        elif len(review) > MAX_REVIEW_LENGTH:
            error = f"Reviews can be at most {MAX_REVIEW_LENGTH} characters."

        if error is None:
            table, column = RATING_TABLES[kind]
            db = get_db()
            db.execute(
                f"""
                INSERT INTO {table} (user_id, {column}, score, review)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (user_id, {column}) DO UPDATE SET
                    score = excluded.score,
                    review = excluded.review,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (g.user["id"], target_id, score, review),
            )
            db.commit()
            flash("Your rating was saved.")
            return redirect(back_url)
        flash(error)
        existing = {"score": score, "review": review}

    return render_template(
        "rate.html",
        heading=heading,
        subheading=subheading,
        back_url=back_url,
        existing=existing,
        is_edit=my_rating(kind, target_id) is not None,
        max_len=MAX_REVIEW_LENGTH,
    )


def get_place_or_404(place_id):
    place = get_db().execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
    if place is None:
        abort(404)
    return place


def get_item_or_404(item_id):
    item = get_db().execute(
        """
        SELECT i.*, p.name AS place_name, p.area AS place_area
        FROM items i JOIN places p ON p.id = i.place_id
        WHERE i.id = ?
        """,
        (item_id,),
    ).fetchone()
    if item is None:
        abort(404)
    return item


# ---------- Pages ----------

@app.route("/")
def index():
    area = request.args.get("area")
    if area not in AREAS:
        area = None
    db = get_db()
    places = db.execute(
        """
        SELECT p.id, p.name, p.area, p.location,
               AVG(r.score) AS avg_score,
               COUNT(r.id) AS num_ratings,
               (SELECT COUNT(*) FROM items i WHERE i.place_id = p.id) AS num_items
        FROM places p
        LEFT JOIN ratings r ON r.place_id = p.id
        WHERE ? IS NULL OR p.area = ?
        GROUP BY p.id
        ORDER BY avg_score IS NULL, avg_score DESC, num_ratings DESC, p.name
        """,
        (area, area),
    ).fetchall()
    top_items = db.execute(
        """
        SELECT i.id, i.name, p.name AS place_name,
               AVG(ir.score) AS avg_score, COUNT(*) AS num_ratings
        FROM items i
        JOIN item_ratings ir ON ir.item_id = i.id
        JOIN places p ON p.id = i.place_id
        WHERE ? IS NULL OR p.area = ?
        GROUP BY i.id
        ORDER BY avg_score DESC, num_ratings DESC, i.name
        LIMIT 5
        """,
        (area, area),
    ).fetchall()
    return render_template("index.html", places=places, top_items=top_items, area=area)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        error = None
        if not username:
            error = "Username is required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."

        if error is None:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = f"Username '{username}' is already taken."
            else:
                session.clear()
                session["user_id"] = cur.lastrowid
                flash("Welcome! Your account was created.")
                return redirect(url_for("index"))
        flash(error)
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.")
        else:
            session.clear()
            session["user_id"] = user["id"]
            next_url = request.args.get("next", "")
            # Only follow local paths so the redirect can't point to another site.
            if not next_url.startswith("/") or next_url.startswith("//"):
                next_url = url_for("index")
            return redirect(next_url)
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("index"))


@app.route("/places/<int:place_id>")
def place(place_id):
    place = get_place_or_404(place_id)
    items = get_db().execute(
        """
        SELECT i.id, i.name, AVG(ir.score) AS avg_score, COUNT(ir.id) AS num_ratings
        FROM items i
        LEFT JOIN item_ratings ir ON ir.item_id = i.id
        WHERE i.place_id = ?
        GROUP BY i.id
        ORDER BY avg_score IS NULL, avg_score DESC, num_ratings DESC, i.name
        """,
        (place_id,),
    ).fetchall()
    return render_template(
        "place.html",
        place=place,
        summary=rating_summary("place", place_id),
        reviews=rating_reviews("place", place_id),
        my_rating=my_rating("place", place_id),
        items=items,
        max_item_len=MAX_ITEM_NAME_LENGTH,
    )


@app.route("/places/<int:place_id>/rate", methods=["GET", "POST"])
@login_required
def rate_place(place_id):
    place = get_place_or_404(place_id)
    return handle_rate(
        "place", place_id,
        heading=place["name"],
        subheading="How was this place overall?",
        back_url=url_for("place", place_id=place_id),
    )


@app.route("/places/<int:place_id>/items", methods=["POST"])
@login_required
def add_item(place_id):
    get_place_or_404(place_id)
    name = " ".join(request.form.get("name", "").split())
    if not name or len(name) > MAX_ITEM_NAME_LENGTH:
        flash(f"Dish names must be 1 to {MAX_ITEM_NAME_LENGTH} characters.")
        return redirect(url_for("place", place_id=place_id))

    db = get_db()
    existing = db.execute(
        "SELECT id FROM items WHERE place_id = ? AND name = ? COLLATE NOCASE",
        (place_id, name),
    ).fetchone()
    if existing:
        flash(f"'{name}' is already listed here. Rate it below.")
        return redirect(url_for("item", item_id=existing["id"]))

    cur = db.execute(
        "INSERT INTO items (place_id, name, added_by) VALUES (?, ?, ?)",
        (place_id, name, g.user["id"]),
    )
    db.commit()
    flash(f"Added '{name}'. Now give it a rating!")
    return redirect(url_for("rate_item", item_id=cur.lastrowid))


@app.route("/items/<int:item_id>")
def item(item_id):
    item = get_item_or_404(item_id)
    return render_template(
        "item.html",
        item=item,
        summary=rating_summary("item", item_id),
        reviews=rating_reviews("item", item_id),
        my_rating=my_rating("item", item_id),
    )


@app.route("/items/<int:item_id>/rate", methods=["GET", "POST"])
@login_required
def rate_item(item_id):
    item = get_item_or_404(item_id)
    return handle_rate(
        "item", item_id,
        heading=item["name"],
        subheading=f"at {item['place_name']}. How was this dish?",
        back_url=url_for("item", item_id=item_id),
    )


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, port=5001)
