import asyncio
from hydrogram import Client, compose
from config import Config
async def main():

    print("Starting Multi-Bot Architecture...")

    # ==========================================
    # ADMIN BOT
    # ==========================================

    admin_bot = Client(
        "admin_bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        plugins={
            "root": "plugins"
        }
    )
    # ==========================================
    # FILE SENDER BOT
    # ==========================================

    file_bot = Client(
        "file_bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.FILE_STORE_BOT_TOKEN,
        plugins={
            "root": "file_sender"
        }
    )
    # ==========================================
    # START BOTH BOTS
    # ==========================================

    await compose([
        admin_bot,
        file_bot
    ])


if __name__ == "__main__":
    asyncio.run(main())
