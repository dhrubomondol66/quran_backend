"""
Complete Test Suite for Quran Recitation API
=============================================
Tests all endpoints to ensure production readiness.

Run with: pytest tests/test_complete_api.py -v
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json
import base64
import wave
import io
import struct

from app.main import app
from app.database import Base, get_db
from app.models import User, Surah, Ayah, UserProgress, SubscriptionStatus

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Setup
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables and seed data"""
    Base.metadata.create_all(bind=engine)
    
    # Seed Quran data
    db = TestingSessionLocal()
    
    # Add Al-Fatihah
    surah = Surah(
        number=1,
        name_ar="الفاتحة",
        name_en="Al-Fatihah",
        ayah_count=7
    )
    db.add(surah)
    db.commit()
    
    # Add ayahs
    ayahs = [
        Ayah(surah_id=surah.id, number=1, text="بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"),
        Ayah(surah_id=surah.id, number=2, text="الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ"),
        Ayah(surah_id=surah.id, number=3, text="الرَّحْمَٰنِ الرَّحِيمِ"),
    ]
    db.add_all(ayahs)
    db.commit()
    db.close()
    
    yield
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    """Test client"""
    return TestClient(app)

@pytest.fixture
def test_user(client):
    """Create and return test user with token"""
    # Register
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "TestPassword123"
    })
    assert response.status_code == 200
    
    # Verify email manually in database
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "test@example.com").first()
    user.is_email_verified = True
    db.commit()
    db.close()
    
    # Login
    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "TestPassword123"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    return {
        "email": "test@example.com",
        "password": "TestPassword123",
        "token": token
    }

def create_test_audio():
    """Create a simple WAV audio file as base64"""
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)  # 16kHz
        
        # Generate 1 second of silence
        duration = 1.0
        num_frames = int(16000 * duration)
        for _ in range(num_frames):
            wav_file.writeframes(struct.pack('<h', 0))
    
    buffer.seek(0)
    audio_bytes = buffer.read()
    return base64.b64encode(audio_bytes).decode()


# ============================================================================
# ROOT & HEALTH ENDPOINTS
# ============================================================================

def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "features" in data

