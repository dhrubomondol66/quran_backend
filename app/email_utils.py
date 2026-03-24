import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
import ssl
from app.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM_EMAIL, SMTP_FROM_NAME, FRONTEND_URL,
    SENDGRID_API_KEY
)

def send_email_sync(to_email: str, subject: str, html_content: str):
    """Send email using SendGrid (if available) or Gmail fallback"""
    
    # Try SendGrid first
    if SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            
            message = Mail(
                from_email=(SMTP_FROM_EMAIL, SMTP_FROM_NAME),
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            print(f"✅ Email sent via SendGrid to {to_email} - Status: {response.status_code}")
            return True
            
        except Exception as e:
            print(f"⚠️ SendGrid failed: {e}, falling back to Gmail")
    
    # Fallback to Gmail
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)
    
    try:
        context = ssl.create_default_context()
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        
        print(f"✅ Email sent via Gmail to {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("Check your SMTP_USER and SMTP_PASSWORD in .env")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error: {e}")
        return False
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

async def send_email(to_email: str, subject: str, html_content: str):
    """Async wrapper for send_email_sync"""
    return send_email_sync(to_email, subject, html_content)

def get_verification_email_template(verification_link: str, user_email: str) -> str:
    """Generate verification email HTML"""
    
    template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }
            .content {
                background: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 10px 10px;
            }
            .button {
                display: inline-block;
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
                font-weight: bold;
            }
            .footer {
                text-align: center;
                margin-top: 30px;
                color: #666;
                font-size: 12px;
            }
            .warning {
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📖 Quran Recitation App</h1>
            <p>Verify Your Email Address</p>
        </div>
        <div class="content">
            <h2>Welcome! 🎉</h2>
            <p>Thank you for registering with Quran Recitation App. We're excited to have you join our community!</p>
            
            <p>To complete your registration and start your journey with the Quran, please verify your email address by clicking the button below:</p>
            
            <div style="text-align: center;">
                <a href="{{ verification_link }}" class="button">Verify Email Address</a>
            </div>
            
            <p>Or copy and paste this link into your browser:</p>
            <p style="background: white; padding: 10px; border-radius: 5px; word-break: break-all;">
                {{ verification_link }}
            </p>
            
            <div class="warning">
                <strong>⚠️ Important:</strong> This verification link will expire in 24 hours.
            </div>
            
            <p>If you didn't create an account with us, please ignore this email.</p>
            
            <p>Best regards,<br>The Quran Recitation Team</p>
        </div>
        <div class="footer">
            <p>© 2026 Quran Recitation App. All rights reserved.</p>
            <p>This is an automated message, please do not reply to this email.</p>
        </div>
    </body>
    </html>
    """)
    
    return template.render(verification_link=verification_link, user_email=user_email)

def get_welcome_email_template(user_name: str) -> str:
    """Generate welcome email after verification"""
    
    template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }
            .content {
                background: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 10px 10px;
            }
            .feature {
                background: white;
                padding: 15px;
                margin: 10px 0;
                border-left: 4px solid #667eea;
                border-radius: 5px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>✅ Email Verified!</h1>
            <p>Welcome to Quran Recitation App</p>
        </div>
        <div class="content">
            <h2>As-salamu alaykum, {{ user_name }}! 🌙</h2>
            
            <p>Your email has been successfully verified. You now have full access to all features!</p>
            
            <h3>What you can do now:</h3>
            
            <div class="feature">
                <strong>🎧 Listen to Recitations</strong><br>
                Access beautiful recitations from world-renowned reciters
            </div>
            
            <div class="feature">
                <strong>🎤 Practice Your Recitation</strong><br>
                Record and track your accuracy with AI-powered feedback
            </div>
            
            <div class="feature">
                <strong>📊 Track Your Progress</strong><br>
                Monitor your daily streaks, accuracy, and time spent
            </div>
            
            <div class="feature">
                <strong>🏆 Compete on Leaderboards</strong><br>
                See how you rank against other users based on accuracy
            </div>
            
            <p style="margin-top: 30px;">Start your Quranic journey today and may Allah make it easy for you!</p>
            
            <p>Best regards,<br>The Quran Recitation Team</p>
        </div>
    </body>
    </html>
    """)
    
    return template.render(user_name=user_name)


def get_password_reset_email_template(reset_link: str, user_email: str) -> str:
    """Generate password reset email HTML"""
    
    template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }
            .content {
                background: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 10px 10px;
            }
            .button {
                display: inline-block;
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
                font-weight: bold;
            }
            .footer {
                text-align: center;
                margin-top: 30px;
                color: #666;
                font-size: 12px;
            }
            .warning {
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }
            .security-note {
                background: #e3f2fd;
                border-left: 4px solid #2196f3;
                padding: 15px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔐 Password Reset Request</h1>
            <p>Quran Recitation App</p>
        </div>
        <div class="content">
            <h2>Reset Your Password</h2>
            <p>We received a request to reset the password for your account associated with <strong>{{ user_email }}</strong>.</p>
            
            <p>Click the button below to reset your password:</p>
            
            <div style="text-align: center;">
                <a href="{{ reset_link }}" class="button">Reset Password</a>
            </div>
            
            <p>Or copy and paste this link into your browser:</p>
            <p style="background: white; padding: 10px; border-radius: 5px; word-break: break-all;">
                {{ reset_link }}
            </p>
            
            <div class="warning">
                <strong>⚠️ Important:</strong> This password reset link will expire in 1 hour.
            </div>
            
            <div class="security-note">
                <strong>🔒 Security Note:</strong> If you didn't request a password reset, please ignore this email. Your password will remain unchanged.
            </div>
            
            <p>Best regards,<br>The Quran Recitation Team</p>
        </div>
        <div class="footer">
            <p>© 2026 Quran Recitation App. All rights reserved.</p>
            <p>This is an automated message, please do not reply to this email.</p>
        </div>
    </body>
    </html>
    """)
    
    return template.render(reset_link=reset_link, user_email=user_email)

def get_password_changed_email_template(user_name: str) -> str:
    """Generate password changed confirmation email"""
    
    template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }
            .header {
                background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }
            .content {
                background: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 10px 10px;
            }
            .security-alert {
                background: #ffebee;
                border-left: 4px solid #f44336;
                padding: 15px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>✅ Password Changed Successfully</h1>
        </div>
        <div class="content">
            <h2>Hello, {{ user_name }}!</h2>
            
            <p>Your password has been successfully changed.</p>
            
            <p>You can now use your new password to log in to your account.</p>
            
            <div class="security-alert">
                <strong>⚠️ Didn't change your password?</strong><br>
                If you didn't make this change, please contact us immediately at support@quranapp.com or reset your password again.
            </div>
            
            <p>Best regards,<br>The Quran Recitation Team</p>
        </div>
    </body>
    </html>
    """)
    
    return template.render(user_name=user_name)