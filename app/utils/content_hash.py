"""
Deterministic content hashing for ETag generation.

``stable_hash`` takes an already-JSON-native structure (typically the output of
``fastapi.encoders.jsonable_encoder``) and returns a sha256 hex digest that is
stable across processes and runs: keys are sorted and whitespace is stripped so
the digest depends only on content, never on dict ordering or formatting. Being
deterministic, two independent instances computing over identical data produce
identical digests — which is what makes ETag validation work across the
scale-to-zero / multi-instance deployment.
"""
import hashlib
import json
from typing import Any


def stable_hash(encoded: Any) -> str:
    """Return the sha256 hex digest of a JSON-native structure."""
    blob = json.dumps(encoded, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
