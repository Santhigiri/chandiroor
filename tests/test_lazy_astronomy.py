"""Regression tests: the heavy astronomy stack must load lazily, not at startup.

Importing the app (and therefore the response schema + DB repository) must not
pull in Skyfield / the ephemeris / pyswisseph — that cost belongs only to the
live-computation fallback, which most requests (served from the DB) never hit.

Each check runs in a **fresh subprocess** on purpose: the pytest session's own
``conftest`` imports the transition classes from their heavy modules, so by the
time a normal test runs ``skyfield`` is already in ``sys.modules``. A clean
interpreter is the only faithful way to observe what app import actually loads.
"""
import os
import subprocess
import sys
import textwrap


def _run(script: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": os.environ.get("DATABASE_URL", "sqlite://")},
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_importing_app_does_not_load_astronomy_stack():
    out = _run(
        """
        import sys
        import main  # noqa: F401
        heavy = [
            m for m in ("skyfield", "swisseph", "core.astronomy.ephemeris")
            if m in sys.modules
        ]
        assert not heavy, f"heavy modules loaded at app import: {heavy}"
        print("clean")
        """
    )
    assert out.endswith("clean")


def test_live_computation_loads_skyfield_lazily():
    out = _run(
        """
        import sys
        from datetime import date
        import main  # noqa: F401
        assert "skyfield" not in sys.modules, "skyfield loaded before any compute"
        from core.calendar.panchangam import get_panchangam_data
        get_panchangam_data(date(2026, 1, 15))
        assert "skyfield" in sys.modules, "skyfield never loaded despite compute"
        print("lazy-ok")
        """
    )
    assert out.endswith("lazy-ok")
