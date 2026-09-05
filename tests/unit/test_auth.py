"""Unit tier — bearer auth core. IDs: AC-MCP-031..033.

Pure logic, no transport, no fastapi required for the core. The module reads
its config from the environment at import time, so each test configures the
env via monkeypatch and reloads ``src.auth`` to re-read it — deterministic
control over the fail-closed behaviour without global state.
"""
import importlib

import pytest

import src.auth as auth

try:
    from fastapi import HTTPException  # only needed for the dependency tests
except ImportError:
    HTTPException = None


@pytest.fixture
def auth_env(monkeypatch):
    """Apply an env config (None = unset) and reload src.auth to re-read it."""

    def _apply(token=None, disabled=None):
        if token is None:
            monkeypatch.delenv("AUTH_BEARER_TOKEN", raising=False)
        else:
            monkeypatch.setenv("AUTH_BEARER_TOKEN", token)
        if disabled is None:
            monkeypatch.delenv("AUTH_DISABLED", raising=False)
        else:
            monkeypatch.setenv("AUTH_DISABLED", disabled)
        importlib.reload(auth)
        return auth

    return _apply


def test_verify_token_correct_and_incorrect(auth_env):
    """AC-MCP-031: verify_token accepts the configured token, rejects wrong/None/empty."""
    auth_env(token="s3cret-token", disabled="0")
    assert auth.AUTH_TOKEN == "s3cret-token"
    assert auth.auth_enabled() is True
    assert auth.verify_token("s3cret-token") is True
    assert auth.verify_token("wrong-token") is False
    assert auth.verify_token(None) is False
    assert auth.verify_token("") is False


def test_fail_closed_token_unset(auth_env):
    """AC-MCP-032: no token configured (and not disabled) => nothing verifies
    and the dependency denies every request — fail closed."""
    auth_env(token=None, disabled=None)
    assert auth.AUTH_TOKEN is None
    assert auth.AUTH_DISABLED is False
    assert auth.auth_enabled() is False
    assert auth.verify_token("anything") is False
    assert auth.verify_token(None) is False
    if HTTPException is None:
        pytest.skip("fastapi not installed — dependency behavior covered in integration tier")
    with pytest.raises(HTTPException) as exc:
        auth.require_bearer("Bearer anything")
    assert exc.value.status_code == 401
    assert exc.value.detail == "unauthorized"
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


def test_require_bearer_accepts_exact_token(auth_env):
    """Dependency happy path: 'Bearer <token>' passes; anything else is 401."""
    auth_env(token="s3cret-token", disabled="0")
    if HTTPException is None:
        pytest.skip("fastapi not installed — dependency behavior covered in integration tier")
    auth.require_bearer("Bearer s3cret-token")  # exact match passes
    with pytest.raises(HTTPException) as exc:
        auth.require_bearer("Bearer wrong-token")
    assert exc.value.status_code == 401
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"
    with pytest.raises(HTTPException) as exc:
        auth.require_bearer(None)
    assert exc.value.status_code == 401


def test_auth_disabled_env_authorized(auth_env):
    """AC-MCP-033: AUTH_DISABLED=1 turns auth off — dependency passes without a header."""
    auth_env(token="s3cret-token", disabled="1")
    assert auth.AUTH_DISABLED is True
    assert auth.auth_enabled() is False
    auth.require_bearer(None)  # passes with no header at all
    auth.require_bearer("Bearer anything")  # passes with any header
    # verify_token itself stays strict: it never authorizes while disabled
    assert auth.verify_token("s3cret-token") is False