
import firebase_admin
from firebase_admin import credentials, firestore
import logging
from typing import Dict, Any, Optional, List
from app.core.settings import settings

logger = logging.getLogger(__name__)

class FirestoreClient:
    """
    Wrapper for Firebase Firestore.
    Handles real-time data storage and session management.
    """

    def __init__(self):
        self.db = None
        self._initialize()

    def _initialize(self):
        """
        Initialize Firebase Admin SDK if not already initialized.
        """
        try:
            # Check if already initialized
            if not firebase_admin._apps:
                # In production, use default credentials (GOOGLE_APPLICATION_CREDENTIALS)
                # Or use service account path from settings
                if settings.FIREBASE_CREDENTIALS_PATH:
                    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                    firebase_admin.initialize_app(cred)
                else:
                    # Use Cloud Run / Default credentials
                    firebase_admin.initialize_app()
            
            self.db = firestore.client()
            logger.info("Firestore initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            self.db = None

    def save_session(self, user_id: str, session_data: Dict[str, Any]):
        """
        Save user session data in real-time.
        """
        if not self.db:
             return
        
        try:
            doc_ref = self.db.collection('sessions').document(user_id)
            doc_ref.set(session_data, merge=True)
        except Exception as e:
            logger.error(f"Error saving session to Firestore: {e}")

    def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user session.
        """
        if not self.db:
            return None
        
        try:
            doc = self.db.collection('sessions').document(user_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting session from Firestore: {e}")
            return None

    def add_solution(self, solution_data: Dict[str, Any]):
        """
        Add a solved problem to the solutions collection.
        """
        if not self.db:
            return

        try:
            self.db.collection('solutions').add(solution_data)
        except Exception as e:
            logger.error(f"Error adding solution to Firestore: {e}")
