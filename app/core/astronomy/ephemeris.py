from pathlib import Path

from skyfield.api import Loader
from skyfield.jpllib import SpiceKernel
from skyfield.timelib import Timescale
from skyfield.vectorlib import VectorFunction

_loader = Loader(str(Path(__file__).parent))

ephem: SpiceKernel = _loader("de421.bsp")

# Barycentric vector functions (each requires summing 2 kernel segments,
# SSB -> body barycenter -> body, except sun which is a direct SSB segment) -
# annotated by their common VectorFunction interface (.at()/.observe()),
# not their concrete VectorSum/ChebyshevPosition subtype.
earth: VectorFunction = ephem["earth"]
sun: VectorFunction = ephem["sun"]
moon: VectorFunction = ephem["moon"]

ts: Timescale = _loader.timescale()
