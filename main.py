import asyncio
from aiohttp import web
from hydrogram import Client, compose
from config import Config
from server import setup_routes

async def start_webserver():
    app = web.Application()
    
    # Load the secure API routes
    setup_routes(app)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render automatically sets the PORT environment variable
    site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
    await site.start()
    print(f"Web server started on port {Config.PORT}")

async def main():
    print("Starting Jarvis 2.0 Architecture...")
    
    # 1. Start the Render API Server
    await start_webserver()
    
    # 2. ADMIN BOT
    admin_bot = Client(
        "admin_bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        plugins=dict(root="plugins") 
    )

    # 3. FILE STORE BOT
    file_bot = Client(
        "file_bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.FILE_STORE_BOT_TOKEN,
        plugins=dict(root="file_sender") 
    )

    # 4. RUN BOTH BOTS SIMULTANEOUSLY
    await compose([admin_bot, file_bot])

if __name__ == "__main__":
    asyncio.run(main())
