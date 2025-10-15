from fastapi import APIRouter, UploadFile, File, Form, HTTPException,Depends
from datetime import datetime
from bson import ObjectId
import uuid

from db import videos_collection
from settings import settings
from core.s3_client import s3_client
from core.logger import logger
from core.auth import get_current_user

router = APIRouter()

# --- Upload a video ---
@router.post("", summary="Upload a video")
async def upload_video(
    title: str = Form("Untitled"),
    description: str = Form(""),
    video: UploadFile = File(...),
    user=Depends(get_current_user)
):
    try:
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
            "user_email": user["email"],  # ✅ tie video to uploader
            "status_audio": "pending",
            "status_text": "pending",
            "status_image": "pending",
        }
        result = videos_collection.insert_one(video_data)

        return {"id": str(result.inserted_id), "s3_url": s3_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")


# --- List videos ---
@router.get("", summary="List all videos of current user")
async def list_videos(user=Depends(get_current_user)):
    try:
        videos = list(
            videos_collection.find(
                {"user_email": user["email"]},  # ✅ filter by current user
                {"title": 1, "description": 1, "s3_url": 1, "uploaded_at": 1}
            ).sort("uploaded_at", -1)
        )
        for v in videos:
            v["_id"] = str(v["_id"])
            v["uploaded_at"] = v["uploaded_at"].isoformat()

        logger.info(f"Fetched {len(videos)} videos for {user['email']}")
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

        # ✅ Ensure user owns this video
        if video["user_email"] != user["email"]:
            raise HTTPException(status_code=403, detail="Not authorized to access this video")

        file_key = video["s3_url"].split("/")[-1]
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": file_key},
            ExpiresIn=3600
        )

        logger.debug(f"Generated presigned URL for video {video_id}")
        return {"video_id": video_id, "presigned_url": presigned_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")
