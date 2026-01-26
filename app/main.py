from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app import models
from app.routers import auth, surah
from app.routers.google import router as google_router
from app.routers.apple import router as apple_router
from app.routers.payment import router as payment_router
from app.routers.recitation import router as recitation_router

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
app.include_router(recitation_router, prefix="/recitation", tags=["Recitation"])  # ✅ Add this

@app.get("/")
def read_root():
    return {"message": "Quran Recitation API - Premium audio recitations for Quran study"}