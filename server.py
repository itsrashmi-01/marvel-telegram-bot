from aiohttp import web
from database import get_movie_by_order
from config import Config

async def handle_ping(request):
    return web.Response(text="Jarvis 2.0 Backend is Online & Secure!")

async def fetch_movie(request):
    # 1. SECURITY: Block anyone trying to access Render directly without the CF Worker secret
    secret_header = request.headers.get("X-Worker-Secret")
    expected_secret = getattr(Config, "SECRET_KEY", "generate_a_random_password_here")
    
    if secret_header != expected_secret:
        return web.json_response({"error": "Unauthorized Origin"}, status=403)

    try:
        data = await request.json()
        movie_id = data.get("id")

        if not movie_id:
            return web.json_response({"error": "Missing ID parameter"}, status=400)

        # 2. Fetch directly from your MongoDB via motor
        movie = await get_movie_by_order(int(movie_id))

        if not movie:
            return web.json_response({"document": None})

        # 3. Clean the response (MongoDB ObjectIds are not JSON serializable by default)
        if "_id" in movie:
            movie["_id"] = str(movie["_id"])

        return web.json_response({"document": movie})

    except Exception as e:
        return web.json_response({"error": "Internal Server Error", "details": str(e)}, status=500)

def setup_routes(app):
    app.router.add_get('/', handle_ping)
    app.router.add_post('/api/fetch', fetch_movie)
