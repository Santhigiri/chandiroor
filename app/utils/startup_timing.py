"""Captures the wall-clock moment ``app.main`` begins importing.

Must be the very first import in ``app/main.py`` (before ``fastapi``, before
any ``app.features``/``app.core`` import) so ``IMPORT_STARTED_AT`` marks the
true start of the process's import chain — not just this module's own,
near-instant load time. ``app/utils/lifespan.py`` reads it back once the app
is ready to serve traffic to log total startup time (import chain + schema
check), unconditionally, in every environment — this is what regressed
before the fix that made the Skyfield/ephemeris stack load lazily instead of
at import time (see tests/core/astronomy/test_lazy_astronomy.py), so it's
worth always having visible rather than only in an ad hoc local benchmark.
"""
import time

IMPORT_STARTED_AT = time.perf_counter()
