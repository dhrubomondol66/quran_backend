from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas

router = APIRouter()

@router.get("/surahs", response_model=list[schemas.SurahOut])
def get_surahs(db: Session = Depends(get_db)):
    return crud.get_all_surahs(db)

@router.get("/surahs/{surah_id}", response_model=schemas.SurahDetailOut)
def get_surah(surah_id: int, db: Session = Depends(get_db)):
    surah = crud.get_surah_by_id(db, surah_id)
    if not surah:
        raise HTTPException(status_code=404, detail="Surah not found")
    return surah
