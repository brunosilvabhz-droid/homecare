import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    """Validate password-login challenges when Turnstile is configured."""
    if not settings.turnstile_secret_key:
        return True
    if not token:
        return False

    # The API runs behind Caddy/Docker, so request.client is normally the proxy's
    # private address, not the visitor's IP. Cloudflare makes remoteip optional;
    # sending the proxy address can invalidate an otherwise valid challenge.
    payload = {"secret": settings.turnstile_secret_key, "response": token}
    try:
        response = requests.post(TURNSTILE_VERIFY_URL, data=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            logger.warning("Turnstile rejected token: errors=%s hostname=%s action=%s",result.get("error-codes",[]),result.get("hostname"),result.get("action"))
        return bool(result.get("success"))
    except (requests.RequestException, ValueError):
        logger.exception("Turnstile validation failed")
        return False
