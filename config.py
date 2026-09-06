import os

class Config:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    MONGO_URI = os.environ.get("MONGO_URI", "")
    ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
    PORT = int(os.environ.get("PORT", 8000)) 
    
    DUMP_CHANNEL_ID = int(os.environ.get("DUMP_CHANNEL_ID", 0)) 
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "") 
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "") 
    
    # --- FILE STORE BOT CONFIG ---
    FILE_STORE_BOT_USERNAME = os.environ.get("FILE_STORE_BOT_USERNAME", "") 
    FILE_STORE_BOT_TOKEN = os.environ.get("FILE_STORE_BOT_TOKEN", "")
    
    # --- CUSTOM DOWNLOAD PAGE ---
    # Add this in Render, e.g., https://your-site.blogspot.com/p/download.html
    DOWNLOAD_PAGE_URL = os.environ.get("DOWNLOAD_PAGE_URL", "")
