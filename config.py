import os

class Config:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    MONGO_URI = os.environ.get("MONGO_URI", "")
    ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
    PORT = int(os.environ.get("PORT", 8000)) # Koyeb / Render defaults
    
    # --- ADDED FOR THE NEW WORKFLOW ---
    DUMP_CHANNEL_ID = int(os.environ.get("DUMP_CHANNEL_ID", 0)) # e.g., -100123456789
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "") # Get free from themoviedb.org
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "") # Your Admin bot username (no @)
    
    # --- NEW FILE STORE BOT ---
    FILE_STORE_BOT_USERNAME = os.environ.get("FILE_STORE_BOT_USERNAME", "") # Your File Bot username (no @)
