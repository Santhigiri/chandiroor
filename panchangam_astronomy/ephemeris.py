from pathlib import Path

from skyfield.api import Loader

_loader = Loader(str(Path(__file__).parent))

ephem = _loader("de421.bsp")

earth = ephem["earth"]
sun = ephem["sun"]
moon = ephem["moon"]

ts = _loader.timescale()
