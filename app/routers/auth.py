from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas, crud, auth
from app.email_utils import send_email, get_verification_email_template, get_welcome_email_template
from google.oauth2 import id_token
from google.auth.transport.requests import Request
import os

router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

@router.post("/register", response_model=schemas.UserOut)
async def register(
    user: schemas.UserCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Register new user and send verification email"""
    
    # Check if user already exists
    if crud.get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user (unverified)
    db_user = crud.create_user(db, user.email, user.password)
    
    # Send verification email in background
    verification_link = f"{FRONTEND_URL}/verify-email?token={db_user.email_verification_token}"
    html_content = get_verification_email_template(verification_link, user.email)
    
    background_tasks.add_task(
        send_email,
        to_email=user.email,
        subject="Verify Your Email - Quran Recitation App",
        html_content=html_content
    )
    
    return db_user

@router.get("/verify-email", response_class=HTMLResponse)
@router.post("/verify-email")
async def verify_email(
    token: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Verify user's email with token (supports both GET and POST)"""
    
    user = crud.verify_user_email(db, token)
    
    if not user:
        # Return HTML error page for browser
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Verification Failed</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    text-align: center;
                    max-width: 500px;
                }
                h1 { color: #d32f2f; }
                p { color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ Verification Failed</h1>
                <p>Invalid or expired verification token.</p>
                <p>Please try registering again or request a new verification email.</p>
            </div>
        </body>
        </html>
        """, status_code=400)
    
    # Send welcome email in background
    user_name = user.first_name or user.email.split('@')[0]
    welcome_html = get_welcome_email_template(user_name)
    
    background_tasks.add_task(
        send_email,
        to_email=user.email,
        subject="Welcome to Quran Recitation App! 🌙",
        html_content=welcome_html
    )
    
    # Return success HTML page
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Email Verified!</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 10px;
                text-align: center;
                max-width: 500px;
            }}
            h1 {{ color: #4caf50; }}
            p {{ color: #666; margin: 10px 0; }}
            .button {{
                display: inline-block;
                margin-top: 20px;
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ Email Verified Successfully!</h1>
            <p>Welcome, <strong>{user_name}</strong>!</p>
            <p>Your email <strong>{user.email}</strong> has been verified.</p>
            <p>You can now login to your account.</p>
            <a href="#" class="button">Go to Login</a>
        </div>
    </body>
    </html>
    """)

@router.post("/resend-verification")
async def resend_verification(
    email: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Resend verification email"""
    
    user = crud.get_user_by_email(db, email)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    
    # Generate new token
    import secrets
    from datetime import datetime, timedelta
    
    user.email_verification_token = secrets.token_urlsafe(32)
    user.verification_token_expires = datetime.utcnow() + timedelta(hours=24)
    db.commit()
    
    # Send email
    verification_link = f"{FRONTEND_URL}/verify-email?token={user.email_verification_token}"
    html_content = get_verification_email_template(verification_link, email)
    
    background_tasks.add_task(
        send_email,
        to_email=email,
        subject="Verify Your Email - Quran Recitation App",
        html_content=html_content
    )
    
    return {"message": "Verification email resent successfully"}

@router.post("/login", response_model=schemas.Token)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    """Login with email and password"""
    
    db_user = crud.get_user_by_email(db, user.email)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not auth.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # ✅ Check if email is verified
    if not db_user.is_email_verified:
        raise HTTPException(
            status_code=403, 
            detail="Email not verified. Please check your email for verification link."
        )
    
    token = auth.create_access_token(
        data={"sub": str(db_user.id)}
    )
    
    return {
        "access_token": token,
        "token_type": "bearer"
    }