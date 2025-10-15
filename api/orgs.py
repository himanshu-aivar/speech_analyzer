from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from datetime import datetime

from db import orgs_collection, users_collection, org_licenses_collection
from core.auth import get_current_user

router = APIRouter(prefix="/api/orgs", tags=["Orgs"])


# -------------------------
# Models
# -------------------------
class OrgCreate(BaseModel):
    name: str
    description: Optional[str] = None
    total_users: int = Field(..., gt=0, description="Total users allowed for this org")
    total_video_credits: int = Field(..., gt=0, description="Total video credits for this org")
    admin_email: EmailStr
    admin_name: str


class OrgModel(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    description: Optional[str] = None
    total_users: int
    total_video_credits: int
    allocated_users: int = 0
    allocated_video_credits: int = 0
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


# -------------------------
# Routes (all superadmin only)
# -------------------------
@router.post("/", response_model=OrgModel, status_code=status.HTTP_201_CREATED)
async def create_org(org: OrgCreate, user=Depends(get_current_user)):
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only superadmins can create orgs")

    org_doc = {
        "_id": ObjectId(),
        "name": org.name,
        "description": org.description,
        "total_users": org.total_users,
        "total_video_credits": org.total_video_credits,
        "allocated_users": 0,
        "allocated_video_credits": 0,
        "created_by": str(user["email"]),
        "created_at": datetime.utcnow(),
    }

    orgs_collection.insert_one(org_doc)
    org_doc["_id"] = str(org_doc["_id"])
    return OrgModel(**org_doc)


@router.get("/", response_model=List[OrgModel])
async def list_orgs(user=Depends(get_current_user)):
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only superadmins can list orgs")

    orgs = list(orgs_collection.find())
    for o in orgs:
        o["_id"] = str(o["_id"])
    return [OrgModel(**o) for o in orgs]


@router.get("/{org_id}", response_model=OrgModel)
async def get_org(org_id: str, user=Depends(get_current_user)):
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only superadmins can view orgs")

    try:
        oid = ObjectId(org_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid org id")

    org = orgs_collection.find_one({"_id": oid})
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")

    org["_id"] = str(org["_id"])
    return OrgModel(**org)

class OrgUpdateLicense(BaseModel):
    add_users: Optional[int] = Field(0, ge=0, description="Number of additional users to add")
    add_video_credits: Optional[int] = Field(0, ge=0, description="Number of additional video credits to add")

@router.patch("/{org_id}/license", response_model=OrgModel)
async def update_org_license(org_id: str, update: OrgUpdateLicense, user=Depends(get_current_user)):
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only superadmins can update licenses")

    try:
        oid = ObjectId(org_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid org id")

    org = orgs_collection.find_one({"_id": oid})
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")

    # Update totals
    new_total_users = org.get("total_users", 0) + update.add_users
    new_total_video_credits = org.get("total_video_credits", 0) + update.add_video_credits

    orgs_collection.update_one(
        {"_id": oid},
        {"$set": {
            "total_users": new_total_users,
            "total_video_credits": new_total_video_credits
        }}
    )

    # Record the purchase
    if update.add_users > 0 or update.add_video_credits > 0:
        org_licenses_collection.insert_one({
            "org_id": oid,
            "purchased_by": user["email"],
            "added_users": update.add_users,
            "added_video_credits": update.add_video_credits,
            "created_at": datetime.utcnow()
        })

    org.update({
        "total_users": new_total_users,
        "total_video_credits": new_total_video_credits
    })
    org["_id"] = str(org["_id"])
    return OrgModel(**org)


# -------------------------
# Delete Org (with users cleanup)
# -------------------------
@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(org_id: str, user=Depends(get_current_user)):
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only superadmins can delete orgs")

    try:
        oid = ObjectId(org_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid org id")

    org = orgs_collection.find_one({"_id": oid})
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")

    # Delete org
    orgs_collection.delete_one({"_id": oid})

    # Delete all users related to this org
    users_collection.delete_many({"org_id": str(org_id)})

    return {"detail": "Org and all related users deleted successfully"}


class OrgAdminCreate(BaseModel):
    email: EmailStr
    name: str


@router.post("/{org_id}/admins", status_code=status.HTTP_201_CREATED)
async def add_org_admin(org_id: str, admin: OrgAdminCreate, user=Depends(get_current_user)):
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only superadmins can add org admins")

    try:
        oid = ObjectId(org_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid org id")

    org = orgs_collection.find_one({"_id": oid})
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")

    # Prevent creating a duplicate user in the same org
    if users_collection.find_one({"email": admin.email, "org_id": oid}):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists in this org")


    user_doc = {
        "_id": ObjectId(),
        "org_id": oid,
        "email": admin.email,
        "name": admin.name,
        "role": "admin",
        "created_at": datetime.utcnow(),
        "created_by": user["email"]
    }

    users_collection.insert_one(user_doc)

    user_doc["_id"] = str(user_doc["_id"])
    user_doc["org_id"] = str(user_doc["org_id"])


    return user_doc

