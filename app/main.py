from fastapi import FastAPI
from app.database import Base, engine
from app import models
from app.routers import auth, surah
from app.routers.google import router as google_router
from app.routers.apple import router as apple_router 
app = FastAPI(title="Quran API")


Base.metadata.create_all(bind=engine)


app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(surah.router, tags=["Surahs"])
app.include_router(google_router, prefix="/auth", tags=["OAuth"])
app.include_router(apple_router, prefix="/auth", tags=["OAuth"])  