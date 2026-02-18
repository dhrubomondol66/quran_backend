from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app import models
from app.routers import auth, surah
from app.routers.google import router as google_router
from app.routers.apple import router as apple_router
from app.routers.payment import router as payment_router
from app.routers.recitation import router as recitation_router
from app.routers.progress import router as progress_router 
from app.routers.leaderboard import router as leaderboard_router  
from app.routers.settings import router as settings_router  
from app.routers.voice_router import router as voice_router
from app.routers.community import router as community_router
from app.routers.analytics import router as analytics_router
from app.routers.notification import router as notification_router
from apscheduler.schedulers.background import BackgroundScheduler
from app.tasks.subscription_checker import check_expiring_subscriptions
import logging
from app.models import Surah, Ayah
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
import os

logger = logging.getLogger(__name__)

app = FastAPI(title="Quran Recitation API")

#######=========== DELETE LATER ====================================================================#################################

@app.post("/admin/populate-surahs")
def populate_surahs(admin_key: str, db: Session = Depends(get_db)):
    """Populate database with Quran data - ONE TIME USE"""
    
    # Security check
    if admin_key != os.getenv("ADMIN_SECRET_KEY", "default-secret-key"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Check if already populated
    if db.query(Surah).count() > 0:
        return {"message": "Surahs already exist", "count": db.query(Surah).count()}
    
    import requests
    URL = "https://api.alquran.cloud/v1/quran/quran-uthmani"
    
    response = requests.get(URL)
    data = response.json()["data"]["surahs"]
    
    for surah in data:
        db_surah = Surah(
            number=surah["number"],
            name_ar=surah["name"],
            name_en=surah["englishName"],
            ayah_count=len(surah["ayahs"]),
        )
        db.add(db_surah)
        db.flush()
        
        for ayah in surah["ayahs"]:
            db_ayah = Ayah(
                surah_id=db_surah.id,
                number=ayah["numberInSurah"],
                text=ayah["text"],
            )
            db.add(db_ayah)
    
    db.commit()
    return {"message": f"Successfully populated {len(data)} surahs"}

# ADD THIS TO app/main.py (after the populate_surahs endpoint)

@app.post("/admin/populate-test-data")
def populate_test_data(admin_key: str, db: Session = Depends(get_db)):
    """Populate database with 100 test users + progress data"""
    
    # Move imports OUTSIDE try block
    from app.models import User, UserProgress, UserSettings, SubscriptionStatus
    from app.auth import hash_password
    import random
    
    # Security check
    if admin_key != os.getenv("ADMIN_SECRET_KEY", "default-secret-key"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    try:
        # Check if already populated
        existing_users = db.query(User).filter(User.email.like('%testuser%@quranapi.test')).count()
        if existing_users >= 50:
            return {"message": f"Test data already exists ({existing_users} users)"}
        
        created_count = 0
        
        first_names = [
            "Ahmed", "Ali", "Hassan", "Omar", "Yusuf", "Ibrahim", "Khalid", "Tariq", "Bilal", "Hamza",
            "Fatima", "Aisha", "Khadija", "Zainab", "Maryam", "Hafsa", "Sumaya", "Ruqayyah", "Amina", "Safiya",
            "Abdullah", "Muhammad", "Mustafa", "Idris", "Ismail", "Zakaria", "Sulaiman", "Dawud", "Musa", "Isa",
            "Asma", "Hana", "Layla", "Noor", "Rania", "Salma", "Yasmin", "Zahra", "Bushra", "Leena",
            "Rashid", "Samir", "Karim", "Jamal", "Faisal", "Nasir", "Amin", "Rafiq", "Majid", "Waleed"
        ]
        
        last_names = [
            "Rahman", "Malik", "Hassan", "Ali", "Khan", "Ahmed", "Sheikh", "Noor", "Siddiqui", "Iqbal",
            "Farooq", "Abbas", "Raza", "Hussain", "Shah", "Aziz", "Rashid", "Karim", "Hakim", "Sharif"
        ]
        
        for i in range(100):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            email = f"testuser{i+1}@quranapi.test"
            
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                continue
            
            user = User(
                email=email,
                hashed_password=hash_password("TestPass123!"),
                first_name=first_name,
                last_name=last_name,
                provider="local",
                is_email_verified=True,
                subscription_status=SubscriptionStatus.FREE,
                #profile_image_url=f"https://api.dicebear.com/7.x/initials/svg?seed={first_name}{last_name}"
            )
            db.add(user)
            db.flush()
            
            if i < 20:
                accuracy = random.uniform(90, 99)
                recitations = random.randint(40, 100)
                streak = random.randint(15, 60)
            elif i < 60:
                accuracy = random.uniform(75, 90)
                recitations = random.randint(10, 40)
                streak = random.randint(5, 20)
            else:
                accuracy = random.uniform(60, 75)
                recitations = random.randint(5, 15)
                streak = random.randint(1, 10)
            
            progress = UserProgress(
                user_id=user.id,
                total_recitation_attempts=recitations,
                average_accuracy=round(accuracy, 2),
                total_time_spent_seconds=recitations * random.randint(90, 300),
                current_streak=streak,
                longest_streak=streak + random.randint(0, 10)
            )
            db.add(progress)
            
            settings = UserSettings(
                user_id=user.id,
                show_on_leaderboard=True,
                notifications_enabled=True
            )
            db.add(settings)
            
            created_count += 1
        
        db.commit()
        
        return {
            "message": f"Successfully created {created_count} test users",
            "test_login": "testuser1@quranapi.test / TestPass123!"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    
# ADD THIS TO app/main.py (after populate_test_data endpoint)

@app.delete("/admin/cleanup-test-data")
def cleanup_test_data(admin_key: str, db: Session = Depends(get_db)):
    """
    Delete all test data from database
    Removes users with @quranapi.test or @leaderboard.com or @test.com emails
    """
    
    # Security check
    if admin_key != os.getenv("ADMIN_SECRET_KEY", "default-secret-key"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    from app.models import User
    
    # Find all test users
    test_patterns = ['%@quranapi.test', '%@leaderboard.com', '%@test.com', '%test_%@test.com']
    
    deleted_counts = {}
    total_deleted = 0
    
    for pattern in test_patterns:
        users = db.query(User).filter(User.email.like(pattern)).all()
        count = len(users)
        
        if count > 0:
            # CASCADE delete will automatically delete:
            # - user_progress
            # - user_settings
            # - community_members
            # - notifications
            # - payments
            # - etc.
            for user in users:
                db.delete(user)
            
            deleted_counts[pattern] = count
            total_deleted += count
    
    db.commit()
    
    return {
        "message": f"Successfully deleted {total_deleted} test users",
        "breakdown": deleted_counts,
        "note": "Associated data (progress, settings, etc.) was also deleted via CASCADE"
    }

#######=========== DELETE LATER (ABOVE) ====================================================================#################################

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables
Base.metadata.create_all(bind=engine)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(surah.router, tags=["Surahs"])
app.include_router(google_router, prefix="/auth", tags=["OAuth"])
app.include_router(apple_router, prefix="/auth", tags=["OAuth"])
app.include_router(payment_router, prefix="/payment", tags=["Payment"])
app.include_router(recitation_router, prefix="/recitation", tags=["Recitation"])
app.include_router(progress_router, prefix="/progress", tags=["Progress"]) 
app.include_router(leaderboard_router, prefix="/leaderboard", tags=["Leaderboard"]) 
app.include_router(settings_router, prefix="/user", tags=["Settings"])  
app.include_router(voice_router, prefix="/voice", tags=["Voice"])
app.include_router(community_router, prefix="/community", tags=["Community"])
app.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
app.include_router(notification_router, prefix="/notifications", tags=["Notifications"])

@app.on_event("startup")
def start_scheduler():
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        check_expiring_subscriptions,
        trigger="interval",
        hours=1,
        id="subscription_checker",
        name="Check expiring subscriptions"
    )
    
    scheduler.start()
    logger.info("Scheduler started - checking subscriptions every hour")


@app.get("/")
def read_root():
    return {"message": "Quran Recitation API - Premium audio recitations for Quran study"}

@app.get("/health")
def health_check():
    """Health check endpoint"""
    import os
    
    return {
        "status": "healthy",
        "version": "2.0",
        "services": {
            "database": "connected",
            "openai_whisper": "configured" if os.getenv("OPENAI_API_KEY") else "not_configured",
            "stripe": "configured" if os.getenv("STRIPE_SECRET_KEY") else "not_configured"
        }
    }