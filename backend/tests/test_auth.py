"""require_auth: every success and failure branch, with a locally generated ES256 key (no network)."""
import inspect
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from jwt.exceptions import PyJWKClientError

from app import dependencies
from app.dependencies import require_auth


@pytest.fixture
def key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def jwks(monkeypatch, key):
    client = SimpleNamespace(get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=key.public_key()))
    monkeypatch.setattr(dependencies, "get_jwks_client", lambda: client)


def _token(key, **claims):
    return jwt.encode({"sub": "user-1", "exp": int(time.time()) + 600, **claims}, key, algorithm="ES256")


def _status(authorization):
    with pytest.raises(HTTPException) as e:
        require_auth(authorization)
    return e.value.status_code, e.value.detail


def test_is_sync_so_blocking_jwks_fetch_runs_in_threadpool():
    assert not inspect.iscoroutinefunction(require_auth)


def test_valid_token_returns_payload(jwks, key):
    assert require_auth(f"Bearer {_token(key)}")["sub"] == "user-1"


def test_missing_header():
    assert _status(None) == (401, "Missing Authorization header")


def test_wrong_scheme():
    assert _status("Basic abc")[0] == 401


def test_expired_token(jwks, key):
    assert _status(f"Bearer {_token(key, exp=int(time.time()) - 10)}") == (401, "Token expired")


def test_token_signed_by_another_key(jwks):
    other = ec.generate_private_key(ec.SECP256R1())
    assert _status(f"Bearer {_token(other)}")[0] == 401


def test_garbage_token(jwks):
    assert _status("Bearer not.a.jwt")[0] == 401


def test_no_matching_signing_key_is_401_not_500(monkeypatch, key):
    def no_key(_t):
        raise PyJWKClientError("Unable to find a signing key that matches")

    monkeypatch.setattr(dependencies, "get_jwks_client", lambda: SimpleNamespace(get_signing_key_from_jwt=no_key))
    assert _status(f"Bearer {_token(key)}")[0] == 401
