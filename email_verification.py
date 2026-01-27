from sqlalchemy import text
from app.database import engine

sql = """
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR UNIQUE,
ADD COLUMN IF NOT EXISTS verification_token_expires TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(email_verification_token);
"""

try:
    with engine.connect() as connection:
        for statement in sql.split(';'):
            if statement.strip():
                connection.execute(text(statement))
                connection.commit()
    
    print("✅ Email verification fields added!")
    
except Exception as e:
    print(f"❌ Error: {e}")