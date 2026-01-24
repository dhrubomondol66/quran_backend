from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport.requests import Request
from app.database import get_db
from app import crud
from app.auth import create_access_token

router = APIRouter()

GOOGLE_CLIENT_ID = "85715069783-dos5k81m9682gp0255ai69a8rascddf7.apps.googleusercontent.com"

@router.post("/google")
def google_login(payload: dict, db: Session = Depends(get_db)):
    try:
        id_info = id_token.verify_oauth2_token(
            payload["id_token"],
            Request(),
            GOOGLE_CLIENT_ID,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    
    email = id_info.get("email")
    google_user_id = id_info.get("sub")
    
    if not email or not google_user_id:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    

    user = crud.get_user_by_email(db, email)
    if not user:
        user = crud.get_user_by_provider_id(db, google_user_id)
    
  
    if not user:
        first_name = id_info.get("given_name", "")
        last_name = id_info.get("family_name", "")
        
        user = crud.create_user_oauth(
            db,
            email=email,
            provider="google",
            provider_id=google_user_id,
            first_name=first_name,
            last_name=last_name
        )
    
    token = create_access_token({"sub": str(user.id)})
    
    return {
        "access_token": token,
        "token_type": "bearer"
    }