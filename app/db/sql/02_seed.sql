-- ============================================================
-- Panchangam API — seed data (PostgreSQL / Neon)
-- Apply 01_schema.sql first. Insertion order respects FKs.
-- dataset_etag is intentionally left empty (derived/recomputed).
-- ============================================================

BEGIN;

-- ---------- Lookup tables ----------

INSERT INTO paksha (id, name, ml, en) VALUES
  (1, 'SHUKLA', 'ശുക്ലപക്ഷം', 'Shukla Paksha'),
  (2, 'KRISHNA', 'കൃഷ്ണപക്ഷം', 'Krishna Paksha');

INSERT INTO nakshatra (id, name, ml, en) VALUES
  (1, 'ASWATHI', 'അശ്വതി', 'Ashwati'),
  (2, 'BHARANI', 'ഭരണി', 'Bharani'),
  (3, 'KARTHIKA', 'കാർത്തിക', 'Karthika'),
  (4, 'ROHINI', 'രോഹിണി', 'Rohini'),
  (5, 'MAKAYIRAM', 'മകയിരം', 'Makayiram'),
  (6, 'THIRUVATHIRA', 'തിരുവാതിര', 'Thiruvathira'),
  (7, 'PUNARTHAM', 'പുണർതം', 'Punartham'),
  (8, 'POOYAM', 'പൂയം', 'Pooyam'),
  (9, 'AAYILYAM', 'ആയില്യം', 'Aayilyam'),
  (10, 'MAKAM', 'മകം', 'Makam'),
  (11, 'POORAM', 'പൂരം', 'Pooram'),
  (12, 'UTHRAM', 'ഉത്രം', 'Uthram'),
  (13, 'ATHAM', 'അത്തം', 'Atham'),
  (14, 'CHITHIRA', 'ചിത്തിര', 'Chithira'),
  (15, 'CHOTHI', 'ചോതി', 'Chothi'),
  (16, 'VISHAKHAM', 'വിശാഖം', 'Vishakham'),
  (17, 'ANIZHAM', 'അനിഴം', 'Anizham'),
  (18, 'THRIKKETTA', 'തൃക്കേട്ട', 'Thrikketta'),
  (19, 'MOOLAM', 'മൂലം', 'Moolam'),
  (20, 'POORADAM', 'പൂരാടം', 'Pooradam'),
  (21, 'UTHRADAM', 'ഉത്രാടം', 'Uthradam'),
  (22, 'THIRUVONAM', 'തിരുവോണം', 'Thiruvonam'),
  (23, 'AVITTAM', 'അവിട്ടം', 'Avittam'),
  (24, 'CHATAYAM', 'ചതയം', 'Chatayam'),
  (25, 'POORURUTTATHI', 'പൂരുരുട്ടാതി', 'Pooruruttathi'),
  (26, 'UTHRATTATHI', 'ഉത്രട്ടാതി', 'Uthrattathi'),
  (27, 'REVATHI', 'രേവതി', 'Revathi');

