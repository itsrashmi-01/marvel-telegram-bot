import re
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

db_client = AsyncIOMotorClient(Config.MONGO_URI)
db = db_client["marvel_db"]

movies_col = db["movies"]
movies_collection = db["movies"]
settings_col = db["settings"]

GENRE_MAP = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    18: "Drama", 14: "Fantasy", 878: "Sci-Fi", 53: "Thriller", 10759: "Action & Adventure", 10765: "Sci-Fi & Fantasy"
}

async def fetch_tmdb_meta(session: aiohttp.ClientSession, title: str):
    tmdb_key = getattr(Config, "TMDB_API_KEY", "")
    if not tmdb_key: return {}
    
    clean_title = re.sub(r'\s*\(\d{4}\)', '', title).strip()
    clean_title = re.sub(r'\s*-?\s*Season \d+', '', clean_title).strip()
    url = f"https://api.themoviedb.org/3/search/multi?api_key={tmdb_key}&query={clean_title}"

    try:
        async with session.get(url) as resp:
            data = await resp.json()
            if data.get("results"):
                top = data["results"][0]
                poster_path = top.get("poster_path")
                backdrop_path = top.get("backdrop_path")
                genres = [GENRE_MAP.get(gid) for gid in top.get("genre_ids", []) if gid in GENRE_MAP]
                
                release_date = top.get("release_date") or top.get("first_air_date") or ""
                release_year = release_date[:4] if release_date else "N/A"

                return {
                    "release_year": release_year,
                    "genres": genres if genres else ["Action", "Sci-Fi", "Adventure"],
                    "images": {
                        "poster_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "",
                        "backdrop_url": f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else ""
                    }
                }
    except Exception as e:
        print(f"TMDB Fetch Error for {title}: {e}")
    return {}

# Removed bot_username parameter since we no longer hardcode links here
async def init_marvel_list(marvel_data: list):
    inserted = 0
    async with aiohttp.ClientSession() as session:
        for item in marvel_data:
            existing = await movies_col.find_one({"watch_order": item["order"]})
            if not existing:
                tmdb_data = await fetch_tmdb_meta(session, item["title"])
                
                doc = {
                    "watch_order": item["order"],
                    "title": item["title"],
                    "release": "",
                    "saga_rank": item.get("saga_rank", 0),
                    "saga": item.get("saga", "Marvel Universe"),
                    "audio": "Pending...",
                    "release_year": tmdb_data.get("release_year", "N/A"),
                    "genres": tmdb_data.get("genres", ["Action", "Sci-Fi", "Adventure"]),
                    "images": tmdb_data.get("images", {"poster_url": "", "backdrop_url": ""}),
                    "status": "Pending",
                    "files": [] # file_id and sizes will live exclusively in here
                }
                await movies_col.insert_one(doc)
                inserted += 1
    return inserted

async def save_movie_files(watch_order: int, new_files: list, audio: str = None, release: str = None):
    movie = await movies_col.find_one({"watch_order": watch_order})
    existing_files = movie.get("files", []) if movie else []

    # Map existing files by quality, then merge/overwrite with newly uploaded files
    files_by_quality = {}
    for idx, f in enumerate(existing_files):
        q_key = f.get("quality") or f"File_{idx + 1}"
        files_by_quality[q_key] = f

    for idx, f in enumerate(new_files):
        q_key = f.get("quality") or f"NewFile_{idx + 1}"
        files_by_quality[q_key] = f

    # Sort qualities cleanly from lowest to highest resolution
    quality_order = {"480p": 1, "540p": 2, "720p": 3, "1080p": 4, "1440p": 5, "2160p": 6, "4K": 6}
    merged_files = sorted(
        files_by_quality.values(),
        key=lambda x: quality_order.get(x.get("quality", ""), 99)
    )

    update_data = {
        "status": "Available",
        "files": merged_files
    }
    if audio:
        update_data["audio"] = audio
    if release:
        update_data["release"] = release

    await movies_col.update_one(
        {"watch_order": watch_order},
        {"$set": update_data},
        upsert=True
    )

async def get_movie_by_order(watch_order: int):
    return await movies_col.find_one({"watch_order": watch_order})

async def get_all_movies():
    cursor = movies_col.find().sort("watch_order", 1)
    return await cursor.to_list(length=200)

# --- MULTI-CHANNEL DATABASE FUNCTIONS ---
async def get_target_channels():
    doc = await settings_col.find_one({"_id": "bot_settings"})
    return doc.get("channels", []) if doc else []

async def add_target_channel(channel_id: int, channel_name: str):
    await settings_col.update_one(
        {"_id": "bot_settings"},
        {"$addToSet": {"channels": {"id": channel_id, "name": channel_name}}},
        upsert=True
    )

async def remove_target_channel(channel_id: int):
    await settings_col.update_one(
        {"_id": "bot_settings"},
        {"$pull": {"channels": {"id": channel_id}}}
    )
