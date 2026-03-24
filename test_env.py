import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Test variables
variables = [
    "DATABASE_URL",
    "SECRET_KEY",
    "ADMIN_SECRET_KEY",
    "ADMIN_INIT_SECRET",
    "CLOUDINARY_CLOUD_NAME",
    "SMTP_HOST",
    "FRONTEND_URL"
]

print("Verifying environment variables:")
for var in variables:
    value = os.getenv(var)
    if value:
        print(f"✅ {var} is correctly loaded: {value}")
    else:
        print(f"❌ {var} is missing!")
