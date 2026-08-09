from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import CurrentUserRead, TokenRead
from app.services.auth import authenticate_user, create_access_token, get_current_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/token", response_model=TokenRead)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
) -> TokenRead:
    user = authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenRead(access_token=create_access_token(user))


@router.get("/me", response_model=CurrentUserRead)
def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
