import sys
from sqlalchemy import text
from app.database import SessionLocal

def main():
    db = SessionLocal()
    try:
        # Run the SQL migration
        db.execute(text("ALTER TABLE users ADD COLUMN is_suspended BOOLEAN DEFAULT FALSE NOT NULL;"))
        db.commit()
        print("Successfully added is_suspended column to users table.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