INSERT INTO thithi (id, name, paksha_id, day, ml, en) VALUES
  (1, 'PRATHAMA_SHUKLA', 1, 1, 'പ്രതിപദ', 'Prathama'),
  (2, 'DWITHIYA_SHUKLA', 1, 2, 'ദ്വിതീയ', 'Dwitiya'),
  (3, 'TRITHIYA_SHUKLA', 1, 3, 'തൃതീയ', 'Tritiya'),
  (4, 'CHATURTHI_SHUKLA', 1, 4, 'ചതുർത്ഥി', 'Chaturthi'),
  (5, 'PANCHAMI_SHUKLA', 1, 5, 'പഞ്ചമി', 'Panchami'),
  (6, 'SHASHTHI_SHUKLA', 1, 6, 'ഷഷ്ഠി', 'Shashthi'),
  (7, 'SAPTAMI_SHUKLA', 1, 7, 'സപ്തമി', 'Saptami'),
  (8, 'ASHTAMI_SHUKLA', 1, 8, 'അഷ്ടമി', 'Ashtami'),
  (9, 'NAVAMI_SHUKLA', 1, 9, 'നവമി', 'Navami'),
  (10, 'DASHAMI_SHUKLA', 1, 10, 'ദശമി', 'Dashami'),
  (11, 'EKADASHI_SHUKLA', 1, 11, 'ഏകാദശി', 'Ekadashi'),
  (12, 'DWADASHI_SHUKLA', 1, 12, 'ദ്വാദശി', 'Dwadashi'),
  (13, 'TRAYODASHI_SHUKLA', 1, 13, 'ത്രയോദശി', 'Trayodashi'),
  (14, 'CHATURDASHI_SHUKLA', 1, 14, 'ചതുര്ദശി', 'Chaturdashi'),
  (15, 'POORNIMA', 1, 15, 'പൗർണമി', 'Purnima'),
  (16, 'PRATHAMA_KRISHNA', 2, 1, 'പ്രതിപദ', 'Prathama'),
  (17, 'DWITHIYA_KRISHNA', 2, 2, 'ദ്വിതീയ', 'Dwitiya'),
  (18, 'TRITHIYA_KRISHNA', 2, 3, 'തൃതീയ', 'Tritiya'),
  (19, 'CHATURTHI_KRISHNA', 2, 4, 'ചതുർത്ഥി', 'Chaturthi'),
  (20, 'PANCHAMI_KRISHNA', 2, 5, 'പഞ്ചമി', 'Panchami'),
  (21, 'SHASHTHI_KRISHNA', 2, 6, 'ഷഷ്ഠി', 'Shashthi'),
  (22, 'SAPTAMI_KRISHNA', 2, 7, 'സപ്തമി', 'Saptami'),
  (23, 'ASHTAMI_KRISHNA', 2, 8, 'അഷ്ടമി', 'Ashtami'),
  (24, 'NAVAMI_KRISHNA', 2, 9, 'നവമി', 'Navami'),
  (25, 'DASHAMI_KRISHNA', 2, 10, 'ദശമി', 'Dashami'),
  (26, 'EKADASHI_KRISHNA', 2, 11, 'ഏകാദശി', 'Ekadashi'),
  (27, 'DWADASHI_KRISHNA', 2, 12, 'ദ്വാദശി', 'Dwadashi'),
  (28, 'TRAYODASHI_KRISHNA', 2, 13, 'ത്രയോദശി', 'Trayodashi'),
  (29, 'CHATURDASHI_KRISHNA', 2, 14, 'ചതുര്ദശി', 'Chaturdashi'),
  (30, 'AMAVASYA', 2, 15, 'അമാവാസി', 'Amavasya');

INSERT INTO malayalam_masa (id, name, ml, en) VALUES
  (1, 'MEDAM', 'മേടം', 'Medam'),
  (2, 'IDAVAM', 'ഇടവം', 'Edavam'),
  (3, 'MITHUNAM', 'മിഥുനം', 'Mithunam'),
  (4, 'KARKIDAKAM', 'കർക്കിടകം', 'Karkidakam'),
  (5, 'CHINGAM', 'ചിങ്ങം', 'Chingam'),
  (6, 'KANNI', 'കന്നി', 'Kanni'),
  (7, 'THULAM', 'തുലാം', 'Thulam'),
  (8, 'VRISCHIKAM', 'വൃശ്ചികം', 'Vrischikam'),
  (9, 'DHANU', 'ധനു', 'Dhanu'),
  (10, 'MAKARAM', 'മകരം', 'Makaram'),
  (11, 'KUMBHAM', 'കുംഭം', 'Kumbham'),
  (12, 'MEENAM', 'മീനം', 'Meenam');

INSERT INTO location (id, name, label, latitude, longitude, timezone) VALUES
  (1, 'tvm', 'Trivandrum, Kerala, India', 8.645, 76.938, 'Asia/Kolkata');

SELECT setval(pg_get_serial_sequence('location', 'id'), (SELECT MAX(id) FROM location));

