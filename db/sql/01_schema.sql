-- ============================================================
-- Panchangam API — PostgreSQL schema (Neon)
-- Generated from the SQLModel table definitions in db/models/.
-- Apply this first, then 02_seed.sql.
-- ============================================================

CREATE TABLE dataset_etag (
	key VARCHAR NOT NULL, 
	etag VARCHAR NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
);

CREATE TABLE location (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	label VARCHAR NOT NULL, 
	latitude FLOAT NOT NULL, 
	longitude FLOAT NOT NULL, 
	timezone VARCHAR NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_location_name ON location (name);

CREATE TABLE malayalam_masa (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	ml VARCHAR NOT NULL, 
	en VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE nakshatra (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	ml VARCHAR NOT NULL, 
	en VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE paksha (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	ml VARCHAR NOT NULL, 
	en VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE thithi (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	paksha_id INTEGER NOT NULL, 
	day INTEGER NOT NULL, 
	ml VARCHAR NOT NULL, 
	en VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	FOREIGN KEY(paksha_id) REFERENCES paksha (id)
);

CREATE TABLE panchangam (
	date DATE NOT NULL, 
	thithi_id INTEGER NOT NULL, 
	nakshatra_id INTEGER NOT NULL, 
	nazhika_from_sunrise FLOAT NOT NULL, 
	PRIMARY KEY (date), 
	FOREIGN KEY(thithi_id) REFERENCES thithi (id), 
	FOREIGN KEY(nakshatra_id) REFERENCES nakshatra (id)
);

CREATE TABLE santhigiri_event (
	id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	description VARCHAR NOT NULL, 
	sort_order INTEGER NOT NULL, 
	nakshatra_id INTEGER, 
	thithi_id INTEGER, 
	ml_day INTEGER, 
	ml_month INTEGER, 
	ml_year INTEGER, 
	en_day INTEGER, 
	en_month INTEGER, 
	en_year INTEGER, 
	occurance INTEGER, 
	is_poornima BOOLEAN, 
	last_occurance BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(nakshatra_id) REFERENCES nakshatra (id), 
	FOREIGN KEY(thithi_id) REFERENCES thithi (id)
);

CREATE INDEX ix_santhigiri_event_sort_order ON santhigiri_event (sort_order);

CREATE TABLE kollavarsham_date (
	date DATE NOT NULL, 
	kv_day INTEGER NOT NULL, 
	kv_month INTEGER NOT NULL, 
	kv_year INTEGER NOT NULL, 
	PRIMARY KEY (date), 
	FOREIGN KEY(date) REFERENCES panchangam (date) ON DELETE CASCADE, 
	FOREIGN KEY(kv_month) REFERENCES malayalam_masa (id)
);

CREATE TABLE nakshatra_transitions (
	id SERIAL NOT NULL, 
	panchangam_date DATE NOT NULL, 
	nakshatra_id INTEGER NOT NULL, 
	start_time TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	end_time TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(panchangam_date) REFERENCES panchangam (date) ON DELETE CASCADE, 
	FOREIGN KEY(nakshatra_id) REFERENCES nakshatra (id)
);

CREATE INDEX idx_nakshatra_transitions_date ON nakshatra_transitions (panchangam_date, start_time);

CREATE TABLE santhigiri_event_dates (
	id SERIAL NOT NULL, 
	panchangam_date DATE NOT NULL, 
	event_id VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(panchangam_date) REFERENCES panchangam (date) ON DELETE CASCADE, 
	FOREIGN KEY(event_id) REFERENCES santhigiri_event (id) ON DELETE CASCADE
);

CREATE INDEX idx_santhigiri_event_dates_date ON santhigiri_event_dates (panchangam_date);
CREATE INDEX ix_santhigiri_event_dates_event_id ON santhigiri_event_dates (event_id);

CREATE TABLE sunrise_sunset (
	id SERIAL NOT NULL, 
	date DATE NOT NULL, 
	location_id INTEGER NOT NULL, 
	sunrise TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	sunset TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_sunrise_sunset_date_loc UNIQUE (date, location_id), 
	FOREIGN KEY(date) REFERENCES panchangam (date) ON DELETE CASCADE, 
	FOREIGN KEY(location_id) REFERENCES location (id)
);

CREATE INDEX idx_sunrise_sunset_date ON sunrise_sunset (date);

CREATE TABLE thithi_transitions (
	id SERIAL NOT NULL, 
	panchangam_date DATE NOT NULL, 
	thithi_id INTEGER NOT NULL, 
	start_time TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	end_time TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(panchangam_date) REFERENCES panchangam (date) ON DELETE CASCADE, 
	FOREIGN KEY(thithi_id) REFERENCES thithi (id)
);

CREATE INDEX idx_thithi_transitions_date ON thithi_transitions (panchangam_date, start_time);

