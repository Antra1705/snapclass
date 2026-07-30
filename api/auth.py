"""JWT-based authentication.

Tokens are signed with JWT_SECRET (HS256) — read from the environment, falling
back to .streamlit/secrets.toml (same file as the Supabase credentials) — and
carry the user's id and role ("teacher" or "student"). Routers depend on
get_current_user / require_teacher / require_student and use assert_self for
"my own data" endpoints.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

ALGORITHM = "HS256"

_bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    id: int
    role: Literal["teacher", "student"]
    name: str = ""


def _secret_from_secrets_toml() -> Optional[str]:
    secrets_path = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return None
    import tomllib

    with open(secrets_path, "rb") as f:
        return tomllib.load(f).get("JWT_SECRET")


def _get_secret() -> str:
    secret = os.environ.get("JWT_SECRET") or _secret_from_secrets_toml()
    if not secret:
        raise RuntimeError(
            "JWT_SECRET must be set as an environment variable "
            "or in .streamlit/secrets.toml"
        )
    return secret


def ensure_jwt_secret_configured() -> None:
    """Called at startup so a missing JWT_SECRET fails fast, not on first login."""
    _get_secret()


def _expiry_minutes() -> int:
    return int(os.environ.get("JWT_EXPIRES_MINUTES", "1440"))


def create_access_token(user_id: int, role: Literal["teacher", "student"], name: str = "") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "name": name,
        "iat": now,
        "exp": now + timedelta(minutes=_expiry_minutes()),
    }
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, _get_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    return AuthenticatedUser(
        id=int(payload["sub"]),
        role=payload["role"],
        name=payload.get("name", ""),
    )


def require_teacher(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access required")
    return user


def require_student(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    return user


def assert_self(user: AuthenticatedUser, path_id: int) -> None:
    """403 when an id in the URL does not match the authenticated user."""
    if user.id != path_id:
        raise HTTPException(status_code=403, detail="You can only access your own data")
