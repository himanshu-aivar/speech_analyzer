import os
from dotenv import load_dotenv

# Load variables from .env into process environment
load_dotenv()

class Settings:
    def __init__(self):
        # Required environment variables
        self.AWS_ACCESS_KEY = self._get_env("AWS_ACCESS_KEY")
        self.AWS_SECRET_ACCESS_KEY = self._get_env("AWS_SECRET_ACCESS_KEY")
        self.DB_URL = self._get_env("DB_URL")
        self.DATABASE_NAME = self._get_env("DATABASE_NAME")
        self.S3_BUCKET_NAME = self._get_env("S3_BUCKET_NAME")
        self.OPENAI_API_KEY = self._get_env("OPENAI_API_KEY")
        self.ASSEMBLYAI_API_KEY = self._get_env("ASSEMBLYAI_API_KEY")

        # Optional with defaults
        self.ASSEMBLYAI_API_URL = os.getenv("ASSEMBLYAI_API_URL", "https://api.assemblyai.com/v2").strip()
        self.AWS_REGION = os.getenv("AWS_REGION", "ap-south-1").strip()
        self.AUTH_SECRET = os.getenv("AUTH_SECRET", "him").strip()
        self.GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID","HIM").strip()

    def _get_env(self, key: str) -> str:
        """Fetch environment variable, strip whitespace, and fail fast if missing."""
        value = os.getenv(key)
        if not value or not value.strip():
            raise RuntimeError(f"❌ Missing required environment variable: {key}")
        return value.strip()

settings = Settings()
