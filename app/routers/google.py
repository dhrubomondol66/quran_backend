from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport.requests import Request

from app.database import get_db
from app import crud
from app.auth import create_access_token   # 👈 JWT utils

router = APIRouter()


GOOGLE_CLIENT_ID = "85715069783-dos5k81m9682gp0255ai69a8rascddf7.apps.googleusercontent.com"

@router.post("/google")
def google_login(payload: dict, db: Session = Depends(get_db)):
    try:
        id_info = id_token.verify_oauth2_token(
            payload["id_token"],
            Request(),  # ✅ correct
            GOOGLE_CLIENT_ID,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = id_info["email"]

    user = crud.get_user_by_email(db, email)
    if not user:
        user = crud.create_user_oauth(db, email=email)

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}
