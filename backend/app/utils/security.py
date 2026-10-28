"""Cryptographic security utilities for authentication, passwords, and tokens."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional, Dict, Any

from app.config import settings

def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2-HMAC-SHA256 with a secure salt."""
    if not password:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", 
        password.encode("utf-8"), 
        salt.encode("utf-8"), 
        100_000
    )
    return f"{salt}${dk.hex()}"

get_password_hash = hash_password

def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2-HMAC-SHA256 hash."""
    if not password or not hashed or "$" not in hashed:
        return False
    try:
        salt, expected_hex = hashed.split("$", 1)
        dk = hashlib.pbkdf2_hmac(
            "sha256", 
            password.encode("utf-8"), 
            salt.encode("utf-8"), 
            100_000
        )
        return secrets.compare_digest(dk.hex(), expected_hex)
    except Exception:
        return False

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)

def create_access_token(data: Dict[str, Any], expires_delta_seconds: int = 43200) -> str:
    """Create a cryptographically signed session token (default 12 hours)."""
    now = int(time.time())
    payload = dict(data)
    payload["iat"] = now
    payload["exp"] = now + expires_delta_seconds
    
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)
    
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)
    
    return f"{payload_b64}.{sig_b64}"

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a signed session token. Returns payload dict or None if invalid/expired."""
    if not token or "." not in token:
        return None
    try:
        parts = token.strip().split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts[0], parts[1]
        
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)
        
        if not secrets.compare_digest(expected_sig, actual_sig):
            return None
            
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        
        # Check expiration
        now = int(time.time())
        if "exp" in payload and payload["exp"] < now:
            return None
            
        return payload
    except Exception:
        return None
