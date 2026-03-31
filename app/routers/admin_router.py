from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
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
import secrets
import string


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
    user_growth: List[dict]
    revenue_growth: List[dict]


@router.get("/dashboard", response_model=DashboardStats)
def get_admin_dashboard(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin dashboard overview.
    Returns stats for total users, premium/free split, revenue, and growth trends.
    """

    total_users = db.query(User).filter(~User.email.in_(ADMIN_EMAILS)).count()

    premium_users = db.query(User).filter(
        User.subscription_status.in_([SubscriptionStatus.ACTIVE]),
        ~User.email.in_(ADMIN_EMAILS)
    ).count()
    free_users = total_users - premium_users

    total_revenue_result = db.query(func.sum(Payment.amount)).filter(
        Payment.status == "succeeded"
    ).scalar()
    total_revenue = float(total_revenue_result or 0) / 100

    now = datetime.utcnow()
    last_7_days = now - timedelta(days=7)
    previous_7_days = now - timedelta(days=14)

    last_week_revenue = db.query(func.sum(Payment.amount)).filter(
        and_(Payment.status == "succeeded", Payment.created_at >= last_7_days)
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

    user_growth = []
    for i in range(7):
        day_start = (now - timedelta(days=6 - i)).replace(hour=0, minute=0, second=0)
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
            "day": day_start.strftime("%a"),
            "free": free_count,
            "premium": premium_count,
            "date": day_start.strftime("%Y-%m-%d")
        })

    revenue_growth = []
    for i in range(7):
        day_start = (now - timedelta(days=6 - i)).replace(hour=0, minute=0, second=0)
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
    plan: str
    joined: str
    subscription_status: str
    is_suspended: bool


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
    Get all users with pagination and search.
    Admins can view all users, filter by plan, and search by name/email.
    """

    query = db.query(User).filter(~User.email.in_(ADMIN_EMAILS))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.email.ilike(search_term),
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term)
            )
        )

    if plan:
        if plan.lower() == "premium":
            query = query.filter(User.subscription_status.in_([SubscriptionStatus.ACTIVE]))
        elif plan.lower() == "basic":
            query = query.filter(User.subscription_status == SubscriptionStatus.FREE)

    total = query.count()
    offset = (page - 1) * per_page
    users = query.order_by(desc(User.created_at)).offset(offset).limit(per_page).all()

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
            subscription_status=user.subscription_status.value,
            is_suspended=user.is_suspended
        ))

    total_pages = (total + per_page - 1) // per_page

    return {
        "users": user_list,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }


@router.post("/users/{user_id}/suspend")
def suspend_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Suspend a user account"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.email in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Cannot suspend an admin account")
    
    user.is_suspended = True
    db.commit()
    return {"message": f"User {user.email} has been suspended"}


@router.post("/users/{user_id}/activate")
def activate_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Activate a suspended user account"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_suspended = False
    db.commit()
    return {"message": f"User {user.email} has been activated"}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Hard delete a user and all their data"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.email in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Cannot delete an admin account")
    
    # Deletion in models with cascade="all, delete-orphan" should handle most things
    # But we can be explicit if needed. The User model has several relationships.
    db.delete(user)
    db.commit()
    return {"message": f"User {user.email} and all associated data deleted"}


# ============================================================================
# ADMIN PROFILE ENDPOINTS
# ============================================================================

class AdminProfile(BaseModel):
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
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
    """Get both admin profiles — Super Admin and Sub Admin."""

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
    """Update current admin's profile. Admins can only update their own profile."""

    from app.auth import verify_password, hash_password

    if updates.first_name is not None:
        admin.first_name = updates.first_name
    if updates.last_name is not None:
        admin.last_name = updates.last_name

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
    Delete ALL users and related data (keeps surahs/ayahs).
    Only callable by authenticated admin.
    """
    if confirm != "DELETE_EVERYTHING":
        raise HTTPException(status_code=400, detail="Must pass confirm=DELETE_EVERYTHING")

    from app.models import (
        User as UserModel, UserProgress, UserSettings, CommunityMember,
        Notification, DeviceToken, Community, CommunityInvitation, Payment, UserActivity
    )

    try:
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

    html = "<h1>Admin Test Email</h1><p>If you see this, the admin email utility is working!</p>"

    try:
        result = send_email_sync(to_email, "Admin Utility: Test Email", html)
        return {
            "success": result,
            "sendgrid_configured": bool(os.getenv("SENDGRID_API_KEY")),
            "gmail_configured": bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# ADMIN AUTH — LOGIN / LOGOUT
# ============================================================================

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


@router.post("/admin-logout")
def admin_logout(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin logout"""
    return {"message": "Admin logout successful"}