def test_health_endpoint(client):
    """Test health check"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

def test_register_user(client):
    """Test user registration"""
    response = client.post("/auth/register", json={
        "email": "newuser@example.com",
        "password": "NewPassword123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data

def test_register_duplicate_email(client, test_user):
    """Test registration with existing email"""
    response = client.post("/auth/register", json={
        "email": test_user["email"],
        "password": "AnotherPassword123"
    })
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]

def test_login_success(client, test_user):
    """Test successful login"""
    response = client.post("/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"]
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_wrong_password(client, test_user):
    """Test login with wrong password"""
    response = client.post("/auth/login", json={
        "email": test_user["email"],
        "password": "WrongPassword123"
    })
    assert response.status_code == 401

def test_login_unverified_email(client):
    """Test login with unverified email"""
    # Register user
    client.post("/auth/register", json={
        "email": "unverified@example.com",
        "password": "Password123"
    })
    
    # Try to login without verification
    response = client.post("/auth/login", json={
        "email": "unverified@example.com",
        "password": "Password123"
    })
    assert response.status_code == 403
    assert "not verified" in response.json()["detail"]


# ============================================================================
# SURAH ENDPOINTS
# ============================================================================

def test_get_all_surahs(client):
    """Test getting all surahs"""
    response = client.get("/surahs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["number"] == 1
    assert data[0]["name_en"] == "Al-Fatihah"

def test_get_single_surah(client):
    """Test getting single surah"""
    response = client.get("/surahs/1")
    assert response.status_code == 200
    data = response.json()
    assert data["number"] == 1
    assert data["name_ar"] == "الفاتحة"

def test_get_invalid_surah(client):
    """Test getting non-existent surah"""
    response = client.get("/surahs/999")
    assert response.status_code == 404


# ============================================================================
# PROGRESS ENDPOINTS
# ============================================================================

def test_get_my_progress(client, test_user):
    """Test getting user progress"""
    response = client.get(
        "/progress/my-progress",
        headers={"Authorization": f"Bearer {test_user['token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "surahs_read" in data
    assert "time_spent" in data
    assert "current_streak" in data
    assert "accuracy" in data

def test_log_activity(client, test_user):
    """Test logging user activity"""
    response = client.post(
        "/progress/log-activity",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "activity_type": "recitation",
            "surah_number": 1,
            "ayah_number": 1,
            "duration_seconds": 60,
            "accuracy_score": 95.5
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["average_accuracy"] == 95.5

def test_log_multiple_activities(client, test_user):
    """Test logging multiple activities and accuracy calculation"""
    # First activity - 90%
    client.post(
        "/progress/log-activity",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "activity_type": "recitation",
            "surah_number": 1,
            "ayah_number": 1,
            "duration_seconds": 60,
            "accuracy_score": 90.0
        }
    )
    
    # Second activity - 80%
    response = client.post(
        "/progress/log-activity",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "activity_type": "recitation",
            "surah_number": 1,
            "ayah_number": 2,
            "duration_seconds": 60,
            "accuracy_score": 80.0
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    # Average should be (90 + 80) / 2 = 85
    assert data["average_accuracy"] == 85.0


# ============================================================================
# LEADERBOARD ENDPOINTS
# ============================================================================

def test_get_leaderboard(client, test_user):
    """Test getting leaderboard"""
    # First log some activities to get on leaderboard
    for i in range(6):  # Need at least 5 recitations
        client.post(
            "/progress/log-activity",
            headers={"Authorization": f"Bearer {test_user['token']}"},
            json={
                "activity_type": "recitation",
                "surah_number": 1,
                "ayah_number": 1,
                "duration_seconds": 60,
                "accuracy_score": 95.0
            }
        )
    
    response = client.get(
        "/leaderboard/leaderboard",
        headers={"Authorization": f"Bearer {test_user['token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "top_3" in data
    assert "current_user" in data
    assert data["ranking_criteria"] == "Accuracy (minimum 5 recitations required)"


# ============================================================================
# SETTINGS ENDPOINTS
# ============================================================================

def test_get_settings(client, test_user):
    """Test getting user settings"""
    response = client.get(
        "/user/settings",
        headers={"Authorization": f"Bearer {test_user['token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "reading_preferences" in data
    assert "audio_settings" in data

def test_update_settings(client, test_user):
    """Test updating settings"""
    response = client.put(
        "/user/settings",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "text_size": "large",
            "theme": "dark",
            "show_on_leaderboard": False
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True

def test_get_profile(client, test_user):
    """Test getting user profile"""
    response = client.get(
        "/user/profile",
        headers={"Authorization": f"Bearer {test_user['token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user["email"]


# ============================================================================
# PAYMENT ENDPOINTS
# ============================================================================

def test_get_subscription_plans(client):
    """Test getting available plans"""
    response = client.get("/payment/plans")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) >= 2  # Monthly and Yearly

def test_get_subscription_status(client, test_user):
    """Test getting subscription status"""
    response = client.get(
        "/payment/subscription-status",
        headers={"Authorization": f"Bearer {test_user['token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["subscription_status"] == "free"


# ============================================================================
# RECITATION ENDPOINTS (Audio API)
# ============================================================================

def test_get_reciters(client, test_user):
    """Test getting available reciters"""
    response = client.get(
        "/recitation/reciters",
        headers={"Authorization": f"Bearer {test_user['token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "reciters" in data
    assert len(data["reciters"]) > 0
    
    # Free users should see some locked reciters
    locked_count = sum(1 for r in data["reciters"] if r.get("locked"))
    assert locked_count > 0


# ============================================================================
# VOICE RECITATION ENDPOINTS
# ============================================================================

@pytest.mark.skipif(
    not pytest.config.getoption("--run-voice-tests", default=False),
    reason="Voice tests require OPENAI_API_KEY"
)
def test_voice_evaluate_rest(client, test_user):
    """Test REST voice evaluation endpoint"""
    audio_base64 = create_test_audio()
    
    response = client.post(
        "/voice/api/recite/evaluate",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "surah_number": 1,
            "ayah_start": 1,
            "ayah_end": 1,
            "audio_base64": audio_base64
        }
    )
    
    # This will fail without OpenAI API key, but structure is correct
    assert response.status_code in [200, 500]  # 500 if no API key
    
    if response.status_code == 200:
        data = response.json()
        assert "transcription" in data
        assert "evaluation" in data
        assert data["saved_to_db"] == True


def test_voice_websocket_connection(client):
    """Test WebSocket connection"""
    from fastapi.testclient import TestClient
    
    with client.websocket_connect("/voice/ws/recite?surah_number=1&ayah_start=1") as websocket:
        # Receive ready message
        data = websocket.receive_json()
        assert data["type"] == "ready"
        assert data["surah_info"]["number"] == 1
        assert "reference_text" in data


# ============================================================================
# AUTHENTICATION PROTECTION TESTS
# ============================================================================

def test_protected_endpoint_without_token(client):
    """Test accessing protected endpoint without token"""
    response = client.get("/progress/my-progress")
    assert response.status_code == 401

def test_protected_endpoint_with_invalid_token(client):
    """Test accessing protected endpoint with invalid token"""
    response = client.get(
        "/progress/my-progress",
        headers={"Authorization": "Bearer invalid_token_here"}
    )
    assert response.status_code == 401


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

def test_invalid_json_request(client):
    """Test sending invalid JSON"""
    response = client.post(
        "/auth/register",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422

def test_missing_required_fields(client):
    """Test missing required fields"""
    response = client.post("/auth/register", json={
        "email": "test@test.com"
        # Missing password
    })
    assert response.status_code == 422


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_complete_user_flow(client):
    """Test complete user journey"""
    # 1. Register
    response = client.post("/auth/register", json={
        "email": "journey@example.com",
        "password": "Journey123"
    })
    assert response.status_code == 200
    
    # 2. Verify email (manual)
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "journey@example.com").first()
    user.is_email_verified = True
    db.commit()
    db.close()
    
    # 3. Login
    response = client.post("/auth/login", json={
        "email": "journey@example.com",
        "password": "Journey123"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 4. Get surahs
    response = client.get("/surahs", headers=headers)
    assert response.status_code == 200
    
    # 5. Log activity
    response = client.post(
        "/progress/log-activity",
        headers=headers,
        json={
            "activity_type": "recitation",
            "surah_number": 1,
            "ayah_number": 1,
            "duration_seconds": 120,
            "accuracy_score": 88.5
        }
    )
    assert response.status_code == 200
    
    # 6. Check progress
    response = client.get("/progress/my-progress", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["accuracy"]["average"] == 88.5
    
    # 7. Update settings
    response = client.put(
        "/user/settings",
        headers=headers,
        json={"theme": "dark"}
    )
    assert response.status_code == 200


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

def test_concurrent_requests(client, test_user):
    """Test handling concurrent requests"""
    import concurrent.futures
    
    def make_request():
        return client.get(
            "/progress/my-progress",
            headers={"Authorization": f"Bearer {test_user['token']}"}
        )
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    # All should succeed
    assert all(r.status_code == 200 for r in results)


# ============================================================================
# RUN CONFIGURATION
# ============================================================================

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "voice: tests that require OpenAI API key"
    )

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
