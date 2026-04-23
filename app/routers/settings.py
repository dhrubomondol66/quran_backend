from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import get_current_user
from app.image_utils import upload_image
from app.models import User, UserSettings, FeatureRequest
from pydantic import BaseModel
from typing import Optional 

router = APIRouter()

class SettingsUpdate(BaseModel):
    # Reading preferences
    text_size: Optional[str] = None
    translation_language: Optional[str] = None
    show_translation: Optional[bool] = None
    
    # Audio settings
    audio_voice: Optional[str] = None
    playback_speed: Optional[float] = None
    auto_play_next: Optional[bool] = None
    
    # App settings
    notifications_enabled: Optional[bool] = None
    daily_reminder_time: Optional[str] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    
    # Privacy
    show_on_leaderboard: Optional[bool] = None
    profile_visibility: Optional[str] = None

def get_or_create_settings(db: Session, user_id: int) -> UserSettings:
    """Get or create user settings"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@router.get("/settings")
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user settings (for Settings screen)"""
    
    settings = get_or_create_settings(db, current_user.id)
    
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email.split('@')[0],
            "subscription_status": current_user.subscription_status,
            "is_premium": current_user.subscription_status in ["active", "lifetime"]
        },
        "reading_preferences": {
            "text_size": settings.text_size,
            "translation_language": settings.translation_language,
            "show_translation": settings.show_translation
        },
        "audio_settings": {
            "audio_voice": settings.audio_voice,
            "playback_speed": settings.playback_speed,
            "auto_play_next": settings.auto_play_next
        },
        "app_settings": {
            "notifications_enabled": settings.notifications_enabled,
            "daily_reminder_time": settings.daily_reminder_time,
            "theme": settings.theme,
            "language": settings.language
        },
        "privacy": {
            "show_on_leaderboard": settings.show_on_leaderboard,
            "profile_visibility": settings.profile_visibility
        }
    }

@router.put("/settings")
def update_settings(
    updates: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user settings"""
    
    settings = get_or_create_settings(db, current_user.id)
    
    # Update only provided fields
    update_data = updates.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if hasattr(settings, field):
            setattr(settings, field, value)
    
    db.commit()
    db.refresh(settings)
    
    return {
        "success": True,
        "message": "Settings updated successfully"
    }

@router.get("/profile")
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user profile information"""
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "provider": current_user.provider,
        "subscription_status": current_user.subscription_status,
        "subscription_plan": current_user.subscription_plan,
        "subscription_end_date": current_user.subscription_end_date,
        "created_at": current_user.created_at
    }

@router.put("/profile")
def update_profile(
    profile_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile"""
    
    if "first_name" in profile_data:
        current_user.first_name = profile_data["first_name"]
    if "last_name" in profile_data:  # ✅ Fixed: removed space
        current_user.last_name = profile_data["last_name"]
    
    db.commit()
    
    return {
        "success": True,
        "message": "Profile updated successfully"
    }

@router.post("/upload-profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload profile picture"""
    
    # Upload to Cloudinary
    image_url = await upload_image(file, folder="quran_app/profiles")
    
    # Update user
    current_user.profile_image_url = image_url
    db.commit()
    
    return {
        "message": "Profile picture uploaded successfully",
        "image_url": image_url
    }

@router.delete("/delete-profile-picture")
def delete_profile_picture(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete profile picture"""
    
    current_user.profile_image_url = None
    db.commit()
    
    return {"message": "Profile picture deleted"}


class FeatureRequestCreate(BaseModel):
    title: str
    description: str

@router.post("/feature-request")
def submit_feature_request(
    request_data: FeatureRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a feature request and notify admins"""
    from app.services.notification_service import NotificationService
    
    new_request = FeatureRequest(
        user_id=current_user.id,
        title=request_data.title,
        description=request_data.description
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    # ✅ Notify Admins about new feature request
    NotificationService.notify_admin_feature_request(db, current_user.email, new_request.title)
    
    return {
        "success": True,
        "message": "Feature request submitted successfully! Admins have been notified.",
        "request_id": new_request.id
    }