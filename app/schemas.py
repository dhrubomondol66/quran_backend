from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

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
    first_name: Optional[str] = None
    last_name: Optional[str] = None   

class UserOut(BaseModel):
    id: int
    email: EmailStr
    provider: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    profile_image_url: Optional[str] = None  # Add this
    subscription_status: str  
    subscription_plan: Optional[str] = None  
    subscription_end_date: Optional[datetime] = None  
    is_email_verified: bool  
    
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

class AppleLogin(BaseModel):
    id_token: str
    user: Optional[dict] = None

# Payment Schemas
class CreateCheckoutSession(BaseModel):
    plan_type: str  # "monthly", "yearly", or "lifetime"
    success_url: str
    cancel_url: str

class PaymentIntentCreate(BaseModel):
    amount: int  # Amount in cents
    plan_type: str

class SubscriptionOut(BaseModel):
    subscription_status: str
    subscription_plan: Optional[str]
    subscription_end_date: Optional[datetime]
    days_remaining: Optional[int] = None
    
    class Config:
        from_attributes = True

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "abc123xyz...",
                "new_password": "NewSecurePassword123!"
            }
        }