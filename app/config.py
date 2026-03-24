import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# General App Settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/quran_app"
)

# Admin Configuration
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "default-secret-key").strip()
ADMIN_INIT_SECRET = os.getenv("ADMIN_INIT_SECRET", "your-super-secret-init-key").strip()
ADMIN_EMAILS = [
    email.strip() for email in os.getenv("ADMIN_EMAILS", "").split(",") 
    if email.strip()
]

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Payment Configuration (amounts in cents)
PREMIUM_PRICE_MONTHLY = int(os.getenv("PREMIUM_PRICE_MONTHLY", "2000"))
PREMIUM_PRICE_YEARLY = int(os.getenv("PREMIUM_PRICE_YEARLY", "20000"))

# Email SMTP Settings (Gmail)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USER)
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Quran Recitation App")

# Email - SendGrid
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# AI / Voice Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

