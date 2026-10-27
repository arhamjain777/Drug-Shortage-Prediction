"""Password hashing (PBKDF2-SHA256) and HS256 tokens using only the standard library."""
import base64, hashlib, hmac, json, os, time
from backend.app.core.config import settings

ITER = 600_000


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER)
    return f"pbkdf2${ITER}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, it, salt, dk = stored.split("$")
        new = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(new.hex(), dk)
    except (ValueError, TypeError):
        return False


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(user_id: int, role: str) -> str:
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps({"sub": user_id, "role": role, "exp": int(time.time()) + settings.token_minutes * 60}).encode())
    sig = _b64(hmac.new(settings.secret_key.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def decode_token(token: str):
    """Return payload dict or None (bad signature / expired / malformed)."""
    try:
        head, body, sig = token.split(".")
        good = _b64(hmac.new(settings.secret_key.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        payload = json.loads(_unb64(body))
        return payload if payload["exp"] > time.time() else None
    except (ValueError, KeyError, TypeError):
        return None
