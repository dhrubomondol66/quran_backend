from sqlalchemy.orm import Session, joinedload
from app.models import Surah, User
from app.auth import hash_password

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
    return db.query(User).filter(User.provider_id == provider_id).first()

def create_user(db: Session, email: str, password: str):
    user = User(
        email=email,
        hashed_password=hash_password(password),
        provider="local"
    )
    db.add(user)
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
        last_name=last_name
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user