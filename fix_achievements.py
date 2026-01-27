from sqlalchemy import text
from app.database import engine

print("🔧 Fixing achievements...")

sql = """
-- Delete old achievements
DELETE FROM user_achievements;
DELETE FROM achievements;

-- Insert with correct enum values
INSERT INTO achievements (name, description, icon, achievement_type, threshold, points) VALUES
('7 Day Streak', 'Use the app for 7 consecutive days', '🔥', 'STREAK', 7, 100),
('30 Day Streak', 'Use the app for 30 consecutive days', '🔥', 'STREAK', 30, 500),
('First Recitation', 'Complete your first recitation', '🎤', 'RECITATIONS', 1, 50),
('10 Recitations', 'Complete 10 recitations', '🎤', 'RECITATIONS', 10, 200),
('50 Recitations', 'Complete 50 recitations', '🏆', 'RECITATIONS', 50, 1000),
('Accuracy Master', 'Achieve 95%+ average accuracy', '⭐', 'ACCURACY', 95, 500),
('Perfect Recitation', 'Achieve 100%% accuracy on a recitation', '💯', 'ACCURACY', 100, 150),
('Dedicated Student', 'Spend 10 hours in the app', '📚', 'TIME_SPENT', 10, 300),
('Scholar', 'Spend 50 hours in the app', '🎓', 'TIME_SPENT', 50, 1500);
"""

try:
    with engine.connect() as connection:
        for statement in sql.split(';'):
            if statement.strip():
                connection.execute(text(statement))
                connection.commit()
    
    print("✅ Achievements fixed!")
    
except Exception as e:
    print(f"❌ Error: {e}")