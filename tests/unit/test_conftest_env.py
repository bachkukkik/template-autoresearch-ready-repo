"""Unit tier — the spawned-service environment is hermetic. ID: AC-MCP-046.

The integration tier starts the service as a subprocess with
``tests/conftest.py::service_subprocess_env``, which begins from a copy of
``os.environ``. The unit modules that exercise the service in-process
(``test_runner.py``, ``test_service_engine.py``) set ``AUTH_DISABLED=1`` at
import time, so in a single pytest process that value — and any developer's
ambient ``AUTH_BEARER_TOKEN`` — reached an auth-enabled service and it served
unauthenticated requests. This suite pins the fix: an auth setting reaches the
spawn only when the caller passes it.
"""
from conftest import service_subprocess_env

AUTH_KEYS = ("AUTH_DISABLED", "AUTH_BEARER_TOKEN")


def test_inherited_auth_env_does_not_reach_the_service(monkeypatch):
    """AC-MCP-046: an inherited AUTH_DISABLED / AUTH_BEARER_TOKEN is dropped;
    only the explicitly overridden value survives."""
    for key in AUTH_KEYS:
        monkeypatch.setenv(key, "1" if key == "AUTH_DISABLED" else "leak")

    env = service_subprocess_env(AUTH_BEARER_TOKEN="t")
    assert "AUTH_DISABLED" not in env
    assert env["AUTH_BEARER_TOKEN"] == "t"

    bare = service_subprocess_env()
    assert not [key for key in AUTH_KEYS if key in bare]
