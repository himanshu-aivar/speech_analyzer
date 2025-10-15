from fastapi import APIRouter, HTTPException,Depends
from bson import ObjectId

from db import audio_analysis_collection, text_analysis_collection, image_analysis_collection,videos_collection
from core.auth import get_current_user
router = APIRouter()


def verify_video_ownership(video_id: str, user: dict):
    if not ObjectId.is_valid(video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID")

    video = videos_collection.find_one({"_id": ObjectId(video_id)})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video["user_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this video")

    return video

# --- Audio results ---
@router.get("/{video_id}/results/audio", summary="Get audio analysis results")
async def get_audio_results(video_id: str, user=Depends(get_current_user)):
    video = verify_video_ownership(video_id, user)

    status = video.get("status_audio", "pending")
    if status == "pending":
        raise HTTPException(status_code=404, detail="Audio analysis not started yet")
    if status == "processing":
        raise HTTPException(status_code=202, detail="Audio analysis still in progress")
    if status == "failed":
        raise HTTPException(status_code=500, detail="Audio analysis failed")

    result = audio_analysis_collection.find_one({"video_id": ObjectId(video_id)})
    if not result:
        raise HTTPException(status_code=404, detail="Audio analysis results missing from DB")

    return {
        "video_id": str(result["video_id"]),
        "analysis_results": result["analysis_results"],
        "processed_at": result["processed_at"].isoformat()
    }


# --- Text results ---
@router.get("/{video_id}/results/text", summary="Get text analysis results")
async def get_text_results(video_id: str, user=Depends(get_current_user)):
    video = verify_video_ownership(video_id, user)

    status = video.get("status_text", "pending")
    if status == "pending":
        raise HTTPException(status_code=404, detail="Text analysis not started yet")
    if status == "processing":
        raise HTTPException(status_code=202, detail="Text analysis still in progress")
    if status == "failed":
        raise HTTPException(status_code=500, detail="Text analysis failed")

    result = text_analysis_collection.find_one({"video_id": ObjectId(video_id)})
    if not result:
        raise HTTPException(status_code=404, detail="Text analysis results missing from DB")

    return {
        "video_id": str(result["video_id"]),
        "analysis_results": result["analysis_results"],
        "processed_at": result["processed_at"].isoformat(),
        "description_context": result["description_context"]
    }


# --- Image results ---
@router.get("/{video_id}/results/image", summary="Get image analysis results")
async def get_image_results(video_id: str, user=Depends(get_current_user)):
    video = verify_video_ownership(video_id, user)

    status = video.get("status_image", "pending")
    if status == "pending":
        raise HTTPException(status_code=404, detail="Image analysis not started yet")
    if status == "processing":
        raise HTTPException(status_code=202, detail="Image analysis still in progress")
    if status == "failed":
        raise HTTPException(status_code=500, detail="Image analysis failed")

    result = image_analysis_collection.find_one({"video_id": ObjectId(video_id)})
    if not result:
        raise HTTPException(status_code=404, detail="Image analysis results missing from DB")

    return {
        "video_id": str(result["video_id"]),
        "visual_insights": result["visual_insights"],
        "s3_url": result["s3_url"],
        "description": result["description"]
    }
