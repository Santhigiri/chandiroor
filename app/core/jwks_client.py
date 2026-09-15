"""
JWKS client for verifying TVM-issued JWTs.

Chandiroor never mints tokens itself — it only verifies access tokens signed
by TVM (the Ashram's auth microservice) with TVM's private key. This module
fetches TVM's published JSON Web Key Set (``settings.tvm_jwks_url``), caches
the raw JWKs in memory keyed by ``kid``, and refetches once on an unknown
``kid`` so a TVM key rotation is picked up without a Chandiroor restart.
"""
from __future__ import annotations

import time
from typing import Any, Dict

import requests

from app.core.config import settings

_JWKS_CACHE_TTL_SECONDS = 15 * 60


class JwksFetchError(Exception):
    """Raised when TVM's JWKS endpoint cannot be reached, parsed, or does not
    contain the requested key."""


_cached_keys: Dict[str, Dict[str, Any]] = {}
_cached_at: float = 0.0


def _fetch_jwks() -> Dict[str, Dict[str, Any]]:
    try:
        response = requests.get(settings.tvm_jwks_url, timeout=5)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise JwksFetchError(f"could not fetch TVM JWKS: {exc}") from exc

    keys: Dict[str, Dict[str, Any]] = {}
    for raw_key in data.get("keys", []):
        kid = raw_key.get("kid")
        if kid:
            keys[kid] = raw_key
    return keys


def get_signing_key(kid: str) -> Dict[str, Any]:
    """Return the raw JWK for *kid*, fetching/refreshing the cache as needed."""
    global _cached_keys, _cached_at

    if not _cached_keys or (time.monotonic() - _cached_at) > _JWKS_CACHE_TTL_SECONDS:
        _cached_keys = _fetch_jwks()
        _cached_at = time.monotonic()

    if kid not in _cached_keys:
        # Possible key rotation on TVM's side — refetch once before giving up.
        _cached_keys = _fetch_jwks()
        _cached_at = time.monotonic()

    try:
        return _cached_keys[kid]
    except KeyError:
        raise JwksFetchError(f"unknown signing key id: {kid!r}") from None


def reset_cache() -> None:
    """Clear the cached key set. Used by tests to force a refetch."""
    global _cached_keys, _cached_at
    _cached_keys = {}
    _cached_at = 0.0
