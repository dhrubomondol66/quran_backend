from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Enum
from app.database import Base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

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

class SubscriptionStatus(str, enum.Enum):
    FREE = "free"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    LIFETIME = "lifetime"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    provider = Column(String, nullable=False, default="local")
    provider_id = Column(String, nullable=True, unique=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    
    # Subscription fields
    subscription_status = Column(
        Enum(SubscriptionStatus), 
        default=SubscriptionStatus.FREE, 
        nullable=False
    )
    subscription_plan = Column(String, nullable=True)  # "monthly", "yearly", "lifetime"
    stripe_customer_id = Column(String, unique=True, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True)
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    payments = relationship("Payment", back_populates="user")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stripe_payment_intent_id = Column(String, unique=True, nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String, default="usd", nullable=False)
    status = Column(String, nullable=False)  # "succeeded", "pending", "failed"
    plan_type = Column(String, nullable=True)  # "monthly", "yearly", "lifetime"
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="payments")