from aiohttp import web
from config import Config

async def health_check(request):
    return web.Response(text="Marvel Bot is running smoothly on Koyeb!")

async def run_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Bind to 0.0.0.0 so Koyeb can route external traffic to it
    site = web.TCPSite(runner, "0.0.0.0", Config.PORT)
    await site.start()
    print(f"Web server started on port {Config.PORT}")
