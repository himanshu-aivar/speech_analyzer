import requests
from fastapi import APIRouter, HTTPException
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import jwt
from datetime import datetime, timedelta
from settings import settings
from db import users_collection  # assume MongoDB
from pydantic import BaseModel

class SSOLoginRequest(BaseModel):
    provider: str  # "google" | "microsoft"
    token: str

class JWTResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
router = APIRouter(prefix="/api/auth", tags=["Auth"])

def create_jwt(user: dict) -> str:
    """
    Minimal JWT containing only name, email, image.
    """
    payload = {
        "email": user["email"],
        "name": user.get("name"),
        "image": user.get("image"),
        "exp": datetime.utcnow() + timedelta(hours=8),
        "role": user.get("role")
    }
    print(f"[INFO] Creating JWT for user: {user['email']}")
    token = jwt.encode(payload, settings.AUTH_SECRET, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def verify_google_token(token: str):
    try:
        idinfo = id_token.verify_oauth2_token(token, grequests.Request(), settings.GOOGLE_CLIENT_ID)
        email = idinfo.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid Google token (no email)")
        return email.lower(), idinfo.get("name"), idinfo.get("picture")
    except Exception as e:
        print(f"[ERROR] Google token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google token")

def verify_microsoft_token(token: str):
    resp = requests.get(
        "https://graph.microsoft.com/oidc/userinfo",
        headers={"Authorization": f"Bearer {token}"}, timeout=10
    )
    if resp.status_code != 200:
        print(f"[ERROR] Microsoft token verification failed: {resp.text}")
        raise HTTPException(status_code=401, detail="Invalid Microsoft token")
    data = resp.json()
    email = data.get("email") or data.get("preferred_username")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid Microsoft token (no email)")
    return email.lower(), data.get("name"), data.get("picture")

@router.post("/sso-login", response_model=JWTResponse)
def sso_login(payload: SSOLoginRequest):
    print(f"[INFO] SSO login request received for provider: {payload.provider}")
    
    if payload.provider == "google":
        email, name, image = verify_google_token(payload.token)
    elif payload.provider == "microsoft":
        email, name, image = verify_microsoft_token(payload.token)
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    # Only allow login if user exists
    user = users_collection.find_one({"email": email})
    if not user:
        print(f"[WARN] SSO login denied: user not registered: {email}")
        raise HTTPException(status_code=403, detail="User not registered. Contact your admin.")

    # Optionally update missing name/image in DB
    updates = {}
    if name and not user.get("name"):
        updates["name"] = name
    if image and not user.get("image"):
        updates["image"] = image
    if updates:
        users_collection.update_one({"_id": user["_id"]}, {"$set": updates})
        user.update(updates)

    jwt_token = create_jwt(user)
    print(f"[INFO] SSO login successful for user: {email}")
    return JWTResponse(access_token=jwt_token)
