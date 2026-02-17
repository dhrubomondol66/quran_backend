from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import SubscriptionStatus, User
from app.services.notification_service import NotificationService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def check_expiring_subscriptions():
    
    db = SessionLocal()
    
    try:
        tomorrow = datetime.utcnow() + timedelta(hours=24)
        day_after_tomorrow = datetime.utcnow() + timedelta(hours=48)
        
        expiring_users = db.query(User).filter(
            User.subscription_end_date >= tomorrow,
            User.subscription_end_date < day_after_tomorrow,
            User.subscription_status == SubscriptionStatus.ACTIVE
        ).all()
        
        for user in expiring_users:
            hours_remaining = (user.subscription_end_date - datetime.utcnow()).total_seconds() / 3600
            days_remaining = int(hours_remaining / 24)
            
            NotificationService.notify_subscription_expiring(
                db=db,
                user_id=user.id,
                days_remaining=max(1, days_remaining)
            )
        
        logger.info(f"Checked subscriptions. Found {len(expiring_users)} expiring soon.")
        
    except Exception as e:
        logger.error(f"Error checking subscriptions: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    
    check_expiring_subscriptions()