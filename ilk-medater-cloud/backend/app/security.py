"""Mots de passe, sessions serveur, MFA TOTP, codes de récupération et limitation de débit."""
import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pwdlib import PasswordHash

from .config import get_settings

hasher = PasswordHash.recommended()  # Argon2id
_DUMMY_HASH = hasher.hash("valeur-factice-pour-temps-constant")

SESSION_COOKIE = "ilk_session"
CSRF_HEADER = "x-ilk-csrf"


def now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ Mots de passe
def check_password_policy(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Le mot de passe doit contenir au moins 12 caractères")
    classes = sum(any(f(c) for c in password) for f in (str.islower, str.isupper, str.isdigit, lambda c: not c.isalnum()))
    if classes < 3:
        raise ValueError("Le mot de passe doit mélanger au moins 3 types : minuscules, majuscules, chiffres, symboles")


def hash_password(password: str) -> str:
    check_password_policy(password)
    return hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        hasher.verify(password, _DUMMY_HASH)  # temps de réponse constant même si le compte n'existe pas
        return False
    try:
        return hasher.verify(password, password_hash)
    except Exception:
        return False


# ------------------------------------------------------------------ Sessions (jeton opaque, stocké haché)
def new_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hmac.new(get_settings().session_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def session_expiry() -> datetime:
    return now() + timedelta(hours=get_settings().session_absolute_hours)


# ------------------------------------------------------------------ MFA
def _aes() -> AESGCM:
    key = hashlib.sha256(get_settings().mfa_encryption_key.encode()).digest()
    return AESGCM(key)


def encrypt_secret(secret: str) -> str:
    nonce = secrets.token_bytes(12)
    return base64.b64encode(nonce + _aes().encrypt(nonce, secret.encode(), b"ilk-totp")).decode()


def decrypt_secret(blob: str) -> str:
    raw = base64.b64decode(blob)
    return _aes().decrypt(raw[:12], raw[12:], b"ilk-totp").decode()


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="ilk.medater Cloud")


def verify_totp(secret: str, code: str) -> bool:
    code = (code or "").strip().replace(" ", "")
    return code.isdigit() and len(code) == 6 and pyotp.TOTP(secret).verify(code, valid_window=1)


def new_recovery_codes(n: int = 10) -> list[str]:
    return ["-".join(secrets.token_hex(3) for _ in range(3)) for _ in range(n)]


def normalize_recovery(code: str) -> str:
    return (code or "").strip().lower().replace(" ", "")


# ------------------------------------------------------------------ Limitation de débit (mémoire, une instance)
class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        t = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and t - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(t)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
