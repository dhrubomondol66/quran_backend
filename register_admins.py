from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import User, SubscriptionStatus
from app.auth import hash_password
import uuid
from datetime import datetime

from app.config import ADMIN_EMAILS, ADMIN_DEFAULT_PASSWORD

def register_manual_admins():
    # Make sure tables exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    print(f"Starting manual admin registration for {len(ADMIN_EMAILS)} users from config...")
    
    # Use ADMIN_DEFAULT_PASSWORD for all admins
    hashed_pwd = hash_password(ADMIN_DEFAULT_PASSWORD)
    
    for email in ADMIN_EMAILS:
        # Check if user already exists
        db_user = db.query(User).filter(User.email == email).first()
        
        if not db_user:
            new_user = User(
                email=email,
                hashed_password=hashed_pwd,
                provider="local",
                is_email_verified=True,
                subscription_status=SubscriptionStatus.ACTIVE,
                created_at=datetime.utcnow()
            )
            
            # Set names based on email if possible
            if email == ADMIN_EMAILS[0]:
                new_user.first_name = "Michael"
                new_user.last_name = "Totok"
            elif len(ADMIN_EMAILS) > 1 and email == ADMIN_EMAILS[1]:
                new_user.first_name = "Dhrubo"
                new_user.last_name = "Mondol"
                
            db.add(new_user)
            print(f"Registered admin: {email}")
        else:
            # Update existing user to make sure they have the password and status
            db_user.hashed_password = hashed_pwd
            db_user.subscription_status = SubscriptionStatus.ACTIVE
            db_user.is_email_verified = True
            print(f"Updated existing admin: {email}")
            
    db.commit()
    db.close()
    print("All done!")

if __name__ == "__main__":
    register_manual_admins()
