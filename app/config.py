import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "85715069783-dos5k81m9682gp0255ai69a8rascddf7.apps.googleusercontent.com")
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "com.yourapp.service")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "YOUR_TEAM_ID")