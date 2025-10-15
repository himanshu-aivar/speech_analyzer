# seed.py
from datetime import datetime
from pymongo import MongoClient
from settings import settings

mongo_client = MongoClient(settings.DB_URL)
db = mongo_client[settings.DATABASE_NAME]
users_collection = db['users']

superadmin = {
    "email": "himanshu.g@elyxdigital.com",
    "name": "Himanshu Goyal",
    "image": None,
    "org": "Elyxdigital",    
    "org_id": None,
    "role": "superadmin",
    "created_at": datetime.utcnow()
}

# avoid duplicates
if not users_collection.find_one({"email": superadmin["email"]}):
    users_collection.insert_one(superadmin)
    print("✅ Superadmin user inserted")
else:
    print("⚠️ Superadmin already exists")
