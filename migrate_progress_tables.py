from sqlalchemy import text
from app.database import engine

migration_sql = """
-- Drop existing tables if you want to recreate
DROP TABLE IF EXISTS user_achievements CASCADE;
DROP TABLE IF EXISTS user_activities CASCADE;
DROP TABLE IF EXISTS user_progress CASCADE;
DROP TABLE IF EXISTS achievements CASCADE;

-- Create user_progress table (UPDATED LOGIC)
CREATE TABLE user_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL UNIQUE,
    total_surahs_read INTEGER DEFAULT 0,
    total_time_spent_seconds INTEGER DEFAULT 0,
    total_ayahs_recited INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_activity_date TIMESTAMP,
    total_recitations INTEGER DEFAULT 0,
    correct_recitations INTEGER DEFAULT 0,
    total_accuracy_points FLOAT DEFAULT 0.0,
    average_accuracy FLOAT DEFAULT 0.0,
    total_recitation_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_user_progress_user_id ON user_progress(user_id);
CREATE INDEX idx_user_progress_accuracy ON user_progress(average_accuracy DESC);
CREATE INDEX idx_user_progress_attempts ON user_progress(total_recitation_attempts DESC);

-- Create user_activities table
CREATE TABLE user_activities (
    id SERIAL PRIMARY KEY,
    user_progress_id INTEGER REFERENCES user_progress(id) ON DELETE CASCADE,
    activity_type VARCHAR NOT NULL,
    surah_number INTEGER NOT NULL,
    ayah_number INTEGER,
    duration_seconds INTEGER DEFAULT 0,
    accuracy_score FLOAT,
    points_earned INTEGER DEFAULT 0,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_activities_progress ON user_activities(user_progress_id);
CREATE INDEX idx_user_activities_date ON user_activities(date DESC);

-- Create achievements table
CREATE TABLE achievements (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT NOT NULL,
    icon VARCHAR,
    achievement_type VARCHAR NOT NULL,
    threshold INTEGER NOT NULL,
    points INTEGER DEFAULT 0
);

-- Create user_achievements table
CREATE TABLE user_achievements (
    id SERIAL PRIMARY KEY,
    user_progress_id INTEGER REFERENCES user_progress(id) ON DELETE CASCADE,
    achievement_id INTEGER REFERENCES achievements(id) ON DELETE CASCADE,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_new BOOLEAN DEFAULT TRUE,
    UNIQUE(user_progress_id, achievement_id)
);

CREATE INDEX idx_user_achievements_progress ON user_achievements(user_progress_id);

-- Insert achievements (UPDATED FOR NEW LOGIC)
INSERT INTO achievements (name, description, icon, achievement_type, threshold, points) VALUES
('7 Day Streak', 'Use the app for 7 consecutive days', '🔥', 'streak', 7, 100),
('30 Day Streak', 'Use the app for 30 consecutive days', '🔥', 'streak', 30, 500),
('First Recitation', 'Complete your first recitation', '🎤', 'recitations', 1, 50),
('10 Recitations', 'Complete 10 recitations', '🎤', 'recitations', 10, 200),
('50 Recitations', 'Complete 50 recitations', '🏆', 'recitations', 50, 1000),
('Accuracy Master', 'Achieve 95%+ average accuracy', '⭐', 'accuracy', 95, 500),
('Perfect Recitation', 'Achieve 100% accuracy on a recitation', '💯', 'accuracy', 100, 150),
('Dedicated Student', 'Spend 10 hours in the app', '📚', 'time_spent', 10, 300),
('Scholar', 'Spend 50 hours in the app', '🎓', 'time_spent', 50, 1500)
ON CONFLICT DO NOTHING;
"""

try:
    with engine.connect() as connection:
        for statement in migration_sql.split(';'):
            if statement.strip():
                connection.execute(text(statement))
                connection.commit()
    
    print("✅ Progress tables updated with new logic!")
    
except Exception as e:
    print(f"❌ Error: {e}")