import asyncio
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
        exclude=["download"] # Prevents the admin bot from handling deep links
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
        include=["download"] # Forces this bot to strictly act as a file provider
    )
)

# ==========================================
# 3. RUN BOTH BOTS
# ==========================================
async def main():
    print("Starting Multi-Bot Architecture...")
    # compose() gracefully runs multiple clients simultaneously
    await compose([admin_bot, file_bot])

if __name__ == "__main__":
    asyncio.run(main())
