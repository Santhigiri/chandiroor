"""
Application configuration read from the environment.

A single ``settings`` singleton is exported and imported directly wherever
configuration is needed, mirroring how ``core.constants`` is consumed. Values
are read from environment variables (and an optional ``.env`` file, already
gitignored), so secrets never live in the repository.

Only auth-related settings live here for now — the panchangam computation
constants remain in ``core.constants``.
"""
from __future__ import annotations

import warnings

from pydantic_settings import BaseSettings, SettingsConfigDict

# A recognisable placeholder used when JWT_SECRET_KEY is not configured. In
# production the deployment MUST override this via the environment (e.g. a GCP
# Cloud Run env var / Secret Manager); a warning is emitted at import time when
# the default is still in use.
_DEV_SECRET_KEY = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── JWT signing ────────────────────────────────────────────────────────────
    jwt_secret_key: str = _DEV_SECRET_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60          # 1 hour
    refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # ── Auth cookies ───────────────────────────────────────────────────────────
    # Tokens are delivered as HTTP-only cookies (never in the response body), so
    # browser JavaScript can never read them. These control the cookie flags.
    #   cookie_secure   — only send over HTTPS. Browsers still accept Secure
    #                     cookies on localhost, so the default works in dev too.
    #   cookie_samesite — "lax"/"strict"/"none". "lax" is fine when the frontend
    #                     and API share a registrable domain (incl. localhost on
    #                     different ports). Truly cross-site deployments need
    #                     "none" (which also requires cookie_secure=True).
    #   cookie_domain   — optional shared parent domain (e.g. ".example.com").
    cookie_secure: bool = True
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None

    # ── CORS ───────────────────────────────────────────────────────────────────
    # Credentialed (cookie-bearing) requests cannot use a wildcard origin, so the
    # allowed frontend origins must be listed explicitly. Provide a comma- or
    # JSON-style list via the CORS_ALLOW_ORIGINS env var in non-dev deployments.
    cors_allow_origins: list[str] = [
        "http://localhost:3000",
        "https://panchangam.santhigiri.app",
    ]

    # ── Initial admin seeding (optional) ──────────────────────────────────────
    # When both are set, an admin user is created at startup if it does not yet
    # exist. Leave unset to skip seeding entirely.
    initial_admin_username: str | None = None
    initial_admin_password: str | None = None

    # ── Google Sign-In (optional) ─────────────────────────────────────────────
    # The OAuth 2.0 Client ID from Google Cloud Console (APIs & Services →
    # Credentials), used as the required `audience` when verifying a Google ID
    # token in `core.security.verify_google_id_token`. Required for
    # `POST /auth/google` to work; that endpoint fails closed (401) if unset.
    google_client_id: str | None = None


settings = Settings()

if settings.jwt_secret_key == _DEV_SECRET_KEY:
    warnings.warn(
        "JWT_SECRET_KEY is using the insecure development default. "
        "Set a strong JWT_SECRET_KEY environment variable in production.",
        stacklevel=2,
    )
