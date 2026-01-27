from sqlalchemy.orm import Session, joinedload
from app.models import Surah, User
from app.auth import hash_password
import secrets
from datetime import datetime, timedelta

def get_all_surahs(db: Session):
    return db.query(Surah).order_by(Surah.number).all()

def get_surah_by_id(db, surah_id: int):
    return (
        db.query(Surah)
        .options(joinedload(Surah.ayahs))
        .filter(Surah.id == surah_id)
        .first()
    )

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user_by_provider_id(db: Session, provider_id: str):
    """Get user by OAuth provider ID"""
    return db.query(User).filter(User.provider_id == provider_id).first()

def get_user_by_verification_token(db: Session, token: str):
    """Get user by email verification token"""
    return db.query(User).filter(User.email_verification_token == token).first()

def create_user(db: Session, email: str, password: str):
    """Create user with email and password (requires verification)"""
    
    # Generate verification token
    verification_token = secrets.token_urlsafe(32)
    token_expires = datetime.utcnow() + timedelta(hours=24)
    
    user = User(
        email=email,
        hashed_password=hash_password(password),
        provider="local",
        is_email_verified=False,  # ✅ Not verified initially
        email_verification_token=verification_token,
        verification_token_expires=token_expires
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def verify_user_email(db: Session, token: str):
    """Verify user's email with token"""
    user = get_user_by_verification_token(db, token)
    
    if not user:
        return None
    
    # Check if token expired
    if user.verification_token_expires < datetime.utcnow():
        return None
    
    # Mark as verified
    user.is_email_verified = True
    user.email_verification_token = None
    user.verification_token_expires = None
    
    db.commit()
    db.refresh(user)
    return user

def create_user_oauth(
    db: Session, 
    email: str, 
    provider: str = "google", 
    provider_id: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None
):
    """Create user from OAuth provider (Google or Apple)"""
    user = User(
        email=email,
        hashed_password=None,
        provider=provider,
        provider_id=provider_id,
        first_name=first_name,
        last_name=last_name,
        is_email_verified=True  # ✅ OAuth users are pre-verified
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user