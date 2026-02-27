import hashlib
import secrets
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyCookie
from app.config_store import config_store

# We use a simple cookie-based session for a lightweight UI
cookie_sec = APIKeyCookie(name="session_token", auto_error=False)

# In-memory store for active session tokens
active_sessions = set()


def hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    )
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, _ = hashed_password.split(":")
        return hash_password(plain_password, salt) == hashed_password
    except ValueError:
        return False


def generate_token() -> str:
    token = secrets.token_urlsafe(32)
    active_sessions.add(token)
    return token


def verify_session(request: Request, session_token: str = Depends(cookie_sec)):
    config = config_store.load()
    if not config.get("auth_enabled", False):
        return True  # Auth is disabled, permit all

    if not session_token or session_token not in active_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return True


def authenticate_user(username: str, password: str) -> bool:
    config = config_store.load()
    if username != config.get("auth_username"):
        return False

    stored_hash = config.get("auth_password_hash")
    if stored_hash:
        return verify_password(password, stored_hash)

    # Backwards compatibility check and migration
    plaintext = config.get("auth_password")
    if plaintext and password == plaintext:
        return True

    return False


def logout_user(session_token: str):
    if session_token in active_sessions:
        active_sessions.remove(session_token)
