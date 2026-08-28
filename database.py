from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

# Initialize MongoDB connection
db_client = AsyncIOMotorClient(Config.MONGO_URI)
db = db_client["marvel_db"]
movies_collection = db["movies"]

async def save_movie(title, file_id, file_type):
    await movies_collection.insert_one({
        "title": title,
        "file_id": file_id,
        "type": file_type
    })
