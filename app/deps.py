from fastapi import Depends, HTTPException, WebSocket
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import User
from app.auth import SECRET_KEY, ALGORITHM  # or from app.config - pick one

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Get current authenticated user from JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


async def get_current_user_ws(
    websocket: WebSocket,
    db: Session
) -> Optional[User]:
    """
    Get user from WebSocket connection with JWT token.
    
    Token should be passed as query parameter:
    ws://localhost:8000/voice/ws/recite?token=YOUR_JWT_TOKEN&surah_number=1
    
    Returns None if token is missing or invalid (allows anonymous connections).
    """
    try:
        token = websocket.query_params.get("token")
        if not token:
            return None
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user
    except (JWTError, ValueError):
        return None