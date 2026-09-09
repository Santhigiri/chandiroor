-- Adds the "generation_job" table backing background data-generation runs
-- (POST /api/v1/panchangam/generate, /panchangam/events/{id}/occurrences,
-- /panchangam/events/generate) — see db/models/generation_job.py and
-- CLAUDE.md's "Background generation jobs" section.
--
-- This is a brand-new table, so `init_db()`'s `SQLModel.metadata.create_all()`
-- (db/database.py) already creates it automatically on any already-deployed
-- database the next time the app starts — this migration only exists for
-- someone who wants the table present immediately, without waiting for a
-- restart, or who is scripting a deploy that applies SQL before the app runs.
-- Safe to run any time; `CREATE TABLE IF NOT EXISTS` makes it a no-op if the
-- table already exists.

CREATE TABLE IF NOT EXISTS generation_job (
	id VARCHAR NOT NULL,
	job_type VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	lock_key INTEGER,
	params JSON NOT NULL,
	progress JSON,
	result JSON,
	error VARCHAR,
	started_by VARCHAR,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_generation_job_lock_key UNIQUE (lock_key)
);

CREATE INDEX IF NOT EXISTS ix_generation_job_job_type ON generation_job (job_type);
CREATE INDEX IF NOT EXISTS ix_generation_job_status ON generation_job (status);
