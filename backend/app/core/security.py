from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt only uses the first 72 bytes of a password; reject longer ones instead of silently truncating
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8


class InvalidToken(Exception):
    """Raised when an access token is missing, malformed, expired or badly signed."""


def validate_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Parol kamida {MIN_PASSWORD_LENGTH} belgidan iborat bo'lishi kerak")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Parol {MAX_PASSWORD_BYTES} baytdan uzun bo'lmasligi kerak")


def get_password_hash(password: str) -> str:
    validate_password_strength(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    encoded = plain_password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, hashed_password.encode("ascii"))
    except ValueError:
        return False


def create_access_token(subject: str, extra_claims: Optional[Dict[str, Any]] = None,
                        expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    claims = {**(extra_claims or {}), "sub": subject, "iat": now, "exp": expire, "type": "access"}
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        raise InvalidToken(str(e)) from e
    if claims.get("type") != "access" or not claims.get("sub"):
        raise InvalidToken("Token turi noto'g'ri")
    return claims
