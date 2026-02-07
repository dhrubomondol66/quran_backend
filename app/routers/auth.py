from fastapi import APIRouter, Depends, HTTPException, Body, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas, crud, auth
from app.email_utils import send_email, get_verification_email_template, get_welcome_email_template, get_password_reset_email_template, get_password_changed_email_template
from google.oauth2 import id_token
from fastapi.security import OAuth2PasswordRequestForm
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

@router.post("/token", response_model=schemas.Token)
def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2 password flow token endpoint for Swagger UI.
    Swagger sends: username/password as form-urlencoded.
    We'll treat username as email.
    """
    db_user = crud.get_user_by_email(db, form_data.username)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not auth.verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not db_user.is_email_verified:
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Please check your email for verification link.",
        )

    access_token = auth.create_access_token({"sub": str(db_user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/forgot-password")
async def forgot_password(
    request: schemas.PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Request password reset - sends email with reset link"""
    
    # Always return success to prevent email enumeration
    # (Don't reveal if email exists or not for security)
    
    user = crud.create_password_reset_token(db, request.email)
    
    if user:
        # Send password reset email
        reset_link = f"{FRONTEND_URL}/reset-password?token={user.password_reset_token}"
        html_content = get_password_reset_email_template(reset_link, request.email)
        
        background_tasks.add_task(
            send_email,
            to_email=request.email,
            subject="Reset Your Password - Quran Recitation App",
            html_content=html_content
        )
    
    # Always return success message (security best practice)
    return {
        "message": "If that email address is in our system, we've sent a password reset link to it."
    }

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(token: str, db: Session = Depends(get_db)):
    """Show password reset form (GET request from email link)"""
    
    # Verify token is valid
    user = crud.get_user_by_reset_token(db, token)
    
    if not user:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Invalid Reset Link</title>
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
                .button {
                    display: inline-block;
                    margin-top: 20px;
                    padding: 15px 30px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ Invalid or Expired Reset Link</h1>
                <p>This password reset link is invalid or has expired.</p>
                <p>Password reset links are only valid for 1 hour.</p>
                <a href="#" class="button">Request New Reset Link</a>
            </div>
        </body>
        </html>
        """, status_code=400)
    
    # Show password reset form
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reset Password</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 10px;
                max-width: 500px;
                width: 100%;
            }}
            h1 {{ color: #333; text-align: center; }}
            .form-group {{
                margin: 20px 0;
            }}
            label {{
                display: block;
                margin-bottom: 5px;
                color: #666;
                font-weight: bold;
            }}
            input {{
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 5px;
                font-size: 16px;
                box-sizing: border-box;
            }}
            input:focus {{
                outline: none;
                border-color: #667eea;
            }}
            button {{
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                margin-top: 10px;
            }}
            button:hover {{
                opacity: 0.9;
            }}
            .message {{
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                display: none;
            }}
            .success {{
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }}
            .error {{
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }}
            .requirements {{
                background: #e3f2fd;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                font-size: 14px;
            }}
            .requirements ul {{
                margin: 10px 0;
                padding-left: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 Reset Your Password</h1>
            <p style="text-align: center; color: #666;">Enter your new password below</p>
            
            <div id="message" class="message"></div>
            
            <form id="resetForm">
                <div class="requirements">
                    <strong>Password Requirements:</strong>
                    <ul>
                        <li>At least 8 characters long</li>
                        <li>Contains at least one letter and one number</li>
                    </ul>
                </div>
                
                <div class="form-group">
                    <label for="password">New Password</label>
                    <input type="password" id="password" name="password" required minlength="8">
                </div>
                
                <div class="form-group">
                    <label for="confirmPassword">Confirm New Password</label>
                    <input type="password" id="confirmPassword" name="confirmPassword" required minlength="8">
                </div>
                
                <button type="submit">Reset Password</button>
            </form>
        </div>
        
        <script>
            const form = document.getElementById('resetForm');
            const messageDiv = document.getElementById('message');
            
            form.addEventListener('submit', async (e) => {{
                e.preventDefault();
                
                const password = document.getElementById('password').value;
                const confirmPassword = document.getElementById('confirmPassword').value;
                
                // Validate passwords match
                if (password !== confirmPassword) {{
                    showMessage('Passwords do not match!', 'error');
                    return;
                }}
                
                // Validate password strength
                if (password.length < 8) {{
                    showMessage('Password must be at least 8 characters long!', 'error');
                    return;
                }}
                
                try {{
                    const response = await fetch('/auth/reset-password', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{
                            token: '{token}',
                            new_password: password
                        }})
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        showMessage(data.message, 'success');
                        form.reset();
                        
                        // Redirect after 2 seconds
                        setTimeout(() => {{
                            window.location.href = '#';  // Change to your login page
                        }}, 2000);
                    }} else {{
                        showMessage(data.detail || 'Password reset failed', 'error');
                    }}
                }} catch (error) {{
                    showMessage('An error occurred. Please try again.', 'error');
                }}
            }});
            
            function showMessage(text, type) {{
                messageDiv.textContent = text;
                messageDiv.className = 'message ' + type;
                messageDiv.style.display = 'block';
            }}
        </script>
    </body>
    </html>
    """)

@router.post("/reset-password")
async def reset_password(
    reset_data: schemas.PasswordReset,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Reset password with token (POST from form)"""
    
    user = crud.reset_user_password(db, reset_data.token, reset_data.new_password)
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token"
        )
    
    # Send confirmation email
    user_name = user.first_name or user.email.split('@')[0]
    confirmation_html = get_password_changed_email_template(user_name)
    
    background_tasks.add_task(
        send_email,
        to_email=user.email,
        subject="Password Changed - Quran Recitation App",
        html_content=confirmation_html
    )
    
    return {
        "message": "Password reset successfully! You can now login with your new password."
    }