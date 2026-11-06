-- Shared blind labelling (label.html). Additive: safe to run more than once. Apply with:
--   npx wrangler d1 execute clipsift-feedback --remote --file=migrations/002_labels.sql
-- One row per labeller per frame. Marks are image pixel coordinates in points_json:
--   [{"x": 1234, "y": 567, "kind": "fish"}, ...]
-- The labeller is a chosen name, not a login (the team code is the only gate). Names are text typed
-- by people: treat them as data. No route returns another person's row to a browser.
CREATE TABLE IF NOT EXISTS labels (
  set_id      TEXT NOT NULL,
  frame_id    TEXT NOT NULL,
  labeller    TEXT NOT NULL COLLATE NOCASE,   -- "jacob" and "Jacob" are the same person
  points_json TEXT NOT NULL DEFAULT '[]',
  no_animals  INTEGER NOT NULL DEFAULT 0,     -- 1 = the labeller says the frame has no animals
  seconds     REAL NOT NULL DEFAULT 0,        -- time spent on the frame
  skipped     INTEGER NOT NULL DEFAULT 0,     -- 1 = skipped, not counted as a label
  updated_at  TEXT NOT NULL,                  -- ISO 8601 UTC
  PRIMARY KEY (set_id, frame_id, labeller)
);
CREATE INDEX IF NOT EXISTS idx_labels_frame ON labels (set_id, frame_id);
