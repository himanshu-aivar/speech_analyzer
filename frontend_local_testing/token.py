# jwt_utils.py

from datetime import datetime, timedelta
import jwt
import os

# -----------------------------
# Settings
# -----------------------------
from settings import Settings
settings = Settings()


# -----------------------------
# JWT Creation
# -----------------------------
def create_jwt(user: dict) -> str:
    """
    Create a minimal JWT containing only name, email, image, and role.
    Expiration is set to 8 hours from creation.
    """
    payload = {
        "email": user["email"],
        "name": user.get("name"),
        "image": user.get("image"),
        "role": user.get("role"),
        "exp": datetime.utcnow() + timedelta(hours=800),
    }

    print(f"[INFO] Creating JWT for user: {user['email']}")
    token = jwt.encode(payload, settings.AUTH_SECRET, algorithm="HS256")

    # Handle PyJWT returning bytes in some versions
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    test_user = {
        "email": "himanshugoyal000043@gmail.com",
        "name": "Himanshu Goyal",
        "image": "https://lh3.googleusercontent.com/a/ACg8ocLo1HVS_4Ru-QO6_PWiIKDsBmWQGDRZb1RCnTguEdII2LMDNQ=s96-c",
        "role": "user",
    }
    token = create_jwt(test_user)
    print("Generated JWT:", token)
