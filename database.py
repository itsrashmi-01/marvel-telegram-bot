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
                    "files": []
                }
                await movies_col.insert_one(doc)
                inserted += 1
    return inserted

def _quality_sort_key(file_obj: dict):
    """Sorts by base resolution (480p -> 720p -> 1080p -> 2160p), then standard before 10bit/HEVC."""
    q_str = (file_obj.get("quality") or "").lower()
    res_order = 99
    if "480p" in q_str: res_order = 1
    elif "540p" in q_str: res_order = 2
    elif "720p" in q_str: res_order = 3
    elif "1080p" in q_str: res_order = 4
    elif "1440p" in q_str: res_order = 5
    elif "2160p" in q_str or "4k" in q_str: res_order = 6

    # Standard encode comes first (0), then 10bit/HEVC variants (1), then numbered duplicates
    variant_order = 1 if ("10bit" in q_str or "hevc" in q_str) else 0
    return (res_order, variant_order, q_str)

async def save_movie_files(watch_order: int, new_files: list, audio: str = None, release: str = None):
    movie = await movies_col.find_one({"watch_order": watch_order})
    existing_files = movie.get("files", []) if movie else []

    # Merge existing files with new files:
    # - Updates if exact same quality label is re-uploaded in a new session
    # - Preserves distinct variants like "1080p" and "1080p 10bit" or "1080p #2"
    files_by_label = {}
    for idx, f in enumerate(existing_files):
        label = f.get("quality") or f"File_{idx + 1}"
        files_by_label[label] = f

    for idx, f in enumerate(new_files):
        label = f.get("quality") or f"NewFile_{idx + 1}"
        files_by_label[label] = f

    merged_files = sorted(files_by_label.values(), key=_quality_sort_key)

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
