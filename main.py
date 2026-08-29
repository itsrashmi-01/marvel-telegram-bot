import asyncio
import uvloop
from hydrogram import Client, idle
from config import Config
from server import run_server

async def main():
    # 1. Install the faster uvloop event loop FIRST
    uvloop.install()
    
    # 2. Initialize the bot INSIDE the async function so the loop exists
    app = Client(
        "marvel_bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        plugins=dict(root="plugins") # Automatically loads your plugins folder
    )

    print("Starting Hydrogram bot...")
    await app.start()
    print("Bot started successfully!")
    
    # 3. Start the web server for Render/Koyeb port binding
    await run_server()
    
    # 4. Keep the bot running infinitely
    await idle()
    
    await app.stop()

if __name__ == "__main__":
    # This creates the event loop and runs the main function
    asyncio.run(main())
