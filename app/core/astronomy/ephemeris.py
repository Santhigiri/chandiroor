from skyfield.api import load
from skyfield import api

ephem = load("de421.bsp")

earth = ephem["earth"]
sun = ephem["sun"]
moon = ephem["moon"]

ts = api.load.timescale()
