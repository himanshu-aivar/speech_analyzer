from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from settings import settings
from api import videos, processing, results, auth_routes, orgs,users

app = FastAPI(
    title="PitchMentor Backend",
    description="Video upload & analysis service",
    version="1.0.0"
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(processing.router, prefix="/api/videos", tags=["Processing"])
app.include_router(results.router, prefix="/api/videos", tags=["Results"])
app.include_router(auth_routes.router)  # 👈 add this
app.include_router(orgs.router) 
app.include_router(users.router)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(settings.PORT or 8000))
