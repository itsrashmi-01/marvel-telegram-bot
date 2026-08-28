import os

class Config:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    MONGO_URI = os.environ.get("MONGO_URI", "")
    ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
    PORT = int(os.environ.get("PORT", 8000)) # Koyeb defaults to 8000
