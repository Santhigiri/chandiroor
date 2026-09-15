"""
Application configuration read from the environment.

A single ``settings`` singleton is exported and imported directly wherever
configuration is needed, mirroring how ``core.constants`` is consumed. Values
are read from environment variables (and an optional ``.env`` file, already
gitignored), so secrets never live in the repository.

Chandiroor is a JWT resource server, not an identity provider: it never mints
tokens or stores credentials. It only verifies access tokens minted by TVM
(the Ashram's auth microservice) against TVM's published JWKS.
"""
from __future__ import annotations

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── TVM JWT verification ───────────────────────────────────────────────────
    # TVM's JWKS endpoint (e.g. https://tvm.santhigiri.app/.well-known/jwks.json).
    # The normal path — verification resolves the signing key by the token's
    # `kid` against whatever TVM currently publishes, so a TVM key rotation
    # needs no Chandiroor config change.
    tvm_jwks_url: str | None = None
    # Fallback signing key (PEM-encoded RSA public key), used only when the
    # JWKS endpoint above is unset or unreachable at verification time (TVM
    # down, network partition, or TVM not yet exposing a JWKS endpoint at
    # all). This is TVM's *public* key only — safe to hand out, since it can
    # verify a signature but never produce one — but it is a static value:
    # unlike the JWKS path, rotating TVM's signing key means updating this
    # env var by hand. Prefer TVM_JWKS_URL whenever it's available.
    tvm_jwt_public_key: str | None = None
    tvm_jwt_issuer: str = "tvm-api"
    tvm_jwt_audience: str = "tvm-users"

    @field_validator("tvm_jwt_public_key")
    @classmethod
    def _unescape_literal_newlines(cls, value: str | None) -> str | None:
        # A PEM key set as a single-line env var commonly arrives with
        # literal "\n" (backslash-n) sequences instead of real line breaks —
        # normalize so `cryptography`'s PEM parser accepts it either way.
        return value.replace("\\n", "\n") if value else value

    @model_validator(mode="after")
    def _require_a_verification_source(self) -> "Settings":
        if not self.tvm_jwks_url and not self.tvm_jwt_public_key:
            raise ValueError(
                "Set TVM_JWKS_URL and/or TVM_JWT_PUBLIC_KEY — Chandiroor has "
                "no way to verify a TVM-issued token without at least one."
            )
        return self

    # ── CORS ───────────────────────────────────────────────────────────────────
    # Credentialed (cookie-bearing) requests cannot use a wildcard origin, so the
    # allowed frontend origins must be listed explicitly. Provide a comma- or
    # JSON-style list via the CORS_ALLOW_ORIGINS env var in non-dev deployments.
    cors_allow_origins: list[str] = [
        "http://localhost:3000",
        "https://panchangam.santhigiri.app",
    ]
    # Temporary broad allowance: any HTTPS origin, matched via regex rather than
    # a fixed list (Starlette's CORSMiddleware reflects the specific matched
    # Origin header for credentialed requests, so this stays spec-compliant
    # without resorting to a literal "*"). Override/narrow via the
    # CORS_ALLOW_ORIGIN_REGEX env var; set to unset/None to fall back to only
    # the explicit cors_allow_origins list above.
    cors_allow_origin_regex: str | None = r"https://.*"


settings = Settings()
