import firebase_admin
from firebase_admin import credentials, messaging
import os
from app.config import FIREBASE_SERVICE_ACCOUNT_PATH
import logging

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
try:
    if not firebase_admin._apps:
        # 1. Try to load from environment variable JSON string (Ideal for Render/Cloud)
        fcm_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        if fcm_json:
            import json
            service_account_info = json.loads(fcm_json)
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized from environment variable.")
        
        # 2. Fallback to file path
        else:
            # Check if the path is absolute or relative to the project root
            if not os.path.isabs(FIREBASE_SERVICE_ACCOUNT_PATH):
                # Assuming project root is the parent of 'app'
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                full_path = os.path.join(project_root, FIREBASE_SERVICE_ACCOUNT_PATH)
            else:
                full_path = FIREBASE_SERVICE_ACCOUNT_PATH

            if os.path.exists(full_path):
                cred = credentials.Certificate(full_path)
                firebase_admin.initialize_app(cred)
                logger.info(f"Firebase Admin SDK initialized from file: {full_path}")
            else:
                logger.warning("Firebase credentials not found (checked FIREBASE_SERVICE_ACCOUNT_JSON and file path). Push notifications will not work.")
except Exception as e:
    logger.error(f"Failed to initialize Firebase Admin SDK: {e}")


def send_fcm_message(tokens: list[str], title: str, body: str, data: dict = None):
    """
    Send a push notification to multiple device tokens.
    """
    if not firebase_admin._apps:
        logger.warning("Firebase Admin SDK not initialized. Cannot send push notification.")
        return False

    if not tokens:
        return False

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data or {},
        tokens=tokens,
    )

    try:
        response = messaging.send_multicast(message)
        logger.info(f"Successfully sent FCM message: {response.success_count} success, {response.failure_count} failure")
        return response
    except Exception as e:
        logger.error(f"Error sending FCM message: {e}")
        return False
