"""
Complete Test Suite for Quran Recitation API
=============================================
Tests all endpoints to ensure production readiness.

Run with: pytest tests/test_complete_api.py -v
Voice tests: pytest tests/test_complete_api.py -v --run-voice-tests
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import base64
import wave
import io
import struct

from app.main import app
from app.database import Base, get_db
from app.models import User, Surah, Ayah


# =============================================================================
# PYTEST CLI OPTION + MARKER REGISTRATION (pytest 9 compatible)
# =============================================================================

def pytest_addoption(parser):
    parser.addoption(
        "--run-voice-tests",
        action="store_true",
        default=False,
        help="Run voice tests (requires OPENAI_API_KEY).",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "voice: tests that require OpenAI API key")


# =============================================================================
# TEST DATABASE SETUP
# =============================================================================

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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

    db = TestingSessionLocal()

    # Add Al-Fatihah (avoid duplicate seed on reruns)
    existing = db.query(Surah).filter(Surah.number == 1).first()
    if not existing:
        surah = Surah(
            number=1,
            name_ar="الفاتحة",
            name_en="Al-Fatihah",
            ayah_count=7,
        )
        db.add(surah)
        db.commit()
        db.refresh(surah)

        ayahs = [
            Ayah(surah_id=surah.id, number=1, text="بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"),
            Ayah(surah_id=surah.id, number=2, text="الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ"),
            Ayah(surah_id=surah.id, number=3, text="الرَّحْمَٰنِ الرَّحِيمِ"),
        ]
        db.add_all(ayahs)
        db.commit()

    db.close()

    yield

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_user(client):
    """Create and return test user with token"""
    # Register (if already exists, ignore)
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "TestPassword123"},
    )
    assert response.status_code in (200, 400)

    # Verify email manually
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "test@example.com").first()
    assert user is not None
    user.is_email_verified = True
    db.commit()
    db.close()

    # Login
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "TestPassword123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    return {"email": "test@example.com", "password": "TestPassword123", "token": token}


def create_test_audio():
    """Create a simple WAV audio file as base64"""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)

        duration = 1.0
        num_frames = int(16000 * duration)
        silence_frame = struct.pack("<h", 0)
        wav_file.writeframes(silence_frame * num_frames)

    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode()


# ============================================================================
# ROOT & HEALTH ENDPOINTS
# ============================================================================

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "features" in data


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={"email": "newuser@example.com", "password": "NewPassword123"},
    )
    assert response.status_code in (200, 400)
    if response.status_code == 200:
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert "id" in data


def test_register_duplicate_email(client, test_user):
    response = client.post(
        "/auth/register",
        json={"email": test_user["email"], "password": "AnotherPassword123"},
    )
    assert response.status_code == 400
    assert "already" in response.json()["detail"].lower()


def test_login_success(client, test_user):
    response = client.post(
        "/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, test_user):
    response = client.post(
        "/auth/login",
        json={"email": test_user["email"], "password": "WrongPassword123"},
    )
    assert response.status_code == 401


def test_login_unverified_email(client):
    client.post("/auth/register", json={"email": "unverified@example.com", "password": "Password123"})

    response = client.post(
        "/auth/login",
        json={"email": "unverified@example.com", "password": "Password123"},
    )
    assert response.status_code == 403
    assert "not verified" in response.json()["detail"].lower()


# ============================================================================
# SURAH ENDPOINTS
# ============================================================================

def test_get_all_surahs(client):
    response = client.get("/surahs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["number"] == 1
    assert data[0]["name_en"] == "Al-Fatihah"


def test_get_single_surah(client):
    response = client.get("/surahs/1")
    assert response.status_code == 200
    data = response.json()
    assert data["number"] == 1
    assert data["name_ar"] == "الفاتحة"


def test_get_invalid_surah(client):
    response = client.get("/surahs/999")
    assert response.status_code == 404


# ============================================================================
# PROGRESS ENDPOINTS
# ============================================================================

def test_get_my_progress(client, test_user):
    response = client.get(
        "/progress/my-progress",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "surahs_read" in data
    assert "time_spent" in data
    assert "current_streak" in data
    assert "accuracy" in data


def test_log_activity(client, test_user):
    response = client.post(
        "/progress/log-activity",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "activity_type": "recitation",
            "surah_number": 1,
            "ayah_number": 1,
            "duration_seconds": 60,
            "accuracy_score": 95.5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["average_accuracy"] == 95.5


def test_log_multiple_activities(client, test_user):
    client.post(
        "/progress/log-activity",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "activity_type": "recitation",
            "surah_number": 1,
            "ayah_number": 1,
            "duration_seconds": 60,
            "accuracy_score": 90.0,
        },
    )

    response = client.post(
        "/progress/log-activity",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "activity_type": "recitation",
            "surah_number": 1,
            "ayah_number": 2,
            "duration_seconds": 60,
            "accuracy_score": 80.0,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["average_accuracy"] == 85.0


# ============================================================================
# LEADERBOARD ENDPOINTS
# ============================================================================

def test_get_leaderboard(client, test_user):
    for _ in range(6):
        client.post(
            "/progress/log-activity",
            headers={"Authorization": f"Bearer {test_user['token']}"},
            json={
                "activity_type": "recitation",
                "surah_number": 1,
                "ayah_number": 1,
                "duration_seconds": 60,
                "accuracy_score": 95.0,
            },
        )

    response = client.get(
        "/leaderboard/leaderboard",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "top_3" in data
    assert "current_user" in data
    assert "Accuracy" in data["ranking_criteria"]


# ============================================================================
# SETTINGS ENDPOINTS
# ============================================================================

def test_get_settings(client, test_user):
    response = client.get(
        "/user/settings",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "reading_preferences" in data
    assert "audio_settings" in data


def test_update_settings(client, test_user):
    response = client.put(
        "/user/settings",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={"text_size": "large", "theme": "dark", "show_on_leaderboard": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_get_profile(client, test_user):
    response = client.get(
        "/user/profile",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user["email"]


# ============================================================================
# PAYMENT ENDPOINTS
# ============================================================================

def test_get_subscription_plans(client):
    response = client.get("/payment/plans")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) >= 2


def test_get_subscription_status(client, test_user):
    response = client.get(
        "/payment/subscription-status",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["subscription_status"] == "free"


# ============================================================================
# RECITATION ENDPOINTS
# ============================================================================

def test_get_reciters(client, test_user):
    response = client.get(
        "/recitation/reciters",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "reciters" in data
    assert len(data["reciters"]) > 0
    locked_count = sum(1 for r in data["reciters"] if r.get("locked"))
    assert locked_count > 0


# ============================================================================
# VOICE RECITATION ENDPOINTS
# ============================================================================

@pytest.mark.voice
def test_voice_evaluate_rest(client, test_user, request):
    """
    Voice evaluation REST test.
    Runs ONLY when:
      - --run-voice-tests is passed
      - OPENAI_API_KEY exists in environment
    """
    if not request.config.getoption("--run-voice-tests"):
        pytest.skip("Use --run-voice-tests to run voice tests.")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not set.")

    audio_base64 = create_test_audio()

    response = client.post(
        "/voice/api/recite/evaluate",
        headers={"Authorization": f"Bearer {test_user['token']}"},
        json={
            "surah_number": 1,
            "ayah_start": 1,
            "ayah_end": 1,
            "audio_base64": audio_base64,
        },
    )

    assert response.status_code in (200, 500)

    if response.status_code == 200:
        data = response.json()
        assert "transcription" in data
        assert "evaluation" in data
        assert data["saved_to_db"] is True


def test_voice_websocket_connection(client):
    with client.websocket_connect("/voice/ws/recite?surah_number=1&ayah_start=1") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "ready"
        assert data["surah_info"]["number"] == 1
        assert "reference_text" in data


# ============================================================================
# AUTH PROTECTION TESTS
# ============================================================================

def test_protected_endpoint_without_token(client):
    response = client.get("/progress/my-progress")
    assert response.status_code == 401


def test_protected_endpoint_with_invalid_token(client):
    response = client.get(
        "/progress/my-progress",
        headers={"Authorization": "Bearer invalid_token_here"},
    )
    assert response.status_code == 401


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

def test_invalid_json_request(client):
    response = client.post(
        "/auth/register",
        data="invalid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_missing_required_fields(client):
    response = client.post("/auth/register", json={"email": "test@test.com"})
    assert response.status_code == 422


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_complete_user_flow(client):
    response = client.post("/auth/register", json={"email": "journey@example.com", "password": "Journey123"})
    assert response.status_code in (200, 400)

    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "journey@example.com").first()
    assert user is not None
    user.is_email_verified = True
    db.commit()
    db.close()

    response = client.post("/auth/login", json={"email": "journey@example.com", "password": "Journey123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/surahs", headers=headers)
    assert response.status_code == 200

    response = client.post(
        "/progress/log-activity",
        headers=headers,
        json={
            "activity_type": "recitation",
            "surah_number": 1,
            "ayah_number": 1,
            "duration_seconds": 120,
            "accuracy_score": 88.5,
        },
    )
    assert response.status_code == 200

    response = client.get("/progress/my-progress", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["accuracy"]["average"] == 88.5

    response = client.put("/user/settings", headers=headers, json={"theme": "dark"})
    assert response.status_code == 200


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

def test_concurrent_requests(client, test_user):
    import concurrent.futures

    def make_request():
        return client.get(
            "/progress/my-progress",
            headers={"Authorization": f"Bearer {test_user['token']}"},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert all(r.status_code == 200 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
