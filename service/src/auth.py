"""Bearer-token auth for the REST + MCP service.

Two layers:
- a pure stdlib core (env constants, ``auth_enabled``, ``verify_token``) so
  the unit tier needs no fastapi;
- a thin FastAPI dependency (``require_bearer``) that imports fastapi lazily,
  only at the moment it must raise ``HTTPException``.

Security posture: fail closed. Auth is enforced whenever a token is configured
and ``AUTH_DISABLED`` is not ``1``; if the token env is unset the service
denies rather than serving unauthenticated. The token is never logged, and
all comparisons use :func:`hmac.compare_digest` (constant-time).
"""
import hmac
import os

AUTH_TOKEN = os.environ.get("AUTH_BEARER_TOKEN")
AUTH_DISABLED = os.environ.get("AUTH_DISABLED") == "1"


def auth_enabled() -> bool:
    """Decision helper: True when auth is configured and in force.

    Fail closed: False when auth is explicitly disabled (``AUTH_DISABLED=1``)
    OR no token is configured. Callers treat "misconfigured" like "off" and
    must deny rather than serve unauthenticated.
    """
    return not AUTH_DISABLED and bool(AUTH_TOKEN)


def verify_token(token: str | None) -> bool:
    """Constant-time check of a presented token against ``AUTH_TOKEN``.

    Fail closed: any missing piece (auth disabled, no token configured,
    empty/None/non-str presented) verifies as False. Never raises, never
    logs the token.
    """
    if AUTH_DISABLED or not AUTH_TOKEN or not isinstance(token, str) or not token:
        return False
    return hmac.compare_digest(token, AUTH_TOKEN)


def require_bearer(authorization: str | None = None) -> None:
    """FastAPI dependency: 401 unless the header is exactly ``Bearer <token>``.

    - ``AUTH_DISABLED=1`` → pass (local dev).
    - No token configured → fail closed: deny every request.
    - Otherwise → deny unless the header matches, constant-time.
    """
    if AUTH_DISABLED:
        return
    if not AUTH_TOKEN or authorization is None or not hmac.compare_digest(
        authorization, "Bearer " + AUTH_TOKEN
    ):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=401,
            detail="unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )