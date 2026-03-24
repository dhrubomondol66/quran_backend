from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import User, SubscriptionStatus
from app.auth import hash_password
import uuid
from datetime import datetime

def register_manual_admins():
    # Make sure tables exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    admins = [
        {"email": "beupintech@gmail.com", "first_name": "Michael", "last_name": "Totok"},
        {"email": "dhrubomondol@gmail.com", "first_name": "Dhrubo", "last_name": "Mondol"}
    ]
    
    password = "admin123"
    hashed_pwd = hash_password(password)
    
    print(f"Starting manual admin registration for {len(admins)} users...")
    
    for admin_data in admins:
        # Check if user already exists
        db_user = db.query(User).filter(User.email == admin_data["email"]).first()
        
        if not db_user:
            new_user = User(
                email=admin_data["email"],
                hashed_password=hashed_pwd,
                first_name=admin_data["first_name"],
                last_name=admin_data["last_name"],
                provider="local",
                is_email_verified=True,
                email_verification_token=str(uuid.uuid4()),
                subscription_status=SubscriptionStatus.ACTIVE,
                subscription_end_date=None,
                created_at=datetime.utcnow()
            )
            db.add(new_user)
            print(f"✅ Registered admin: {admin_data['email']}")
        else:
            # Update existing user to make sure they have the password and status
            db_user.hashed_password = hashed_pwd
            db_user.subscription_status = SubscriptionStatus.ACTIVE
            db_user.is_email_verified = True
            print(f"ℹ️ Updated existing admin: {admin_data['email']}")
            
    db.commit()
    db.close()
    print("All done!")

if __name__ == "__main__":
    register_manual_admins()
