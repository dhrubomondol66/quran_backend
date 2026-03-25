from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, timedelta
from app.database import get_db
from app.deps import get_current_user
from app.models import User, Payment, SubscriptionStatus
from typing import Optional, List
from pydantic import BaseModel
from app.config import ADMIN_INIT_SECRET, ADMIN_EMAILS
from app import auth, schemas, crud
import os

router = APIRouter()
def exclude_admins_filter(query, model=User):
    """Filter to exclude admin users from queries"""
    return query.filter(~model.email.in_(ADMIN_EMAILS))

def is_admin(user: User) -> bool:
    """Check if user is an admin"""
    return user.email in ADMIN_EMAILS

def require_admin(current_user: User = Depends(get_current_user)):
    """Dependency to require admin access"""
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ============================================================================
# DASHBOARD ENDPOINT
# ============================================================================

class DashboardStats(BaseModel):
    total_users: int
    premium_users: int
    free_users: int
    total_revenue: float
    revenue_change_percent: float
    user_growth: List[dict]  # Last 7 days growth data
    revenue_growth: List[dict]  # Last 7 days revenue data


@router.get("/dashboard", response_model=DashboardStats)
def get_admin_dashboard(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin dashboard overview
    Returns stats for total users, premium/free split, revenue, and growth trends
    """
    
    # Total users (excluding admins)
    total_users = db.query(User).filter(~User.email.in_(ADMIN_EMAILS)).count()
    
    # Premium vs Free users (excluding admins)
    premium_users = db.query(User).filter(
        User.subscription_status.in_([SubscriptionStatus.ACTIVE]),
        ~User.email.in_(ADMIN_EMAILS)
    ).count()
    free_users = total_users - premium_users
    
    # Total revenue (sum of all successful payments)
    total_revenue_result = db.query(func.sum(Payment.amount)).filter(
        Payment.status == "succeeded"
    ).scalar()
    total_revenue = float(total_revenue_result or 0) / 100  # Convert cents to dollars
    
    # Revenue change (last 7 days vs previous 7 days)
    now = datetime.utcnow()
    last_7_days = now - timedelta(days=7)
    previous_7_days = now - timedelta(days=14)
    
    last_week_revenue = db.query(func.sum(Payment.amount)).filter(
        and_(
            Payment.status == "succeeded",
            Payment.created_at >= last_7_days
        )
    ).scalar()
    last_week_revenue = float(last_week_revenue or 0) / 100
    
    prev_week_revenue = db.query(func.sum(Payment.amount)).filter(
        and_(
            Payment.status == "succeeded",
            Payment.created_at >= previous_7_days,
            Payment.created_at < last_7_days
        )
    ).scalar()
    prev_week_revenue = float(prev_week_revenue or 0) / 100
    
    revenue_change = 0
    if prev_week_revenue > 0:
        revenue_change = ((last_week_revenue - prev_week_revenue) / prev_week_revenue) * 100
    
    # User growth - last 7 days
    user_growth = []
    for i in range(7):
        day_start = (now - timedelta(days=6-i)).replace(hour=0, minute=0, second=0)
        day_end = day_start + timedelta(days=1)
        
        free_count = db.query(User).filter(
            and_(
                User.created_at >= day_start,
                User.created_at < day_end,
                User.subscription_status == SubscriptionStatus.FREE,
                ~User.email.in_(ADMIN_EMAILS)
            )
        ).count()
        
        premium_count = db.query(User).filter(
            and_(
                User.created_at >= day_start,
                User.created_at < day_end,
                User.subscription_status.in_([SubscriptionStatus.ACTIVE]),
                ~User.email.in_(ADMIN_EMAILS)
            )
        ).count()
        
        user_growth.append({
            "day": day_start.strftime("%a"),  # Mon, Tue, Wed...
            "free": free_count,
            "premium": premium_count,
            "date": day_start.strftime("%Y-%m-%d")
        })
    
    # Revenue growth - last 7 days
    revenue_growth = []
    for i in range(7):
        day_start = (now - timedelta(days=6-i)).replace(hour=0, minute=0, second=0)
        day_end = day_start + timedelta(days=1)
        
        day_revenue = db.query(func.sum(Payment.amount)).filter(
            and_(
                Payment.status == "succeeded",
                Payment.created_at >= day_start,
                Payment.created_at < day_end
            )
        ).scalar()
        day_revenue = float(day_revenue or 0) / 100
        
        revenue_growth.append({
            "day": day_start.strftime("%a"),
            "revenue": round(day_revenue, 2),
            "date": day_start.strftime("%Y-%m-%d")
        })
    
    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "free_users": free_users,
        "total_revenue": round(total_revenue, 2),
        "revenue_change_percent": round(revenue_change, 1),
        "user_growth": user_growth,
        "revenue_growth": revenue_growth
    }


# ============================================================================
# USER MANAGEMENT ENDPOINT
# ============================================================================

class UserListItem(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    plan: str  # "Premium" or "Basic"
    joined: str  # Date joined
    subscription_status: str


class UserManagementResponse(BaseModel):
    users: List[UserListItem]
    total: int
    page: int
    per_page: int
    total_pages: int


@router.get("/users", response_model=UserManagementResponse)
def get_all_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by name or email"),
    plan: Optional[str] = Query(None, description="Filter by plan: 'premium' or 'basic'"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100)
):
    """
    Get all users with pagination and search
    Admins can view all users, filter by plan, and search by name/email
    """
    
    # Base query (excluding admins)
    query = db.query(User).filter(~User.email.in_(ADMIN_EMAILS))
    
    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.email.ilike(search_term),
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term)
            )
        )
    
    # Plan filter
    if plan:
        if plan.lower() == "premium":
            query = query.filter(
                User.subscription_status.in_([SubscriptionStatus.ACTIVE])
            )
        elif plan.lower() == "basic":
            query = query.filter(User.subscription_status == SubscriptionStatus.FREE)
    
    # Get total count
    total = query.count()
    
    # Pagination
    offset = (page - 1) * per_page
    users = query.order_by(desc(User.created_at)).offset(offset).limit(per_page).all()
    
    # Format response
    user_list = []
    for user in users:
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split("@")[0]
        plan_status = "Premium" if user.subscription_status in [SubscriptionStatus.ACTIVE] else "Basic"
        
        user_list.append(UserListItem(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=full_name,
            plan=plan_status,
            joined=user.created_at.strftime("%Y-%m-%d"),
            subscription_status=user.subscription_status.value
        ))
    
    total_pages = (total + per_page - 1) // per_page
    
    return {
        "users": user_list,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }


# ============================================================================
# ADMIN PROFILE ENDPOINTS
# ============================================================================

class AdminProfile(BaseModel):
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str  # "Super Admin" or "Sub Admin"
    is_current_user: bool


class UpdateAdminProfile(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


@router.get("/profile/admins")
def get_all_admin_profiles(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get both admin profiles
    Shows Super Admin and Sub Admin details
    """
    
    admins = db.query(User).filter(User.email.in_(ADMIN_EMAILS)).all()
    
    profiles = []
    for admin_user in admins:
        role = "Super Admin" if admin_user.email == ADMIN_EMAILS[0] else "Sub Admin"
        profiles.append(AdminProfile(
            email=admin_user.email,
            first_name=admin_user.first_name,
            last_name=admin_user.last_name,
            role=role,
            is_current_user=(admin_user.id == admin.id)
        ))
    
    return {"admins": profiles}


@router.put("/profile/update")
def update_admin_profile(
    updates: UpdateAdminProfile,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update current admin's profile
    Admins can only update their own profile
    """
    
    from app.auth import verify_password, hash_password
    
    # Update name
    if updates.first_name is not None:
        admin.first_name = updates.first_name
    if updates.last_name is not None:
        admin.last_name = updates.last_name
    
    # Update password if provided
    if updates.current_password and updates.new_password:
        if not verify_password(updates.current_password, admin.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        admin.hashed_password = hash_password(updates.new_password)
    
    db.commit()
    db.refresh(admin)
    
    return {
        "message": "Profile updated successfully",
        "admin": {
            "email": admin.email,
            "first_name": admin.first_name,
            "last_name": admin.last_name
        }
    }


# ============================================================================
# DATA UTILITIES
# ============================================================================

@router.post("/populate-surahs")
def populate_surahs(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Populate database with Quran data - ONE TIME USE"""
    from app.models import Surah, Ayah
    
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


@router.delete("/nuclear-cleanup")
def nuclear_cleanup(
    confirm: str = Query(..., description="Must be 'DELETE_EVERYTHING'"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete ALL users and related data (keeps surahs/ayahs)
    Only callable by authenticated admin
    """
    if confirm != "DELETE_EVERYTHING":
        raise HTTPException(status_code=400, detail="Must pass confirm=DELETE_EVERYTHING")
    
    from app.models import User as UserModel, UserProgress, UserSettings, CommunityMember, Notification, DeviceToken, Community, CommunityInvitation, Payment, UserActivity
    
    try:
        # Delete everything user-related (bottom-up)
        db.query(DeviceToken).delete()
        db.query(Notification).delete()
        db.query(UserActivity).delete()
        db.query(Payment).delete()
        db.query(CommunityInvitation).delete()
        db.query(CommunityMember).delete()
        db.query(Community).delete()
        db.query(UserSettings).delete()
        db.query(UserProgress).delete()
        db.query(UserModel).delete()
        
        db.commit()
        
        return {
            "message": "Successfully deleted ALL users and related data",
            "kept": "Surahs and Ayahs preserved"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/test-email")
def test_email(
    to_email: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Test email sending functionality"""
    from app.email_utils import send_email_sync
    import os
    
    html = "<h1>Admin Test Email</h1><p>If you see this, the admin email utility is working!</p>"
    
    try:
        result = send_email_sync(to_email, "Admin Utility: Test Email", html)
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

@router.post("/admin-login")
def admin_login(
    login_data: schemas.UserLogin,
    db: Session = Depends(get_db)
):
    """Admin login with email and password"""
    db_user = crud.get_user_by_email(db, login_data.email)
    
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not auth.verify_password(login_data.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if db_user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")
        
    token = auth.create_access_token(data={"sub": str(db_user.id)})
    
    return {
        "message": "Admin login successful",
        "admin": schemas.UserOut.from_orm(db_user),
        "token": token
    }

@router.post("/admin-forgot-password")
def forgot_password(
    email: str,
    db: Session = Depends(get_db)
):
    """Forgot password for admin"""
    db_user = crud.get_user_by_email(db, email)
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if db_user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # For security, we should probably generate a shorter-lived token specifically for password reset
    # but for now we'll use the current implementation style
    token = auth.create_access_token(data={"sub": str(db_user.id)})
    
    return {
        "message": "Forgot password successful",
        "admin": schemas.UserOut.from_orm(db_user),
        "token": token
    }

@router.post("/admin-reset-password")
def reset_password(
    token: str,
    password: str,
    db: Session = Depends(get_db)
):
    """Reset password for admin using the token from forgot-password"""
    from jose import jwt, JWTError
    from app.config import SECRET_KEY
    from app.auth import ALGORITHM, hash_password
    
    try:
        # Decode the token to get the user ID
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
        
    # Find user by ID
    db_user = db.query(User).filter(User.id == user_id).first()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if they are an admin
    if not is_admin(db_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Update password
    db_user.hashed_password = hash_password(password)
    db.commit()
    
    return {
        "message": "Password reset successful",
        "admin": schemas.UserOut.from_orm(db_user)
    }

@router.post("/admin-logout")
def admin_logout(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin logout"""
    return {
        "message": "Admin logout successful"
    }

# ============================================================================
# ADMIN INITIALIZATION (Run once to create admin users)
# ============================================================================

@router.post("/init-admins")
def initialize_admins(
    secret_key: str = Query(..., description="Admin initialization secret key"),
    db: Session = Depends(get_db)
):
    """
    ONE-TIME SETUP: Create the two admin accounts
    Requires ADMIN_INIT_SECRET from environment variables
    """
    
    if secret_key != ADMIN_INIT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid initialization key")
    
    from app.auth import hash_password
    from app.config import ADMIN_DEFAULT_PASSWORD
    
    admins_created = []
    
    for email in ADMIN_EMAILS:
        if not db.query(User).filter(User.email == email).first():
            user = User(
                email=email,
                hashed_password=hash_password(ADMIN_DEFAULT_PASSWORD),
                provider="local",
                is_email_verified=True,
                subscription_status=SubscriptionStatus.ACTIVE
            )
            # Set names based on index or email
            if email == ADMIN_EMAILS[0]:
                user.first_name = "Michael"
                user.last_name = "Totok"
            elif len(ADMIN_EMAILS) > 1 and email == ADMIN_EMAILS[1]:
                user.first_name = "Dhrubo"
                user.last_name = "Mondol"
            
            db.add(user)
            admins_created.append(f"Admin {email} created")
    
    if admins_created:
        db.commit()
        return {
            "message": "Admin accounts initialized",
            "admins": admins_created,
            "warning": "⚠️ CHANGE DEFAULT PASSWORDS IMMEDIATELY via /admin/profile/update"
        }
    else:
        return {"message": "Admin accounts already exist"}
