from fastapi import APIRouter, UploadFile, File, Form, HTTPException,Depends
from datetime import datetime
from bson import ObjectId
import uuid

from db import videos_collection, users_collection, orgs_collection
from settings import settings
from core.s3_client import s3_client
from core.logger import logger
from core.auth import get_current_user

router = APIRouter()

async def get_user_org_and_credits(user: dict):
    """Get user's org and remaining video credits"""
    user_doc = users_collection.find_one({"email": user["email"]})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    org = orgs_collection.find_one({"_id": user_doc["org_id"]})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return user_doc, org

# --- Upload a video ---
@router.post("", summary="Upload a video")
async def upload_video(
    title: str = Form("Untitled"),
    description: str = Form(""),
    video: UploadFile = File(...),
    user=Depends(get_current_user)
):
    # ✅ RBAC: Only users can upload videos (admins/superadmins manage the system)
    if user["role"] != "user":
        raise HTTPException(status_code=403, detail="Only users can upload videos. Admins and superadmins manage the system.")
    
    try:
        # ✅ Get user's org and credits
        user_doc, org = await get_user_org_and_credits(user)
        
        # ✅ Check if user has remaining credits
        remaining_credits = user_doc.get("allocated_video_credits", 0)
        if remaining_credits <= 0:
            raise HTTPException(status_code=400, detail="No video credits remaining")
        
        ext = video.filename.split('.')[-1] if '.' in video.filename else 'mp4'
        file_name = f"{uuid.uuid4()}.{ext}"

        s3_client.upload_fileobj(
            video.file,
            settings.S3_BUCKET_NAME,
            file_name,
            ExtraArgs={'ContentType': video.content_type}
        )
        s3_url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{file_name}"

        video_data = {
            "title": title,
            "description": description,
            "s3_url": s3_url,
            "uploaded_at": datetime.utcnow(),
            "user_email": user["email"],
            "user_id": user_doc["_id"],  # ✅ Store user ID for org queries
            "org_id": user_doc["org_id"],  # ✅ Store org ID for isolation
            "status_audio": "pending",
            "status_text": "pending",
            "status_image": "pending",
        }
        result = videos_collection.insert_one(video_data)

        # ✅ Deduct credit after successful upload
        users_collection.update_one(
            {"_id": user_doc["_id"]},
            {"$inc": {"allocated_video_credits": -1}}
        )

        return {"id": str(result.inserted_id), "s3_url": s3_url, "remaining_credits": remaining_credits - 1}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")


# --- List videos ---
@router.get("", summary="List all videos of current user")
async def list_videos(user=Depends(get_current_user)):
    try:
        # ✅ RBAC: Different access based on role
        if user["role"] == "user":
            # Users can only see their own videos
            videos = list(
                videos_collection.find(
                    {"user_email": user["email"]},
                    {"title": 1, "description": 1, "s3_url": 1, "uploaded_at": 1, "status_audio": 1, "status_text": 1, "status_image": 1}
                ).sort("uploaded_at", -1)
            )
        elif user["role"] == "admin":
            # Admins can see all videos in their org
            user_doc = users_collection.find_one({"email": user["email"]})
            if not user_doc:
                raise HTTPException(status_code=404, detail="User not found")
            if not user_doc.get("org_id"):
                raise HTTPException(status_code=404, detail="Admin user not associated with any organization")
            
            videos = list(
                videos_collection.find(
                    {"org_id": user_doc["org_id"]},
                    {"title": 1, "description": 1, "s3_url": 1, "uploaded_at": 1, "user_email": 1, "status_audio": 1, "status_text": 1, "status_image": 1}
                ).sort("uploaded_at", -1)
            )
        elif user["role"] == "superadmin":
            # Superadmins can see all videos
            videos = list(
                videos_collection.find(
                    {},
                    {"title": 1, "description": 1, "s3_url": 1, "uploaded_at": 1, "user_email": 1, "org_id": 1, "status_audio": 1, "status_text": 1, "status_image": 1}
                ).sort("uploaded_at", -1)
            )
        else:
            raise HTTPException(status_code=403, detail="Invalid role")

        for v in videos:
            v["_id"] = str(v["_id"])
            v["uploaded_at"] = v["uploaded_at"].isoformat()
            if "org_id" in v:
                v["org_id"] = str(v["org_id"])

        logger.info(f"Fetched {len(videos)} videos for {user['email']} (role: {user['role']})")
        return {"videos": videos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch videos: {str(e)}")

# --- Get presigned URL ---
@router.get("/{video_id}/presigned-url", summary="Get presigned download URL")
async def get_presigned_url(video_id: str,  user=Depends(get_current_user)):
    try:
        video = videos_collection.find_one({"_id": ObjectId(video_id)})
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # ✅ RBAC: Only users can download videos (admins/superadmins manage the system)
        if user["role"] != "user":
            raise HTTPException(status_code=403, detail="Only users can download videos. Admins and superadmins manage the system.")
        
        # Users can only access their own videos
        if video["user_email"] != user["email"]:
            raise HTTPException(status_code=403, detail="Not authorized to access this video")

        file_key = video["s3_url"].split("/")[-1]
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": file_key},
            ExpiresIn=3600
        )

        logger.debug(f"Generated presigned URL for video {video_id} for user {user['email']} (role: {user['role']})")
        return {"video_id": video_id, "presigned_url": presigned_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")