# ============================================================================
# ADMIN PASSWORD RESET
# ============================================================================
#
# IMPORTANT — you already have these two columns in your User model:
#
#   password_reset_token        = Column(String, nullable=True)
#   password_reset_expires = Column(DateTime, nullable=True)
#   alembic upgrade head
#
# Also set this env var on Render:
#   BACKEND_URL = https://quran-api-admin.vercel.app/
# ============================================================================

def _generate_reset_token(length: int = 64) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/admin-forgot-password")
def forgot_password(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Send a password-reset email to the admin.
    Always returns 200 to prevent email enumeration.
    """
    db_user = crud.get_user_by_email(db, email)

    if not db_user or db_user.email not in ADMIN_EMAILS:
        return {"message": "If that email belongs to an admin, a reset link has been sent."}

    # ✅ Store token in DB — survives Render restarts
    token = _generate_reset_token()
    db_user.password_reset_token = token
    db_user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    frontend_url = os.getenv("FRONTEND_URL", "https://quran-api-admin.vercel.app")
    reset_link = f"{frontend_url}/reset-password?token={token}"

    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:auto">
      <h2 style="color:#1a2a1e">Qari Admin — Password Reset</h2>
      <p>Hi {db_user.first_name or 'Admin'},</p>
      <p>We received a request to reset your admin password.
         Click the button below — the link expires in <strong>1 hour</strong>.</p>
      <a href="{reset_link}"
         style="display:inline-block;padding:12px 28px;background:#1a2a1e;
                color:#c9a84c;border-radius:8px;text-decoration:none;
                font-weight:600;margin:16px 0">
        Reset Password
      </a>
      <p style="color:#666;font-size:13px">
        Or copy this link:<br>
        <a href="{reset_link}" style="color:#1a2a1e">{reset_link}</a>
      </p>
      <p style="color:#999;font-size:12px">
        If you didn't request this, you can safely ignore this email.
      </p>
    </div>
    """

    from app.email_utils import send_email_sync
    try:
        send_email_sync(db_user.email, "Qari Admin — Password Reset", html)
    except Exception as e:
        print(f"[ERROR] Failed to send reset email to {db_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send reset email. Check server email config.")

    return {"message": "If that email belongs to an admin, a reset link has been sent."}


@router.get("/reset-password")
def reset_password_page(token: str, db: Session = Depends(get_db)):
    """
    ✅ GET route — browser hits this when admin clicks the email link.
    Validates the token and serves an HTML password reset form.
    """
    db_user = db.query(User).filter(
        User.password_reset_token == token,
        User.password_reset_expires > datetime.utcnow()
    ).first()

    if not db_user:
        return HTMLResponse(status_code=400, content="""
        <!DOCTYPE html>
        <html>
        <head><title>Invalid Link</title></head>
        <body style="font-family:'Segoe UI',sans-serif;text-align:center;padding:80px;background:#f0f2f0">
            <div style="background:white;padding:40px;border-radius:16px;
                        max-width:420px;margin:auto;box-shadow:0 4px 24px rgba(0,0,0,0.1)">
                <h2 style="color:#c0392b">❌ Invalid or Expired Link</h2>
                <p style="color:#666;margin-top:12px">
                    This reset link is invalid or has already been used.<br>
                    Please request a new password reset from the admin panel.
                </p>
            </div>
        </body>
        </html>""")

    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reset Admin Password — Qari</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                font-family: 'Segoe UI', sans-serif;
                background: #f0f2f0;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
            }}
            .card {{
                background: white;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.1);
                width: 100%;
                max-width: 420px;
            }}
            h2 {{ color: #1a2a1e; margin-bottom: 8px; }}
            .subtitle {{ color: #666; font-size: 14px; margin-bottom: 28px; }}
            label {{
                display: block;
                font-size: 13px;
                font-weight: 600;
                color: #333;
                margin-bottom: 6px;
            }}
            input {{
                width: 100%;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 15px;
                margin-bottom: 16px;
                outline: none;
                transition: border-color 0.2s;
            }}
            input:focus {{ border-color: #1a2a1e; }}
            input:disabled {{ background: #f5f5f5; }}
            button {{
                width: 100%;
                padding: 13px;
                background: #1a2a1e;
                color: #c9a84c;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.2s;
            }}
            button:hover:not(:disabled) {{ background: #2d4a33; }}
            button:disabled {{ background: #999; cursor: not-allowed; }}
            #msg {{ margin-top: 16px; font-size: 14px; text-align: center; min-height: 20px; }}
            .error {{ color: #c0392b; }}
            .success {{ color: #27ae60; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🔐 Reset Password</h2>
            <p class="subtitle">Enter your new admin password below.</p>

            <label>New Password</label>
            <input type="password" id="password" placeholder="At least 8 characters" />

            <label>Confirm Password</label>
            <input type="password" id="confirm" placeholder="Repeat your password" />

            <button id="btn" onclick="submitReset()">Reset Password</button>
            <div id="msg"></div>
        </div>

        <script>
            async function submitReset() {{
                const password = document.getElementById('password').value;
                const confirm  = document.getElementById('confirm').value;
                const msg = document.getElementById('msg');
                const btn = document.getElementById('btn');

                msg.className = 'error';

                if (!password || !confirm) {{
                    msg.innerText = 'Please fill in both fields.';
                    return;
                }}
                if (password !== confirm) {{
                    msg.innerText = 'Passwords do not match.';
                    return;
                }}
                if (password.length < 8) {{
                    msg.innerText = 'Password must be at least 8 characters.';
                    return;
                }}

                btn.disabled = true;
                btn.innerText = 'Resetting...';
                msg.innerText = '';

                try {{
                    const res = await fetch('/admin/admin-reset-password', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            token: '{token}',
                            password: password,
                            confirm_password: confirm
                        }})
                    }});

                    const data = await res.json();

                    if (res.ok) {{
                        msg.className = 'success';
                        msg.innerText = '✅ ' + data.message;
                        document.getElementById('password').disabled = true;
                        document.getElementById('confirm').disabled = true;
                        btn.style.display = 'none';
                    }} else {{
                        msg.innerText = data.detail || 'Something went wrong.';
                        btn.disabled = false;
                        btn.innerText = 'Reset Password';
                    }}
                }} catch (e) {{
                    msg.innerText = 'Network error. Please try again.';
                    btn.disabled = false;
                    btn.innerText = 'Reset Password';
                }}
            }}
        </script>
    </body>
    </html>""")


class ResetPasswordRequest(BaseModel):
    token: str
    password: str
    confirm_password: str


@router.post("/admin-reset-password")
def reset_password(
    token: str,
    password: str,
    confirm_password: str,
    db: Session = Depends(get_db)
):
    """Reset password for admin using the token from forgot-password"""
    from app.auth import hash_password
    
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Find user by token
    db_user = db.query(User).filter(
        User.password_reset_token == token,
        User.password_reset_expires > datetime.utcnow()
    ).first()
    
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
        
    # Update password
    db_user.hashed_password = hash_password(password)
    db_user.password_reset_token = None
    db_user.password_reset_expires = None
    db.commit()
    
    return {
        "message": "Password reset successful",
        "admin": schemas.UserOut.from_orm(db_user)
    }


# ============================================================================
# ADMIN INITIALIZATION (Run once to create admin users)
# ============================================================================

@router.get("/admin-username")
def get_admin_username(admin: User = Depends(require_admin)):
    """Return the email of the currently logged-in admin"""
    return {
        "admin_username": admin.email
    }



@router.post("/init-admins")
def initialize_admins(
    secret_key: str = Query(..., description="Admin initialization secret key"),
    db: Session = Depends(get_db)
):
    """
    ONE-TIME SETUP: Create the two admin accounts.
    Requires ADMIN_INIT_SECRET from environment variables.
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