-- Which views a labeller used on a frame (frame, movement, clip), kept for later analysis. Additive. Apply once with:
--   npx wrangler d1 execute clipsift-feedback --remote --file=migrations/003_label_views.sql
-- Apply it BEFORE deploying the new Worker, which writes this column. SQLite has no "ADD COLUMN IF NOT EXISTS",
-- so running it a second time fails with "duplicate column name": that error is harmless.
ALTER TABLE labels ADD COLUMN views_json TEXT NOT NULL DEFAULT '[]';
