from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from bson import ObjectId
from db import users_collection, orgs_collection
from core.auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/api/users", tags=["Users"])

# -----------------------------
# Models
# -----------------------------
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str = Field(..., pattern="^(user|admin)$")  # only user or admin
    allocated_video_credits: Optional[int] = Field(
        None, description="Video credits to assign (only for users; ignored for admins)"
    )

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(user|admin)$")
    allocated_video_credits: Optional[int] = None  # optional update

class UserOut(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    email: EmailStr
    role: str
    org_id: str
    allocated_video_credits: int = 0  # default 0 for admins or old users

class CreditAllocationUpdate(BaseModel):
    allocated_video_credits: int = Field(..., ge=0, description="Number of video credits to allocate to the user")

# -----------------------------
# Helper
# -----------------------------
async def get_user_org(current_user):
    """Fetch current user from DB to get org_id"""
    user_in_db = users_collection.find_one({"email": current_user["email"]})
    if not user_in_db:
        raise HTTPException(status_code=404, detail="Current user not found")
    return str(user_in_db["org_id"])

# -----------------------------
# APIs
# -----------------------------

async def get_user_org(current_user: dict) -> ObjectId:
    """
    Extract org_id from the current user's email (via token).
    """
    user = users_collection.find_one({"email": current_user["email"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user["org_id"]

# -----------------------------
# Create User
# -----------------------------
@router.post("/", response_model=UserOut)
async def create_user(user_data: UserCreate, current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create users")

    org_obj_id = await get_user_org(current_user)
    org = orgs_collection.find_one({"_id": org_obj_id})
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")

    # Check org user limit
    allocated_users = org.get("allocated_users", 0)
    total_users = org.get("total_users", 0)
    if allocated_users >= total_users:
        raise HTTPException(status_code=400, detail="User limit reached for this org")

    # Prevent duplicate email
    if users_collection.find_one({"email": user_data.email, "org_id": org_obj_id}):
        raise HTTPException(status_code=400, detail="User with this email already exists in this org")

    # Allocate video credits
    allocated_video_credits = 0
    if user_data.role == "user":
        requested_credits = user_data.allocated_video_credits or 0
        if requested_credits + org.get("allocated_video_credits", 0) > org.get("total_video_credits", 0):
            raise HTTPException(status_code=400, detail="Not enough video credits available in org")
        allocated_video_credits = requested_credits
    else:
        # Admins cannot have credits
        if user_data.allocated_video_credits and user_data.allocated_video_credits > 0:
            raise HTTPException(status_code=400, detail="Admins cannot have video credits")

    user_doc = user_data.dict(exclude_unset=True, by_alias=True)
    user_doc["org_id"] = org_obj_id
    user_doc["allocated_video_credits"] = allocated_video_credits
    user_doc["created_at"] = datetime.utcnow()

    result = users_collection.insert_one(user_doc)
    user_doc["_id"] = str(result.inserted_id)
    user_doc["org_id"] = str(user_doc["org_id"])

    # Update org allocations
    update_fields = {"allocated_users": allocated_users + 1}
    if allocated_video_credits > 0:
        update_fields["allocated_video_credits"] = org.get("allocated_video_credits", 0) + allocated_video_credits
    orgs_collection.update_one({"_id": org_obj_id}, {"$set": update_fields})

    return user_doc

# List Users
@router.get("/", response_model=List[UserOut])
async def list_users(
    role: str = Query(..., pattern="^(user|admin)$"),
    current_user=Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can list users")

    org_obj_id = await get_user_org(current_user)

    users = users_collection.find({"org_id": org_obj_id, "role": role}).to_list(length=100)
    for u in users:
        u["_id"] = str(u["_id"])
        u["org_id"] = str(u["org_id"])
        u.setdefault("allocated_video_credits", 0)
    return users

# Get User
@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: str, current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view users")

    org_obj_id = await get_user_org(current_user)

    user = users_collection.find_one({"_id": ObjectId(user_id), "org_id": org_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found in this org")

    user["_id"] = str(user["_id"])
    user["org_id"] = str(user["org_id"])
    user.setdefault("allocated_video_credits", 0)
    return user


@router.put("/{user_id}/credits", response_model=UserOut)
async def allocate_video_credits(user_id: str, update_data: CreditAllocationUpdate, current_user=Depends(get_current_user)):
    """
    Allocate video credits to a user within the same org.
    Only admins can allocate credits.
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can allocate credits")

    org_obj_id = await get_user_org(current_user)

    # Validate user id
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    # Ensure user exists in same org
    user = users_collection.find_one({"_id": user_obj_id, "org_id": org_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found in this org")

    # Ensure org exists
    org = orgs_collection.find_one({"_id": org_obj_id})
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")

    # Only normal users can have credits
    if user["role"] != "user":
        raise HTTPException(status_code=400, detail="Admins cannot have video credits")

    new_credits = update_data.allocated_video_credits or 0
    old_credits = user.get("allocated_video_credits", 0)

    # Check org-level credit availability
    if org.get("allocated_video_credits", 0) - old_credits + new_credits > org.get("total_video_credits", 0):
        raise HTTPException(status_code=400, detail="Not enough video credits available in org")

    # Update org allocation
    orgs_collection.update_one(
        {"_id": org_obj_id},
        {"$inc": {"allocated_video_credits": new_credits - old_credits}}
    )

    # Update user allocation
    users_collection.update_one(
        {"_id": user_obj_id},
        {"$set": {"allocated_video_credits": new_credits, "updated_at": datetime.utcnow()}}
    )

    user["allocated_video_credits"] = new_credits
    user["updated_at"] = datetime.utcnow()
    user["_id"] = str(user["_id"])
    user["org_id"] = str(user["org_id"])
    return user

# -----------------------------
# Delete User
# -----------------------------
@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete users")

    org_obj_id = await get_user_org(current_user)

    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    user = users_collection.find_one({"_id": user_obj_id, "org_id": org_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found in this org")

    orgs_collection.update_one(
        {"_id": org_obj_id},
        {"$inc": {"allocated_users": -1, "allocated_video_credits": -user.get("allocated_video_credits", 0)}}
    )

    users_collection.delete_one({"_id": user_obj_id})
    return {"detail": "User deleted successfully"}
