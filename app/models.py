from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.database import Base
from sqlalchemy.orm import relationship

class Surah(Base):
    __tablename__ = "surahs"

    id = Column(Integer, primary_key=True)
    number = Column(Integer, unique=True, index=True)
    name_ar = Column(String, nullable=False)
    name_en = Column(String, nullable=False)
    ayah_count = Column(Integer, nullable=False)

    ayahs = relationship(
        "Ayah",
        back_populates="surah",
        order_by="Ayah.number"
    )

class Ayah(Base):
    __tablename__ = "ayahs"

    id = Column(Integer, primary_key=True)
    surah_id = Column(Integer, ForeignKey("surahs.id", ondelete="CASCADE"))
    number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)

    surah = relationship("Surah", back_populates="ayahs")
    
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    provider = Column(String, nullable=False, default="local")
    provider_id = Column(String, nullable=True)