INSERT INTO santhigiri_event (id, name, description, sort_order, nakshatra_id, thithi_id, ml_day, ml_month, ml_year, en_day, en_month, en_year, occurance, is_poornima, last_occurance, day_offset) VALUES
  ('POURNAMI', 'Pournami', '
    The full moon day (Pournami) is observed as a day of fasting and prayers at the Ashram. This day is considered very auspicious for spiritual and material wellbeing. It is also an apt time to pray for one’s ancestral lineage (pithrus) and a change in our capability and propensity for action (‘karmagati’). Devotees in large numbers pray through the day and night at the Ashram on ‘Pournami’, with Deepa and Kumbha Pradakshina. Pournami prayers are held at the Ashram Branches also.
    ', 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, TRUE, NULL, NULL),
  ('NAVOLI_JYOTHIR_DINAM', 'Navoli Jyothir Dinam', '
This is the day on which Guru left His physical body and merged in the ‘Adisankalpam’ (The Plane of Primordial Consciousness), on May 6th, 1999. The Guru’s ‘Prakasham’ (Light) is now present in the world as ‘Nava Oli’ (A New Light). The day is observed as ‘Navaolijyothirdinam – Sarvamangala Sudinam’ (the Day of the New Light, Auspicious for All). Devotees observe ‘vratam’ (austerities) for 72 days prior to ‘Navaolijyothirdinam’, commemorating the 72 years that Guru lived, enduring great sacrifices and hardships. A Deepa Pradakshina is held in the evening, followed by a special ‘pushpanjali’ (floral offering) by the sanyasi sangh. A spectacular fireworks and percussion display is held after the 9 p.m. prayers to mark the time of the Guru’s physical departure.
        ', 1, NULL, NULL, NULL, NULL, NULL, 6, 5, NULL, NULL, NULL, NULL, NULL),
  ('JANMAGRIHA_THEERTHA_YATHRA', 'Janmagriha Theertha Yaathra', 'Janmagriha Theertha Yaathra', 2, 15, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
  ('POOJITHA_PEEDA_SAMARPANAM', 'Poojitha Peeda Samarppanam Varshikam', 'Poojitha Peeda Samarppanam Varshikam Ardhavarshika kumba mela', 3, NULL, NULL, NULL, NULL, NULL, 22, 2, NULL, NULL, NULL, NULL, NULL),
  ('POOJITHA_PEEDA_VRITHARAMBAM', 'Poojitha Peeda Vritharambam', 'Poojitha Peeda Vritharambam', 4, NULL, NULL, NULL, NULL, NULL, 13, 1, NULL, NULL, NULL, NULL, NULL),
  ('PRATHISTA_VARSHIKAM', 'Prathista Varshikam', 'Prathista Varshikam', 5, NULL, NULL, NULL, NULL, NULL, 10, 2, NULL, NULL, NULL, NULL, NULL),
  ('NAVOLI_JYOTHIR_DINAM_VRITHARAMBAM', 'Navoli Jyothir Dinam Vritharambam', 'Navoli Jyothir Dinam Vritharambam', 6, NULL, NULL, NULL, NULL, NULL, 24, 2, NULL, NULL, NULL, NULL, NULL),
  ('SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM', 'Sahakarana Mandiram Samarpana Varshikam', '
        On this day the ‘Sahakarana Mandiram’ (Shrine of Togetherness) was dedicated to Guru. The day falls on Kumbham 17 (February-March). It is marked by special prayers at the Ashram.
    ', 7, NULL, NULL, 17, 11, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
  ('PRATHISTA_POORTHIKARANA_VARSHIKAM', 'Prathista Poorthikarana Varshikam', 'Prathista Poorthikarana Varshikam', 8, NULL, NULL, 10, 1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
  ('DIVYA_POOJA_SAMARPANA_VARSHIKAM', 'Divya pooja samarpana varshikam', 'Divya pooja samarpana varshikam', 9, NULL, NULL, NULL, NULL, NULL, 7, 5, NULL, NULL, NULL, NULL, NULL),
  ('NAVAPOOJITHAM_VRITHARAMBAM', 'Navapoojitham vritharambam', 'Navapoojitham vritharambam', 10, NULL, NULL, NULL, 5, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
  ('NAVAPOOJITHAM', 'Navapoojitham', '
        Guru was born on September 1, 1927. The birthday celebrations are held as per the Malayalam Calendar, according to which Guru was born under the ‘Chothi’ star in the month of ‘Chingam’ (falling in August-September). The day is celebrated as ‘Navapoojitham - Janmadina Poojitha Samarpanam’. It is a day of special prayers, including Deepa Pradakshina (procession with lit lamps), at the Ashram.
    ', 11, 15, NULL, NULL, 5, NULL, NULL, NULL, NULL, NULL, NULL, TRUE, NULL),
  ('POORNA_KUMBAMELA', 'Poornakumba mela', '
The ‘Poorna Kumbhamela’ commemorates the day of the Guru’s spiritual attainment, falling on the 4th of the Malayalam month of ‘Kanni’ (September). The highlight of the celebrations is a colorful procession by devotees, carrying ceremonial parasols and decorated ‘kumbhams’ (earthen pots filled with holy water – theertham), around the Ashram. Taking the ‘kumbham’ for 12 successive times helps to remove the ‘karmadoshas’ (karmic errors) of the self and the family.
    ', 12, NULL, NULL, 4, 6, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
  ('SANYASADHEEKSHA_VARSHIKAM', 'Sanyasadheeksha varshikam', '
        Falling on the Vijayadashami day (mostly in October), this marks the anniversary of the day that Guru first conferred ‘sanyasam’ (vow of renunciation of householder life) on disciples in 1984. Every year on this day, devotees gather to pray for the wellbeing of ‘sanyasis’ (renunciates). This paves the way for greater mutual understanding and spiritual bonding between the renunciate and the householder.
    ', 13, NULL, 10, NULL, 7, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
  ('SAMSKARIKA_DINAM', 'Samskarika Dinam', '
        The formation of a National Centre for Cultural Renaissance (NCCR) on February 17, 1983, marked the beginning of an organized movement for cultural activities in the Ashram. The ‘Santhigiri Vishwa Samskarika Navodhana Kendram’ was registered as a charitable society on June 20, 1984. The organization is engaged in various cultural and voluntary activities to propagate the teachings of Guru for a spiritual and cultural renaissance in the world. The Santhigiri Vishwa Samskarika Navodhana Kendram has more than 200 units in Kerala and elsewhere. The Samskarika Dinam is marked by awareness meetings, seminars and cultural programmes to spread the Guru’s ideology.
    ', 14, NULL, NULL, NULL, NULL, NULL, 5, 11, NULL, NULL, NULL, NULL, NULL),
  ('SHISHYAPOOJITHA_BDAY', 'Shishyapoojitha''s Birthday', 'Shishyapoojitha''s Birthday', 15, 20, NULL, NULL, 7, NULL, NULL, NULL, NULL, NULL, NULL, TRUE, NULL);


-- ---------- App settings (defaults) ----------

INSERT INTO app_setting (key, value, updated_at) VALUES
  ('seed_year_range', '{"start_year": 2021, "end_year": 2030}', '2026-07-31 13:51:57.687176+00:00'),
  ('default_location_code', '{"code": "tvm"}', '2026-07-31 13:51:57.687176+00:00'),
  ('max_generate_span_days', '{"max_days": 366}', '2026-07-31 13:51:57.687176+00:00'),
  ('max_event_generate_year_span', '{"max_years": 15}', '2026-07-31 13:51:57.687176+00:00'),
  ('event_cutoffs', '{"nazhika_cutoff": 7.5, "transition_hour_cutoff": 3.0}', '2026-07-31 13:51:57.687176+00:00'),
  ('nakshatra_transition_step_days', '{"default": 0.01, "overrides": {}}', '2026-07-31 13:51:57.687176+00:00'),
  ('astronomy_epsilons', '{"nakshatra_epsilon": 1e-08, "kollavarsham_epsilon": 1e-06}', '2026-07-31 13:51:57.687176+00:00');



COMMIT;
