from sqlalchemy.orm import Session, joinedload
from app.models import Surah, User
from app.auth import hash_password
import secrets
from datetime import datetime, timedelta
from app.models import Surah, User, SubscriptionStatus


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

def create_user(db: Session, email: str, password: str, first_name: str = None, last_name: str = None):
    """Create user with email and password (requires verification)"""
    
    # Generate verification token
    verification_token = secrets.token_urlsafe(32)
    token_expires = datetime.utcnow() + timedelta(hours=24)
    
    user = User(
        email=email,
        hashed_password=hash_password(password),
        provider="local",
        first_name=first_name,  
        last_name=last_name,  
        is_email_verified=False,
        email_verification_token=verification_token,
        verification_token_expires=token_expires,
        subscription_status=SubscriptionStatus.FREE,
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
        is_email_verified=True,  # ✅ OAuth users are pre-verified
        subscription_status=SubscriptionStatus.FREE,  # ✅ ADD THIS
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_password_reset_token(db: Session, email: str):
    """Create password reset token for user"""
    user = get_user_by_email(db, email)
    
    if not user:
        return None
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    token_expires = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
    
    user.password_reset_token = reset_token
    user.password_reset_expires = token_expires
    
    db.commit()
    db.refresh(user)
    return user

def get_user_by_reset_token(db: Session, token: str):
    """Get user by password reset token"""
    user = db.query(User).filter(User.password_reset_token == token).first()
    
    if not user:
        return None
    
    # Check if token expired
    if user.password_reset_expires < datetime.utcnow():
        return None
    
    return user

def reset_user_password(db: Session, token: str, new_password: str):
    """Reset user password with token"""
    user = get_user_by_reset_token(db, token)
    
    if not user:
        return None
    
    # Update password
    user.hashed_password = hash_password(new_password)
    
    # Clear reset token
    user.password_reset_token = None
    user.password_reset_expires = None
    
    db.commit()
    db.refresh(user)
    return user