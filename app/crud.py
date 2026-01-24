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


def create_user(db: Session, email: str, password: str):
    user = User(
        email=email,
        hashed_password=hash_password(password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

from app.models import User

def create_user_oauth(db, email: str, provider: str = "google", provider_id: str | None = None):
    user = User(
        email=email,
        hashed_password=None,
        provider=provider,
        provider_id=provider_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
