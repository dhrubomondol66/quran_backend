from pydantic import BaseModel, EmailStr
from typing import List


class AyahOut(BaseModel):
    id: int
    number: int     
    text: str

    class Config:
        from_attributes = True


class SurahOut(BaseModel):
    id: int
    number: int
    name_ar: str
    name_en: str
    ayah_count: int

    class Config:
        from_attributes = True


class SurahDetailOut(SurahOut):
    ayahs: List[AyahOut]


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleLogin(BaseModel):
    id_token: str
