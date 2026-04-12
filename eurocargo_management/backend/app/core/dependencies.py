"""FastAPI reusable dependencies (auth, etc.)."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Decode the Bearer JWT and return the corresponding User row."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Not authenticated')
    try:
        payload = decode_access_token(credentials.credentials)
        username: str = payload.get('sub', '')
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Invalid or expired token')

    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='User not found')
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Like get_current_user but additionally enforces the admin role."""
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail='Admin access required')
    return current_user


def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias='X-API-Key'),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    """Accept requests that carry either:
    - a valid X-API-Key header (service-to-service), or
    - a valid Bearer JWT (admin UI or any authenticated user).
    """
    # 1. API key check
    if x_api_key is not None:
        if not settings.ecm_api_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail='API key authentication is not configured')
        if x_api_key == settings.ecm_api_key:
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Invalid API key')

    # 2. JWT check
    if credentials:
        try:
            decode_access_token(credentials.credentials)
            return
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Invalid or expired token')

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail='Not authenticated')
