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

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── TVM JWT verification ───────────────────────────────────────────────────
    # TVM's JWKS endpoint (e.g. https://tvm.santhigiri.app/.well-known/jwks.json).
    # Required — there is no local fallback secret, since Chandiroor never signs
    # its own tokens.
    tvm_jwks_url: str
    tvm_jwt_issuer: str = "tvm-api"
    tvm_jwt_audience: str = "tvm-users"

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
