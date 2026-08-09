from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.session import get_db, get_session_factory
from app.models.user import User


password_hasher = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="认证凭据无效或已过期",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user: User) -> str:
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="认证服务尚未配置")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": str(user.id), "exp": expires_at, "role": "admin" if user.is_admin else "user"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="认证服务尚未配置")
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub", ""))
    except (InvalidTokenError, TypeError, ValueError):
        raise _CREDENTIALS_EXCEPTION
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION
    return user


def bootstrap_admin(session_factory: sessionmaker[Session] | None = None) -> bool:
    """Create the configured local administrator once; never log its credentials."""
    settings = get_settings()
    if bool(settings.bootstrap_admin_username) != bool(settings.bootstrap_admin_password):
        raise RuntimeError("管理员初始化用户名和密码必须同时配置")
    if not settings.bootstrap_admin_username:
        return False
    if not settings.jwt_secret_key:
        raise RuntimeError("初始化管理员前必须配置 JWT_SECRET_KEY")

    with (session_factory or get_session_factory())() as db:
        existing = db.query(User).filter(User.username == settings.bootstrap_admin_username).one_or_none()
        if existing is not None:
            return False
        db.add(
            User(
                username=settings.bootstrap_admin_username,
                password_hash=hash_password(settings.bootstrap_admin_password),
                is_active=True,
                is_admin=True,
            )
        )
        db.commit()
    return True
