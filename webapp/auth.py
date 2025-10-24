"""Helpers for Azure App Service Easy Auth."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from flask import Request

logger = logging.getLogger(__name__)


@dataclass
class Principal:
    oid: str
    name: str
    preferred_username: str


def decode_easy_auth_header(header_value: str) -> Optional[Principal]:
    """Decode the Easy Auth principal header into a Principal."""

    try:
        decoded = base64.b64decode(header_value)
        data: Dict[str, Any] = json.loads(decoded)
        user_claims = {c["typ"]: c["val"] for c in data.get("claims", []) if "typ" in c and "val" in c}
        return Principal(
            oid=user_claims.get("oid", ""),
            name=user_claims.get("name", ""),
            preferred_username=user_claims.get("preferred_username", ""),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to decode Easy Auth header: %s", exc)
        return None


def extract_principal(request: Request) -> Optional[Principal]:
    header = request.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not header:
        return None
    return decode_easy_auth_header(header)
