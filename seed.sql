-- Food spots on and around the Santa Clara University campus.
-- Safe to run again: existing places are updated, not duplicated.
INSERT INTO places (name, area, location, description) VALUES
    ('The Marketplace', 'on', 'Benson Center', 'Main campus dining commons.'),
    ('Mission Bakery', 'on', 'Benson Center', 'Bakery and coffee.'),
    ('The Bronco', 'on', 'Benson Center', 'Campus pub and late-night food.'),
    ('Sunstream Cafe', 'on', 'Learning Commons', 'Coffee and snacks in the library.'),
    ('Thai Pepper', 'off', 'Franklin Square', 'Thai curries and noodles.'),
    ('Mio Vicino', 'off', 'Franklin Square', 'Italian.'),
    ('Asadero', 'off', '2323 The Alameda', 'Mexican.'),
    ('Sara''s Kitchen', 'off', '1595 Franklin St', 'Brunch diner with a patio.'),
    ('Mission City Coffee Roasting Co.', 'off', 'The Alameda', 'Local coffee roaster.')
ON CONFLICT (name) DO UPDATE SET
    area = excluded.area,
    location = excluded.location,
    description = excluded.description;
