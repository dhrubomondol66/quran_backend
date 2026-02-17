from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.deps import get_current_user
from app.models import User, Notification, DeviceToken
from pydantic import BaseModel


router = APIRouter()


# Request/Response Models
class DeviceTokenRequest(BaseModel):
    token: str
    device_type: str  # "ios", "android", "web"


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None  
    
    class Config:
        from_attributes = True


# Endpoints
@router.post("/device-token")
def register_device_token(
    token_data: DeviceTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register user's device token for push notifications"""
    
    # Check if token already exists
    existing_token = db.query(DeviceToken).filter(
        DeviceToken.token == token_data.token
    ).first()
    
    if existing_token:
        # Update existing token
        existing_token.user_id = current_user.id
        existing_token.device_type = token_data.device_type
        existing_token.is_active = True
        existing_token.last_used = datetime.utcnow()
    else:
        # Create new token
        new_token = DeviceToken(
            user_id=current_user.id,
            token=token_data.token,
            device_type=token_data.device_type
        )
        db.add(new_token)
    
    db.commit()
    
    return {"success": True, "message": "Device token registered"}


@router.get("/notifications", response_model=List[NotificationResponse])
def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's notifications"""
    
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id
    )
    
    if unread_only:
        query = query.filter(Notification.is_read == False)
    
    notifications = query.order_by(
        desc(Notification.created_at)
    ).limit(limit).all()
    
    return [
        NotificationResponse(
            id=n.id,
            type=n.type.value,
            title=n.title,
            message=n.message,
            is_read=n.is_read,
            created_at=n.created_at,
            related_entity_type=n.related_entity_type,
            related_entity_id=n.related_entity_id
        )
        for n in notifications
    ]


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read"""
    
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "message": "Notification marked as read"}


@router.post("/notifications/mark-all-read")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all notifications as read"""
    
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({
        "is_read": True,
        "read_at": datetime.utcnow()
    })
    
    db.commit()
    
    return {"success": True, "message": "All notifications marked as read"}


@router.get("/notifications/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get count of unread notifications"""
    
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    
    return {"unread_count": count}


@router.delete("/notifications/{notification_id}")
def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a notification"""
    
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notification)
    db.commit()
    
    return {"success": True, "message": "Notification deleted"}