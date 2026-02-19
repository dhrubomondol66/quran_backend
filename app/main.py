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

# ADD THIS TO app/main.py

@app.delete("/admin/nuclear-cleanup")
def nuclear_cleanup(admin_key: str, confirm: str, db: Session = Depends(get_db)):
    """
    Delete ALL users and related data (keeps surahs/ayahs)
    Requires confirm=DELETE_EVERYTHING for safety
    """
    
    if admin_key != os.getenv("ADMIN_SECRET_KEY", "default-secret-key"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    if confirm != "DELETE_EVERYTHING":
        raise HTTPException(status_code=400, detail="Must pass confirm=DELETE_EVERYTHING")
    
    from app.models import User, UserProgress, UserSettings, CommunityMember, Notification, DeviceToken, Community, CommunityInvitation, Payment, UserActivity
    
    try:
        # Delete everything user-related (bottom-up to avoid foreign key issues)
        db.query(DeviceToken).delete()
        db.query(Notification).delete()
        db.query(UserActivity).delete()
        db.query(Payment).delete()
        db.query(CommunityInvitation).delete()
        db.query(CommunityMember).delete()
        db.query(Community).delete()
        db.query(UserSettings).delete()
        db.query(UserProgress).delete()
        db.query(User).delete()
        
        db.commit()
        
        return {
            "message": "Successfully deleted ALL users and related data",
            "kept": "Surahs and Ayahs preserved"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# ADD THIS TO app/main.py

@app.post("/admin/test-email")
def test_email(admin_key: str, to_email: str, db: Session = Depends(get_db)):
    """Test email sending"""
    
    if admin_key != os.getenv("ADMIN_SECRET_KEY", "default-secret-key"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    from app.email_utils import send_email_sync
    
    html = "<h1>Test Email</h1><p>If you see this, email is working!</p>"
    
    try:
        result = send_email_sync(to_email, "Test Email from Quran API", html)
        return {
            "success": result,
            "sendgrid_configured": bool(os.getenv("SENDGRID_API_KEY")),
            "gmail_configured": bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
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