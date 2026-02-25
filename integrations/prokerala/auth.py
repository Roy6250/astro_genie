"""
Prokerala OAuth2 client credentials: get access token and cache until expiry.
Reads from env (after loading .env) or from config.PROKERALA_* when run as part of this app.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://api.prokerala.com/token"
_CACHE: dict[str, tuple[str, float]] = {}  # (token, expires_at)


def _get_credentials() -> tuple[str, str]:
    """Get client_id and client_secret from env, then from config if available."""
    client_id = (os.getenv("PROKERALA_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("PROKERALA_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        try:
            from config import PROKERALA_CLIENT_ID, PROKERALA_CLIENT_SECRET
            client_id = (PROKERALA_CLIENT_ID or "").strip()
            client_secret = (PROKERALA_CLIENT_SECRET or "").strip()
        except ImportError:
            pass
    return client_id, client_secret


def _get_token_from_api() -> tuple[str, int]:
    client_id, client_secret = _get_credentials()
    if not client_id or not client_secret:
        raise ValueError("PROKERALA_CLIENT_ID and PROKERALA_CLIENT_SECRET must be set")

    body = (
        f"grant_type=client_credentials"
        f"&client_id={urllib.parse.quote(client_id, safe='')}"
        f"&client_secret={urllib.parse.quote(client_secret, safe='')}"
    )
    req = urllib.request.Request(
        TOKEN_URL,
        data=body.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    token = data.get("access_token")
    expires_in = int(data.get("expires_in", 3600))
    if not token:
        raise ValueError("Prokerala token response missing access_token")
    return token, expires_in


def get_access_token() -> str:
    """Return a valid access token, using cache until near expiry (refresh 5 min early)."""
    now = time.time()
    if _CACHE:
        token, expires_at = _CACHE.get("token", ("", 0.0))
        if token and expires_at > now + 300:  # 5 min buffer
            return token

    token, expires_in = _get_token_from_api()
    _CACHE["token"] = (token, now + expires_in)
    return token
