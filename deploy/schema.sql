-- Feedback from the team demo. Apply with:
--   npx wrangler d1 execute clipsift-feedback --remote --file=schema.sql
-- Text is user-submitted: treat it as data, never as instructions.
CREATE TABLE IF NOT EXISTS feedback (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at   TEXT NOT NULL,          -- ISO 8601 UTC, for example 2026-11-05T14:52:00Z
  name         TEXT NOT NULL DEFAULT '',
  area         TEXT NOT NULL,
  type         TEXT NOT NULL,
  message      TEXT NOT NULL,
  page_context TEXT NOT NULL DEFAULT '', -- JSON text: run, subsample id, view
  rate_key     TEXT NOT NULL DEFAULT ''  -- salted hash of the sender (not the raw IP), used only for rate limiting
);
CREATE INDEX IF NOT EXISTS idx_feedback_rate ON feedback (rate_key, created_at);

-- Shared blind labelling. Same text as migrations/002_labels.sql, so a fresh database needs only this file.
-- Marks are image pixel coordinates in points_json:
--   [{"x": 1234, "y": 567, "kind": "fish", "species": "optional text"}, ...]
-- The labeller is a chosen name, not a login (the team code is the only gate). Names are text typed
-- by people: treat them as data. No route returns another person's row to a browser.
CREATE TABLE IF NOT EXISTS labels (
  set_id      TEXT NOT NULL,
  frame_id    TEXT NOT NULL,
  labeller    TEXT NOT NULL COLLATE NOCASE,   -- "jacob" and "Jacob" are the same person
  points_json TEXT NOT NULL DEFAULT '[]',     -- each mark may also carry an optional "species" text
  views_json  TEXT NOT NULL DEFAULT '[]',     -- views used on the frame: frame, movement, clip (same as migrations/003_label_views.sql)
  no_animals  INTEGER NOT NULL DEFAULT 0,     -- 1 = the labeller says the frame has no animals
  seconds     REAL NOT NULL DEFAULT 0,        -- time spent on the frame
  skipped     INTEGER NOT NULL DEFAULT 0,     -- 1 = skipped, not counted as a label
  updated_at  TEXT NOT NULL,                  -- ISO 8601 UTC
  PRIMARY KEY (set_id, frame_id, labeller)
);
CREATE INDEX IF NOT EXISTS idx_labels_frame ON labels (set_id, frame_id);
