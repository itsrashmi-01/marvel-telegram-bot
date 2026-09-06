import asyncio
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from hydrogram import Client, compose
from config import Config

# ==========================================
# 1. ADMIN BOT (Loads everything EXCEPT download.py)
# ==========================================
admin_bot = Client(
    "admin_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(
        root="plugins", 
        exclude=["download"] 
    )
)

# ==========================================
# 2. FILE STORE BOT (Loads ONLY download.py)
# ==========================================
file_bot = Client(
    "file_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.FILE_STORE_BOT_TOKEN,
    plugins=dict(
        root="plugins", 
        include=["download"] 
    )
)

# ==========================================
# 3. RUN BOTH BOTS
# ==========================================
if __name__ == "__main__":
    print("Starting Multi-Bot Architecture...")
    # Run compose directly on the global loop we created at the top
    loop.run_until_complete(compose([admin_bot, file_bot]))
