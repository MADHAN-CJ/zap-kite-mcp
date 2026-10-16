from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_VERSION = "v1"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _aes_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode()).digest()


def encrypt(secret: str, plaintext: str) -> str:
    nonce = os.urandom(12)
    sealed = AESGCM(_aes_key(secret)).encrypt(nonce, plaintext.encode(), None)
    return f"{_VERSION}:{_b64(nonce)}:{_b64(sealed)}"


def decrypt(secret: str, stored: str) -> str:
    version, nonce, sealed = stored.split(":")
    if version != _VERSION:
        raise ValueError(f"unsupported ciphertext version {version}")
    return AESGCM(_aes_key(secret)).decrypt(_unb64(nonce), _unb64(sealed), None).decode()


def _mac(secret: str, purpose: str, message: bytes) -> bytes:
    key = hashlib.sha256(f"{purpose}:{secret}".encode()).digest()
    return hmac.new(key, message, hashlib.sha256).digest()


def sign(secret: str, purpose: str, payload: dict[str, Any], ttl_s: int) -> str:
    body = dict(payload, exp=int(time.time()) + ttl_s)
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    return f"{_b64(raw)}.{_b64(_mac(secret, purpose, raw))}"


def verify(secret: str, purpose: str, token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    try:
        raw = _unb64(body)
        if not hmac.compare_digest(_mac(secret, purpose, raw), _unb64(sig)):
            return None
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or int(data.get("exp", 0)) < time.time():
        return None
    return data


def otp_hash(secret: str, code: str, email: str) -> str:
    return _mac(secret, "otp", f"{code}:{email.lower()}".encode()).hex()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
