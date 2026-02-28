import requests
import os
from dotenv import load_dotenv

load_dotenv()

FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")

def sign_in_with_email(email, password):
    """
    Signs in a user using Firebase Auth REST API.
    Returns (id_token, local_id, email, error_message)
    """
    if not FIREBASE_WEB_API_KEY:
        return None, None, None, "FIREBASE_WEB_API_KEY is not set in .env"

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 200:
            return data["idToken"], data["localId"], data["email"], None
        else:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            return None, None, None, error_msg
    except Exception as e:
        return None, None, None, str(e)

def sign_up_with_email(email, password):
    """
    Registers a new user using Firebase Auth REST API.
    """
    if not FIREBASE_WEB_API_KEY:
        return None, None, None, "FIREBASE_WEB_API_KEY is not set in .env"

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 200:
            return data["idToken"], data["localId"], data["email"], None
        else:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            return None, None, None, error_msg
    except Exception as e:
        return None, None, None, str(e)
