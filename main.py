import asyncio
from hydrogram import Client, compose
from config import Config

# ==========================================
# MAIN EXECUTION WRAPPER
# ==========================================
async def main():
    print("Starting Multi-Bot Architecture...")
    
    # 1. ADMIN BOT (Loads everything EXCEPT download.py)
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

    # 2. FILE STORE BOT (Loads ONLY download.py)
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

    # 3. RUN BOTH BOTS SIMULTANEOUSLY
    await compose([admin_bot, file_bot])

if __name__ == "__main__":
    # asyncio.run() creates a fresh event loop natively and handles uvloop correctly
    asyncio.run(main())
