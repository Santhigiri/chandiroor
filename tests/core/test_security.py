"""
Tests for TVM access-token verification (``core/security.py``), including the
static-public-key fallback used when TVM's JWKS endpoint is unset or
unreachable.
"""
from __future__ import annotations

import pytest

import app.core.jwks_client as jwks_client
from app.core.config import settings
from app.core.security import TokenError, verify_access_token
from app.utils.roles import Role
from tests.conftest import _test_public_pem, mint_tvm_token


def test_verify_access_token_via_jwks():
    """The normal path: JWKS resolves the signing key by `kid`."""
    token = mint_tvm_token(Role.ADMIN, user_id=42)

    claims = verify_access_token(token)

    assert claims.user_id == 42
    assert claims.role is Role.ADMIN
    assert claims.is_verified is True


def test_verify_access_token_falls_back_to_static_key_when_jwks_unreachable(
    monkeypatch,
):
    """JWKS fetch fails (e.g. TVM unreachable) but a fallback key is
    configured — verification still succeeds against the same keypair."""
    monkeypatch.setattr(settings, "tvm_jwt_public_key", _test_public_pem)
    monkeypatch.setattr(
        jwks_client,
        "_fetch_jwks",
        lambda: (_ for _ in ()).throw(jwks_client.JwksFetchError("TVM unreachable")),
    )
    jwks_client.reset_cache()

    token = mint_tvm_token(Role.USER, user_id=7)

    claims = verify_access_token(token)

    assert claims.user_id == 7
    assert claims.role is Role.USER


def test_verify_access_token_raises_when_jwks_fails_and_no_fallback_configured(
    monkeypatch,
):
    monkeypatch.setattr(settings, "tvm_jwt_public_key", None)
    monkeypatch.setattr(
        jwks_client,
        "_fetch_jwks",
        lambda: (_ for _ in ()).throw(jwks_client.JwksFetchError("TVM unreachable")),
    )
    jwks_client.reset_cache()

    token = mint_tvm_token(Role.USER)

    with pytest.raises(TokenError):
        verify_access_token(token)


def test_verify_access_token_rejects_malformed_token():
    with pytest.raises(TokenError):
        verify_access_token("not-a-real-token")
