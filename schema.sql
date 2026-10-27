-- Safe to run again: only creates tables that don't exist yet.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS places (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    area        TEXT CHECK (area IN ('on', 'off')),  -- on or off campus
    location    TEXT,
    description TEXT
);

-- One rating + review per user per place.
CREATE TABLE IF NOT EXISTS ratings (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    place_id   INTEGER NOT NULL REFERENCES places(id),
    score      INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    review     TEXT CHECK (length(review) <= 500),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (user_id, place_id)
);

-- Dishes inside a place, added by logged-in users.
CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY,
    place_id   INTEGER NOT NULL REFERENCES places(id),
    name       TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
    added_by   INTEGER REFERENCES users(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (place_id, name COLLATE NOCASE)
);

-- One rating + review per user per dish.
CREATE TABLE IF NOT EXISTS item_ratings (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    item_id    INTEGER NOT NULL REFERENCES items(id),
    score      INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    review     TEXT CHECK (length(review) <= 500),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (user_id, item_id)
);
