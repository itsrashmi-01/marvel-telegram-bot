import hmac
import json
from aiohttp import web
from database import get_movie_by_order, get_products_grouped_by_category
from config import Config


def _is_valid_worker_secret(request: web.Request) -> bool:
    secret_header = request.headers.get("X-Worker-Secret", "")
    expected_secret = getattr(Config, "SECRET_KEY", "") or ""
    if not expected_secret or not secret_header:
        return False
    return hmac.compare_digest(secret_header, expected_secret)


async def handle_ping(request: web.Request) -> web.Response:
    return web.Response(text="Jarvis 2.0 Backend is Online & Secure!")


async def fetch_movie(request: web.Request) -> web.Response:
    # 1. SECURITY: Block anyone trying to access Render directly without the CF Worker secret
    if not _is_valid_worker_secret(request):
        return web.json_response({"error": "Unauthorized Origin"}, status=403)

    try:
        data = await request.json()
        raw_id = data.get("id")

        if raw_id is None or str(raw_id).strip() == "":
            return web.json_response({"error": "Missing ID parameter"}, status=400)

        try:
            movie_id = int(raw_id)
        except (ValueError, TypeError):
            return web.json_response({"error": "Invalid ID parameter"}, status=400)

        # 2. Fetch directly from your MongoDB via motor
        movie = await get_movie_by_order(movie_id)

        if not movie:
            return web.json_response({"document": None})

        # --- DYNAMIC TELEGRAM LINK INJECTION ---
        # Builds a unique deep link per quality index (?start=file_<watch_order>_<idx>)
        # so the File Store Bot delivers the actual video file instead of the web page link
        raw_bot_username = getattr(Config, "FILE_STORE_BOT_USERNAME", "") or ""
        bot_username = raw_bot_username.replace("@", "").strip()

        if isinstance(movie.get("files"), list) and bot_username:
            order = movie.get("watch_order")
            for idx, file_obj in enumerate(movie["files"]):
                if isinstance(file_obj, dict):
                    file_obj["telegram_link"] = f"https://t.me/{bot_username}?start=file_{order}_{idx}"

        # 3. BULLETPROOF JSON SERIALIZATION
        safe_json = json.dumps({"document": movie}, default=str)
        return web.Response(text=safe_json, content_type="application/json")

    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON payload"}, status=400)
    except Exception as e:
        return web.json_response({"error": "Internal Server Error", "details": str(e)}, status=500)


async def fetch_products(request: web.Request) -> web.Response:
    if not _is_valid_worker_secret(request):
        return web.json_response({"error": "Unauthorized Origin"}, status=403)

    try:
        grouped = await get_products_grouped_by_category()
        safe_json = json.dumps(grouped, default=str)
        return web.Response(text=safe_json, content_type="application/json")
    except Exception as e:
        return web.json_response({"error": "Internal Server Error", "details": str(e)}, status=500)


def setup_routes(app: web.Application) -> None:
    app.router.add_get("/", handle_ping)
    app.router.add_post("/api/fetch", fetch_movie)
    app.router.add_post("/api/products", fetch_products)
