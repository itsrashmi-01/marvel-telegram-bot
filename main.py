import asyncio
import uvloop
from hydrogram import Client, idle
from config import Config
from server import run_server

# Use uvloop for faster async performance
uvloop.install()

app = Client(
    "marvel_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins") # Automatically loads files from the plugins folder
)

async def main():
    print("Starting Hydrogram bot...")
    await app.start()
    print("Bot started successfully!")
    
    # Start the aiohttp web server for Koyeb health checks
    await run_server()
    
    # Keep the bot running
    await idle()
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
