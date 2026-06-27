import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

try:
    from .models import User, get_db
except ImportError:
    from models import User, get_db

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

bcrypt_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(password: str) -> str:
    return bcrypt_pwd.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt_pwd.verify(plain_password, hashed_password)

def create_access_token(user_id:int) -> str:
    expiry = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id),"exp": expiry}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token:str = Depends(oauth2_scheme),db: Session = Depends(get_db)) -> User:
    credentials_error= HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail = "invalid or expired token",
        headers = {"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_error
    return user
        
        

                    