import asyncio
from aiohttp import web
from hydrogram import Client, compose
from config import Config

# ==========================================
# DUMMY WEB SERVER (Keeps Render/Koyeb happy)
# ==========================================
async def handle_ping(request):
    return web.Response(text="Bot is running smoothly!")

async def start_webserver():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render automatically sets the PORT environment variable
    site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
    await site.start()
    print(f"Web server started on port {Config.PORT}")

# ==========================================
# 1. ADMIN BOT
# ==========================================
admin_bot = Client(
    "admin_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins") 
)

# ==========================================
# 2. FILE STORE BOT
# ==========================================
file_bot = Client(
    "file_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.FILE_STORE_BOT_TOKEN,
    plugins=dict(root="file_sender") 
)

# ==========================================
# 3. RUN BOTS & WEB SERVER SIMULTANEOUSLY
# ==========================================
async def main():
    print("Starting Multi-Bot Architecture & Web Server...")
    
    # 1. Start the dummy web server so Render detects an open port
    await start_webserver()
    
    # 2. Start both Telegram bots
    await compose([admin_bot, file_bot])

if __name__ == "__main__":
    asyncio.run(main())
