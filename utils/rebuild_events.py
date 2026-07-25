"""Rebuild the Santhigiri event occurrences from the Postgres base data.

This is the DB-sourced counterpart to running the individual ``cache_*`` scripts
against the pickle files. It loads the base PanchangamData (sunrise/sunset, thithi
and nakshatra transitions, Kollavarsham) from Postgres via ``DATABASE_URL``, derives
every Santhigiri event occurrence — Pournami included — on top of those values, and
writes the result back to the pickle cache.

The base astronomical values therefore come from the database (where they are already
populated) rather than being recomputed or read from the pickle. The output still
flows pickle -> ``scripts/gen_seed_sql.py`` -> ``db/sql/*.sql`` -> re-applied to
Postgres, so the seed-regeneration step remains the mechanism that persists the
recomputed occurrences.

Run offline (requires ``DATABASE_URL`` set and the DB seeded with base data):

    python -c "from utils.rebuild_events import rebuild_events_from_db; rebuild_events_from_db()"
"""
from utils.cache_common_events import update_common_events
from utils.cache_chothi_theerthayathra import update_chothi_theerthayathra
from utils.cache_crud import load_cache_from_db, write_cache
from utils.cache_navapoojitham import update_navapoojitham
from utils.cache_sishya_bday import update_sishya_bday


def rebuild_events_from_db() -> None:
    """Recompute all Santhigiri event occurrences from the DB base and write the cache."""
    # Load the base once, events cleared, so recomputed occurrences fully replace the
    # ones already seeded in the DB instead of stacking on top of them.
    cache = load_cache_from_db(clear_events=True)

    # Accumulate every event derivation onto the single DB-sourced cache. Pournami is
    # part of update_common_events, which reads the DB sunrise/sunset + thithi
    # transitions off this cache via is_poornima.
    cache = update_common_events(cache)
    cache = update_navapoojitham(cache)
    cache = update_sishya_bday(cache)
    cache = update_chothi_theerthayathra(cache)

    write_cache(cache)
