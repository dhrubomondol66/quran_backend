from fastapi import FastAPI
from app.database import Base, engine
from app import models
from app.routers import auth, surah

app = FastAPI(title="Quran API")

# Create tables (users, surahs, ayahs)
Base.metadata.create_all(bind=engine)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(surah.router, tags=["Surahs"])






