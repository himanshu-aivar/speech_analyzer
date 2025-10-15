from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from settings import settings

security = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=403, detail="Invalid or missing auth scheme")

    token = credentials.credentials.strip()

    try:
        payload = jwt.decode(token, settings.AUTH_SECRET, algorithms=[ALGORITHM])
        return {
            "email": payload["email"],
            "role": payload["role"],
            "name": payload.get("name"),
            "image": payload.get("image")
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
