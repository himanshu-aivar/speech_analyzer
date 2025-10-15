from fastapi import APIRouter, HTTPException, BackgroundTasks,Depends
from bson import ObjectId

from db import videos_collection
from processors.audio_processor import process_video_audio
from processors.text_processor import process_video_text
from processors.visual_processor import process_visual_analysis
from settings import settings
from core.auth import get_current_user
router = APIRouter()

# --- Process audio ---
@router.post("/{video_id}/process/audio", summary="Trigger audio analysis")
async def process_audio(video_id: str, background_tasks: BackgroundTasks,user=Depends(get_current_user)):
    video = videos_collection.find_one({"_id": ObjectId(video_id)})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video["user_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this video")

    # Check if already processing or completed
    if video.get("status_audio") in ["processing", "completed"]:
        raise HTTPException(status_code=400, detail=f"Audio processing already {video['status_audio']}")

    # Mark as processing
    videos_collection.update_one(
        {"_id": ObjectId(video_id)},
        {"$set": {"status_audio": "processing"}}
    )

    s3_url = video["s3_url"]
    s3_key = s3_url.split("/")[-1]
    background_tasks.add_task(process_video_audio, video_id, settings.S3_BUCKET_NAME, s3_key)

    return {"message": f"Audio processing started for video {video_id}"}


# --- Process text ---
@router.post("/{video_id}/process/text", summary="Trigger text analysis")
async def process_text(video_id: str, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    video = videos_collection.find_one({"_id": ObjectId(video_id)})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video["user_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this video")
    # Check if already processing or completed
    if video.get("status_text") in ["processing", "completed"]:
        raise HTTPException(status_code=400, detail=f"Text processing already {video['status_text']}")

    # Mark as processing
    videos_collection.update_one(
        {"_id": ObjectId(video_id)},
        {"$set": {"status_text": "processing"}}
    )

    s3_url = video["s3_url"]
    description = video.get("description", "")
    background_tasks.add_task(process_video_text, video_id, s3_url, description)

    return {"message": f"Text processing started for video {video_id}"}


# --- Process image ---
@router.post("/{video_id}/process/image", summary="Trigger image analysis")
async def process_image(video_id: str, background_tasks: BackgroundTasks,user=Depends(get_current_user)):
    video = videos_collection.find_one({"_id": ObjectId(video_id)})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video["user_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this video")

    # Check if already processing or completed
    if video.get("status_image") in ["processing", "completed"]:
        raise HTTPException(status_code=400, detail=f"Image processing already {video['status_image']}")

    # Mark as processing
    videos_collection.update_one(
        {"_id": ObjectId(video_id)},
        {"$set": {"status_image": "processing"}}
    )

    s3_url = video["s3_url"]
    description = video.get("description", "")
    background_tasks.add_task(process_visual_analysis, video_id, s3_url, description)

    return {"message": f"Image processing started for video {video_id}"}
