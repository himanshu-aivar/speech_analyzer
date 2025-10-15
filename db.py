from pymongo import MongoClient
from settings import settings
# MongoDB Configuration
mongo_client = MongoClient(settings.DB_URL)
db = mongo_client[settings.DATABASE_NAME]
videos_collection = db['videos']
audio_analysis_collection = db['audio_analysis']
text_analysis_collection = db['text_analysis']
image_analysis_collection = db['image_analysis']
users_collection = db["users"]
orgs_collection = db["organisations"]
org_licenses_collection = db["licenses"]