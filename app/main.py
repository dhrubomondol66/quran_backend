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

app = FastAPI(title="Quran Recitation API")

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

@app.get("/")
def read_root():
    return {"message": "Quran Recitation API - Premium audio recitations for Quran study"}

# ✅ ADD THIS HEALTH ENDPOINT
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