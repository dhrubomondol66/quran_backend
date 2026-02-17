from sqlalchemy.orm import Session
from app.models import Notification, NotificationType, User, DeviceToken, Community
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications"""
    
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[int] = None
    ) -> Notification:
        """Create a notification for a user"""
        
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        NotificationService.send_push_notification(db, notification)
        
        return notification
    
    @staticmethod
    def send_push_notification(db: Session, notification: Notification):
        """Send push notification to user's devices"""
        
        # Get user's active device tokens
        tokens = db.query(DeviceToken).filter(
            DeviceToken.user_id == notification.user_id,
            DeviceToken.is_active == True
        ).all()
        
        if not tokens:
            logger.info(f"No device tokens for user {notification.user_id}")
            return
        
        logger.info(f"Would send push to {len(tokens)} devices for user {notification.user_id}")
        logger.info(f"Title: {notification.title}")
        logger.info(f"Message: {notification.message}")
        
        # Mark as sent
        notification.is_sent = True
        db.commit()
    
    @staticmethod
    def notify_community_created(db: Session, community_id: int, creator_id: int):
        """Notify all users when a new community is created"""
        
        community = db.query(Community).filter(Community.id == community_id).first()
        if not community:
            return
        
        all_users = db.query(User).filter(User.id != creator_id).all()
        
        title = "New Community Created!"
        message = f"'{community.name}' community is now available. Join now!"
        
        for user in all_users:
            NotificationService.create_notification(
                db=db,
                user_id=user.id,
                notification_type=NotificationType.COMMUNITY_CREATED,
                title=title,
                message=message,
                related_entity_type="community",
                related_entity_id=community_id
            )
        
        logger.info(f"Notified {len(all_users)} users about new community: {community.name}")
    
    @staticmethod
    def notify_invite_accepted(db: Session, inviter_id: int, invitee_name: str, community_name: str):
        """Notify community creator when invite is accepted"""
        
        title = "Invitation Accepted"
        message = f"{invitee_name} accepted your invitation to join '{community_name}'!"
        
        NotificationService.create_notification(
            db=db,
            user_id=inviter_id,
            notification_type=NotificationType.INVITE_ACCEPTED,
            title=title,
            message=message,
            related_entity_type="community",
            related_entity_id=None
        )
    
    @staticmethod
    def notify_invite_declined(db: Session, inviter_id: int, invitee_name: str, community_name: str):
        """Notify community creator when invite is declined"""
        
        title = "Invitation Declined"
        message = f"{invitee_name} declined your invitation to join '{community_name}'."
        
        NotificationService.create_notification(
            db=db,
            user_id=inviter_id,
            notification_type=NotificationType.INVITE_DECLINED,
            title=title,
            message=message,
            related_entity_type="community",
            related_entity_id=None
        )
    
    @staticmethod
    def notify_join_request(db: Session, creator_id: int, requester_name: str, community_name: str, request_id: int):
        """Notify creator when someone requests to join their community"""
        
        title = "New Join Request"
        message = f"{requester_name} wants to join '{community_name}'. Review their request!"
        
        NotificationService.create_notification(
            db=db,
            user_id=creator_id,
            notification_type=NotificationType.JOIN_REQUEST,
            title=title,
            message=message,
            related_entity_type="join_request",
            related_entity_id=request_id
        )
    
    @staticmethod
    def notify_subscription_expiring(db: Session, user_id: int, days_remaining: int):
        """Notify user when subscription is expiring soon"""
        
        title = "Subscription Expiring Soon"
        message = f"Your subscription expires in {days_remaining} day{'s' if days_remaining != 1 else ''}. Renew now to keep your premium features!"
        
        NotificationService.create_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.SUBSCRIPTION_EXPIRING,
            title=title,
            message=message,
            related_entity_type="subscription",
            related_entity_id=user_id
        )