"""Portal SSO service for Interview Assistant.

Validates RS256 JWTs issued by portal.kolektif360.com and extracts
tenant/user info so the Flask app can trust the session.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

import jwt
import requests

logger = logging.getLogger(__name__)

PORTAL_PUBLIC_KEY_URL = os.environ.get(
    "PORTAL_PUBLIC_KEY_URL",
    "https://portal.kolektif360.com/api/.well-known/jwt-public-key.pem",
)
APP_SLUG = "interview"


@lru_cache(maxsize=1)
def _get_public_key() -> str:
    """Fetch and cache the Portal RS256 public key PEM."""
    resp = requests.get(PORTAL_PUBLIC_KEY_URL, timeout=10)
    resp.raise_for_status()
    return resp.text


def validate_token(token: str) -> dict:
    """Validate a Portal-issued JWT and return its payload.

    Raises jwt.PyJWTError on invalid / expired tokens.
    """
    public_key = _get_public_key()
    payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        options={"verify_exp": True},
    )
    return payload


def clear_key_cache() -> None:
    """Invalidate the cached public key (e.g., after a key rotation)."""
    _get_public_key.cache_clear()
