from sqlalchemy.orm import Session
from app.models import Notification, NotificationType, User, DeviceToken, Community
from datetime import datetime
from typing import List, Optional
import logging
from app.firebase_admin import send_fcm_message
from app.config import ADMIN_EMAILS

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
        """Create a notification for a user and trigger push"""
        
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
        """Send real-time push notification using Firebase"""
        
        # Get user's active device tokens
        tokens = db.query(DeviceToken).filter(
            DeviceToken.user_id == notification.user_id,
            DeviceToken.is_active == True
        ).all()
        
        if not tokens:
            logger.info(f"No active device tokens for user {notification.user_id}")
            return
        
        token_list = [t.token for t in tokens]
        
        # Prepare data payload
        data = {
            "notification_id": str(notification.id),
            "type": notification.type.value,
        }
        if notification.related_entity_type:
            data["related_entity_type"] = notification.related_entity_type
        if notification.related_entity_id:
            data["related_entity_id"] = str(notification.related_entity_id)

        # Send via FCM
        success = send_fcm_message(
            tokens=token_list,
            title=notification.title,
            body=notification.message,
            data=data
        )
        
        if success:
            notification.is_sent = True
            db.commit()
            logger.info(f"FCM push sent to {len(token_list)} devices for user {notification.user_id}")
    
    @staticmethod
    def notify_admins(db: Session, notification_type: NotificationType, title: str, message: str, related_entity_type: str = None, related_entity_id: int = None):
        """Notify all admin users"""
        admins = db.query(User).filter(User.email.in_(ADMIN_EMAILS)).all()
        for admin in admins:
            NotificationService.create_notification(
                db=db,
                user_id=admin.id,
                notification_type=notification_type,
                title=title,
                message=message,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id
            )

    @staticmethod
    def broadcast_notification(db: Session, notification_type: NotificationType, title: str, message: str, related_entity_type: str = None, related_entity_id: int = None):
        """Notify all users in the system"""
        # Note: For very large user bases, this should be handled via FCM Topics
        # but for this app, we'll iterate through users with tokens
        users_with_tokens = db.query(User.id).join(DeviceToken).filter(DeviceToken.is_active == True).distinct().all()
        
        for user_row in users_with_tokens:
            NotificationService.create_notification(
                db=db,
                user_id=user_row.id,
                notification_type=notification_type,
                title=title,
                message=message,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id
            )

    # --- Specific Trigger Methods ---

    @staticmethod
    def notify_admin_new_user(db: Session, user_email: str):
        """Trigger: New user registration"""
        NotificationService.notify_admins(
            db=db,
            notification_type=NotificationType.ADMIN_USER_REGISTERED,
            title="New User Registered! 👤",
            message=f"User {user_email} has just joined the app."
        )

    @staticmethod
    def notify_admin_user_deleted(db: Session, user_email: str):
        """Trigger: User deleted account"""
        NotificationService.notify_admins(
            db=db,
            notification_type=NotificationType.ADMIN_USER_DELETED,
            title="User Account Deleted 🗑️",
            message=f"User {user_email} has deleted their account."
        )

    @staticmethod
    def notify_admin_community_created(db: Session, community_name: str, creator_name: str):
        """Trigger: User created a community"""
        NotificationService.notify_admins(
            db=db,
            notification_type=NotificationType.ADMIN_COMMUNITY_CREATED,
            title="New Community Created! 🏘️",
            message=f"{creator_name} created a new community: '{community_name}'"
        )

    @staticmethod
    def notify_admin_premium_purchased(db: Session, user_email: str, plan_type: str):
        """Trigger: User purchased premium"""
        NotificationService.notify_admins(
            db=db,
            notification_type=NotificationType.ADMIN_PREMIUM_PURCHASED,
            title="Premium Purchase! 💎",
            message=f"User {user_email} just purchased the {plan_type} plan."
        )

    @staticmethod
    def notify_admin_feature_request(db: Session, user_email: str, feature_title: str):
        """Trigger: User sent feature request"""
        NotificationService.notify_admins(
            db=db,
            notification_type=NotificationType.ADMIN_FEATURE_REQUEST,
            title="New Feature Request! 💡",
            message=f"{user_email} requested: '{feature_title}'"
        )

    @staticmethod
    def broadcast_new_book(db: Session, book_title: str, book_id: int):
        """Trigger: Admin added new book to library"""
        NotificationService.broadcast_notification(
            db=db,
            notification_type=NotificationType.NEW_BOOK_ADDED,
            title="New Book in Library! 📚",
            message=f"'{book_title}' is now available in the library. Check it out!",
            related_entity_type="book",
            related_entity_id=book_id
        )

    # --- Existing Community Methods (Updated to use push automatically) ---

    @staticmethod
    def notify_community_created(db: Session, community_id: int, creator_id: int):
        """Notify all users when a new community is available (User notification)"""
        community = db.query(Community).filter(Community.id == community_id).first()
        if not community: return
        
        # Also notify admin about the creation
        creator = db.query(User).filter(User.id == creator_id).first()
        creator_name = f"{creator.first_name or ''} {creator.last_name or ''}".strip() or creator.email.split('@')[0]
        NotificationService.notify_admin_community_created(db, community.name, creator_name)
        
        # User notification
        NotificationService.broadcast_notification(
            db=db,
            notification_type=NotificationType.COMMUNITY_CREATED,
            title="New Community Available!",
            message=f"'{community.name}' community was just created. Join now!",
            related_entity_type="community",
            related_entity_id=community_id
        )

    @staticmethod
    def notify_invite_accepted(db: Session, inviter_id: int, invitee_name: str, community_name: str):
        title = "Invitation Accepted ✅"
        message = f"{invitee_name} joined your community '{community_name}'!"
        NotificationService.create_notification(db, inviter_id, NotificationType.INVITE_ACCEPTED, title, message, "community")

    @staticmethod
    def notify_invite_declined(db: Session, inviter_id: int, invitee_name: str, community_name: str):
        title = "Invitation Declined ❌"
        message = f"{invitee_name} declined to join '{community_name}'."
        NotificationService.create_notification(db, inviter_id, NotificationType.INVITE_DECLINED, title, message, "community")

    @staticmethod
    def notify_join_request(db: Session, creator_id: int, requester_name: str, community_name: str, request_id: int):
        title = "New Join Request 📩"
        message = f"{requester_name} wants to join '{community_name}'."
        NotificationService.create_notification(db, creator_id, NotificationType.JOIN_REQUEST, title, message, "join_request", request_id)

    @staticmethod
    def notify_subscription_expiring(db: Session, user_id: int, days_remaining: int):
        title = "Subscription Expiring ⏳"
        message = f"Your subscription expires in {days_remaining} days. Renew now!"
        NotificationService.create_notification(db, user_id, NotificationType.SUBSCRIPTION_EXPIRING, title, message, "subscription", user_id)