from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import jwt
import requests
from typing import Dict
from app.database import get_db
from app import crud
from app.auth import create_access_token

router = APIRouter()

# TODO: Replace these with your actual Apple credentials
APPLE_CLIENT_ID = "com.yourapp.service"  # Your Service ID from Apple Developer
APPLE_TEAM_ID = "YOUR_TEAM_ID"  # Your Team ID

# Cache for Apple's public keys
APPLE_PUBLIC_KEYS_CACHE: Dict = {}

def get_apple_public_keys():
    """Fetch Apple's public keys for JWT verification"""
    global APPLE_PUBLIC_KEYS_CACHE
    
    if APPLE_PUBLIC_KEYS_CACHE:
        return APPLE_PUBLIC_KEYS_CACHE
    
    try:
        response = requests.get("https://appleid.apple.com/auth/keys")
        response.raise_for_status()
        APPLE_PUBLIC_KEYS_CACHE = response.json()
        return APPLE_PUBLIC_KEYS_CACHE
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch Apple public keys: {str(e)}"
        )

def verify_apple_token(id_token_str: str) -> dict:
    """Verify Apple ID token and return decoded payload"""
    
    # Get Apple's public keys
    apple_keys = get_apple_public_keys()
    
    # Decode token header to get the key id (kid)
    try:
        unverified_header = jwt.get_unverified_header(id_token_str)
        kid = unverified_header.get("kid")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    # Find the matching public key
    public_key = None
    for key in apple_keys.get("keys", []):
        if key.get("kid") == kid:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            break
    
    if not public_key:
        raise HTTPException(status_code=401, detail="Public key not found")
    
    # Verify and decode the token
    try:
        decoded = jwt.decode(
            id_token_str,
            public_key,
            algorithms=["RS256"],
            audience=APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com"
        )
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

@router.post("/apple")
def apple_login(payload: dict, db: Session = Depends(get_db)):
    """
    Handle Apple Sign In
    
    Expected payload:
    {
        "id_token": "eyJraWQ...",
        "user": {  # Only sent on first sign-in
            "name": {
                "firstName": "Ahmed",
                "lastName": "Rahman"
            },
            "email": "ahmed@example.com"
        }
    }
    """
    
    # Validate payload
    if "id_token" not in payload:
        raise HTTPException(status_code=400, detail="id_token is required")
    
    # Verify the Apple ID token
    try:
        id_info = verify_apple_token(payload["id_token"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401, 
            detail=f"Token verification failed: {str(e)}"
        )
    
    # Extract user information from verified token
    apple_user_id = id_info.get("sub")  # Apple's unique user identifier
    email = id_info.get("email")
    
    if not apple_user_id:
        raise HTTPException(
            status_code=401, 
            detail="Invalid Apple token: missing user ID"
        )
    
    # Handle Apple's private relay email
    if not email:
        # If user chose to hide email, use Apple's private relay format
        email = f"{apple_user_id}@privaterelay.appleid.com"
    
    # Check if user exists by email or provider_id
    user = crud.get_user_by_email(db, email)
    if not user:
        user = crud.get_user_by_provider_id(db, apple_user_id)
    
    # Create new user if doesn't exist
    if not user:
        # Extract name from payload (only available on first sign-in)
        user_data = payload.get("user", {})
        name_data = user_data.get("name", {})
        first_name = name_data.get("firstName", "")
        last_name = name_data.get("lastName", "")
        
        user = crud.create_user_oauth(
            db,
            email=email,
            provider="apple",
            provider_id=apple_user_id,
            first_name=first_name,
            last_name=last_name
        )
    
    # Generate JWT token for your app
    token = create_access_token({"sub": str(user.id)})
    
    return {
        "access_token": token,
        "token_type": "bearer"
    }