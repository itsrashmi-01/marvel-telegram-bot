import os

class Config:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    MONGO_URI = os.environ.get("MONGO_URI", "")
    ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
    PORT = int(os.environ.get("PORT", 8000)) # Koyeb defaults to 8000
    
    # --- ADDED FOR THE NEW WORKFLOW ---
    DUMP_CHANNEL_ID = int(os.environ.get("DUMP_CHANNEL_ID", 0)) # e.g., -100123456789
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "") # Get free from themoviedb.org
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "") # e.g., YourBotName without the @
