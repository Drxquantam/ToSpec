-- Runs automatically on first Postgres container start
-- (mounted into /docker-entrypoint-initdb.d/ by docker-compose.yml)

CREATE TABLE IF NOT EXISTS presets (
    id          TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    label       TEXT NOT NULL,
    width_px    INTEGER NOT NULL CHECK (width_px > 0),
    height_px   INTEGER NOT NULL CHECK (height_px > 0),
    dpi         INTEGER NOT NULL CHECK (dpi > 0),
    cm_width    NUMERIC(6,2) NOT NULL,
    cm_height   NUMERIC(6,2) NOT NULL,
    min_kb      INTEGER NOT NULL CHECK (min_kb > 0),
    max_kb      INTEGER NOT NULL CHECK (max_kb >= min_kb),
    note        TEXT,
    source      TEXT
);

-- Seed data sourced from the official ibps.in / ssc.nic.in / upsconline.nic.in
-- notifications referenced in the client-side tool. Do not alter these numbers
-- without checking the source notification.
INSERT INTO presets (id, category, label, width_px, height_px, dpi, cm_width, cm_height, min_kb, max_kb, note, source) VALUES
('ibps_photo', 'IBPS / Bank', 'Photo', 430, 400, 200, 3.5, 4.5, 20, 50,
    'Pixel size is mandated directly by IBPS.',
    'ibps.in recruitment notification (Guidelines for scanning & upload of documents)'),
('ibps_sign', 'IBPS / Bank', 'Signature', 140, 60, 200, 4.0, 2.0, 10, 20,
    'Not in capital letters — cursive/running handwriting only.',
    'ibps.in recruitment notification'),
('ibps_thumb', 'IBPS / Bank', 'Left thumb impression', 240, 240, 200, 3.0, 3.0, 20, 50,
    'Left thumb, black or blue ink on plain white paper.',
    'ibps.in recruitment notification'),
('ibps_decl', 'IBPS / Bank', 'Handwritten declaration', 800, 400, 200, 10.0, 5.0, 50, 100,
    'Handwritten declaration text, English only, not in capitals.',
    'ibps.in recruitment notification'),
('ssc_photo', 'SSC', 'Photo', 413, 531, 300, 3.5, 4.5, 20, 50,
    'SSC''s notification fixes only the 3.5x4.5cm size and 20-50KB — exact pixel count isn''t mandated, so any DPI works. 300 DPI is used here as a sensible default.',
    'ssc.nic.in official notification PDF'),
('ssc_sign', 'SSC', 'Signature', 472, 236, 300, 4.0, 2.0, 10, 20,
    'cm size varies by which SSC exam: most notifications say 4x2cm, some say 4x3cm or 6x2cm. Check your specific notification before finalizing.',
    'ssc.nic.in official notification PDF'),
('upsc_photo', 'UPSC', 'Photo', 350, 450, 300, 2.96, 3.81, 20, 200,
    'UPSC''s official instructions specify no pixel or cm size at all — only 20-200KB, JPG, and that the face must fill 75% of the frame. Pixel size shown here is just a reasonable starting point.',
    'upsconline.nic.in — Instructions for uploading the Photo & Signature (PDF)'),
('upsc_sign', 'UPSC', 'Triple signature', 450, 400, 300, 3.81, 3.39, 20, 100,
    'This is the scan containing all three stacked signatures, not a single signature. Official spec: both width and height between 350-500px, 20-100KB.',
    'upsconline.nic.in — Instructions for uploading the Photo & Signature (PDF)')
ON CONFLICT (id) DO NOTHING;
