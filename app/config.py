import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Payment Configuration (amounts in cents)
PREMIUM_PRICE_MONTHLY = 2000  # $20.00
PREMIUM_PRICE_YEARLY = 20000  # $200.00

