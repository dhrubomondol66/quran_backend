from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport.requests import Request
from app.database import get_db
from app import crud
from app.auth import create_access_token
import logging

router = APIRouter()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = "85715069783-l5ggv452q2ut3a3qbh3i0mgquoo052lt.apps.googleusercontent.com"

@router.post("/google")
def google_login(payload: dict, db: Session = Depends(get_db)):
    # Log the incoming request (without the full token for security)
    logger.info(f"Google login attempt - payload keys: {payload.keys()}")
    
    try:
        id_info = id_token.verify_oauth2_token(
            payload["id_token"],
            Request(),
            GOOGLE_CLIENT_ID,
        )
        logger.info(f"Token verified successfully for email: {id_info.get('email')}")
        
    except ValueError as e:
        # This catches issues like expired tokens, wrong audience, etc.
        logger.error(f"Token verification failed (ValueError): {str(e)}")
        raise HTTPException(
            status_code=401, 
            detail=f"Invalid Google token: {str(e)}"
        )
    except Exception as e:
        # Catch any other errors
        logger.error(f"Unexpected error during token verification: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=401, 
            detail=f"Token verification failed: {str(e)}"
        )
    
    email = id_info.get("email")
    google_user_id = id_info.get("sub")
    
    if not email or not google_user_id:
        raise HTTPException(status_code=401, detail="Invalid Google token: missing email or user ID")
    
    logger.info(f"Looking up user: {email}")
    
    # Check if user exists by email or provider_id
    user = crud.get_user_by_email(db, email)
    if not user:
        user = crud.get_user_by_provider_id(db, google_user_id)
    
    # Create new user if doesn't exist
    if not user:
        first_name = id_info.get("given_name", "")
        last_name = id_info.get("family_name", "")
        
        logger.info(f"Creating new user: {email}")
        
        user = crud.create_user_oauth(
            db,
            email=email,
            provider="google",
            provider_id=google_user_id,
            first_name=first_name,
            last_name=last_name
        )
    else:
        logger.info(f"User found: {user.id}")
    
    token = create_access_token({"sub": str(user.id)})
    
    return {
        "access_token": token,
        "token_type": "bearer"
    }