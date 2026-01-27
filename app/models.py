from sqlalchemy import Column, Float, Integer, String, Text, ForeignKey, DateTime, Boolean, Enum
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
    
# Update the UserProgress model in models.py
class UserProgress(Base):
    __tablename__ = "user_progress"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Progress metrics
    total_surahs_read = Column(Integer, default=0)
    total_time_spent_seconds = Column(Integer, default=0)  # ✅ Changed: total time in app
    total_ayahs_recited = Column(Integer, default=0)
    current_streak = Column(Integer, default=0)  # days
    longest_streak = Column(Integer, default=0)  # days
    last_activity_date = Column(DateTime, nullable=True)
    
    # Accuracy metrics (PRIMARY FOR LEADERBOARD)
    total_recitations = Column(Integer, default=0)
    correct_recitations = Column(Integer, default=0)
    total_accuracy_points = Column(Float, default=0.0)  # ✅ Sum of all accuracy scores
    average_accuracy = Column(Float, default=0.0)  # ✅ PRIMARY LEADERBOARD METRIC
    
    # Secondary leaderboard metrics
    total_recitation_attempts = Column(Integer, default=0)  # ✅ Number of recitation attempts
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="progress")
    activities = relationship("UserActivity", back_populates="progress")
    achievements = relationship("UserAchievement", back_populates="progress")

class ActivityType(str, enum.Enum):
    LISTENING = "listening"
    RECITATION = "recitation"
    READING = "reading"

class UserActivity(Base):
    __tablename__ = "user_activities"
    
    id = Column(Integer, primary_key=True)
    user_progress_id = Column(Integer, ForeignKey("user_progress.id", ondelete="CASCADE"))
    
    activity_type = Column(Enum(ActivityType), nullable=False)
    surah_number = Column(Integer, nullable=False)
    ayah_number = Column(Integer, nullable=True)
    
    # Duration and accuracy
    duration_seconds = Column(Integer, default=0)  # time spent
    accuracy_score = Column(Float, nullable=True)  # for recitations (0-100)
    
    # Points earned
    points_earned = Column(Integer, default=0)
    
    date = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    progress = relationship("UserProgress", back_populates="activities")

class AchievementType(str, enum.Enum):
    STREAK = "STREAK"
    SURAHS_COMPLETED = "SURAHS_COMPLETED"
    HOURS_LISTENED = "HOURS_LISTENED"
    ACCURACY = "ACCURACY"
    RECITATIONS = "RECITATIONS"
    TIME_SPENT = "TIME_SPENT"

class Achievement(Base):
    __tablename__ = "achievements"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String, nullable=True)  # emoji or icon name
    achievement_type = Column(Enum(AchievementType), nullable=False)
    threshold = Column(Integer, nullable=False)  # e.g., 7 for "7 Day Streak"
    points = Column(Integer, default=0)
    
    # Relationships
    user_achievements = relationship("UserAchievement", back_populates="achievement")

class UserAchievement(Base):
    __tablename__ = "user_achievements"
    
    id = Column(Integer, primary_key=True)
    user_progress_id = Column(Integer, ForeignKey("user_progress.id", ondelete="CASCADE"))
    achievement_id = Column(Integer, ForeignKey("achievements.id", ondelete="CASCADE"))
    
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    is_new = Column(Boolean, default=True)  # for showing "New" badge
    
    # Relationships
    progress = relationship("UserProgress", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")

class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    
    # Reading preferences
    text_size = Column(String, default="medium")  # small, medium, large
    translation_language = Column(String, default="en")
    show_translation = Column(Boolean, default=True)
    
    # Audio settings
    audio_voice = Column(String, default="ar.alafasy")  # default reciter
    playback_speed = Column(Float, default=1.0)  # 0.5x to 2.0x
    auto_play_next = Column(Boolean, default=True)
    
    # App settings
    notifications_enabled = Column(Boolean, default=True)
    daily_reminder_time = Column(String, nullable=True)  # HH:MM format
    theme = Column(String, default="light")  # light, dark, auto
    language = Column(String, default="en")
    
    # Privacy
    show_on_leaderboard = Column(Boolean, default=True)
    profile_visibility = Column(String, default="public")  # public, friends, private
    
    # Relationship
    user = relationship("User", back_populates="settings")

# Update User model to include relationships
# Add these to your existing User model:
User.progress = relationship("UserProgress", back_populates="user", uselist=False)
User.settings = relationship("UserSettings", back_populates="user", uselist=False)
    