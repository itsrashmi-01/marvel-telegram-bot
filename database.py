import re
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

# Initialize MongoDB connection
db_client = AsyncIOMotorClient(Config.MONGO_URI)
db = db_client["marvel_db"]

# Define BOTH variable names so all plugins work perfectly without crashing
movies_col = db["movies"]
movies_collection = db["movies"]
settings_col = db["settings"]  # Added for Channel Management

# TMDB Genre ID mapping
GENRE_MAP = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    18: "Drama", 14: "Fantasy", 878: "Sci-Fi", 53: "Thriller", 10759: "Action & Adventure", 10765: "Sci-Fi & Fantasy"
}

async def fetch_tmdb_meta(session: aiohttp.ClientSession, title: str):
    """Fetches posters, backdrop, overview, rating, and genres from TMDB."""
    tmdb_key = getattr(Config, "TMDB_API_KEY", "")
    if not tmdb_key:
        return {}
    
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

                return {
                    "overview": top.get("overview", "No synopsis available."),
                    "rating": round(top.get("vote_average", 0.0), 1),
                    "genres": genres if genres else ["Action", "Sci-Fi", "Adventure"],
                    "images": {
                        "poster_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "",
                        "backdrop_url": f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else ""
                    }
                }
    except Exception as e:
        print(f"TMDB Fetch Error for {title}: {e}")
    return {}

async def init_marvel_list(marvel_data: list, bot_username: str = ""):
    """Seeds the 82 Marvel movies into MongoDB and automatically grabs metadata."""
    inserted = 0
    async with aiohttp.ClientSession() as session:
        for item in marvel_data:
            existing = await movies_col.find_one({"watch_order": item["order"]})
            if not existing:
                tmdb_data = await fetch_tmdb_meta(session, item["title"])
                
                doc = {
                    "watch_order": item["order"],
                    "title": item["title"],
                    "saga_rank": item.get("saga_rank", 0),
                    "saga": item.get("saga", "Marvel Universe"),
                    "language": "English + Hindi",
                    "genres": tmdb_data.get("genres", ["Action", "Sci-Fi", "Adventure"]),
                    "rating": tmdb_data.get("rating", 0.0),
                    "overview": tmdb_data.get("overview", "Overview coming soon."),
                    "images": tmdb_data.get("images", {"poster_url": "", "backdrop_url": ""}),
                    "links": {
                        "trailer_url": "",
                        "stream_url": "",
                        "telegram_deep_link": f"https://t.me/{bot_username}?start=get_{item['order']}" if bot_username else ""
                    },
                    "status": "Pending",
                    "files": []
                }
                await movies_col.insert_one(doc)
                inserted += 1
    return inserted

async def add_or_update_file(watch_order: int, quality: str, file_size: str, file_id: str, download_url: str = ""):
    """Adds or updates a single file quality resolution with download link."""
    file_entry = {
        "quality": quality,
        "file_size": file_size,
        "file_id": file_id,
        "download_url": download_url
    }
    
    # 1. Remove existing entry of the same quality to avoid duplicates
    await movies_col.update_one(
        {"watch_order": watch_order},
        {"$pull": {"files": {"quality": quality}}}
    )
    
    # 2. Append the new quality file and mark status as Available
    await movies_col.update_one(
        {"watch_order": watch_order},
        {
            "$push": {"files": file_entry},
            "$set": {"status": "Available"}
        }
    )

async def save_movie_files(watch_order: int, new_files: list):
    """Saves multiple files with their Telegram IDs and MediaFire links."""
    for f in new_files:
        # Remove existing entry of the same quality to avoid duplicates
        await movies_col.update_one(
            {"watch_order": watch_order},
            {"$pull": {"files": {"quality": f["quality"]}}}
        )
        # Push the new file object
        await movies_col.update_one(
            {"watch_order": watch_order},
            {
                "$push": {"files": f},
                "$set": {"status": "Available"}
            }
        )

async def get_movie_by_order(watch_order: int):
    """Fetch movie details by its watch order number."""
    return await movies_col.find_one({"watch_order": watch_order})

async def get_all_movies():
    """Fetch all movies sorted by watch order."""
    cursor = movies_col.find().sort("watch_order", 1)
    return await cursor.to_list(length=200)

async def get_target_channel():
    """Fetches the saved channel ID from the database."""
    doc = await settings_col.find_one({"_id": "bot_settings"})
    return doc.get("channel_id") if doc else None

async def set_target_channel(channel_id: int):
    """Saves or updates the channel ID in the database."""
    await settings_col.update_one(
        {"_id": "bot_settings"},
        {"$set": {"channel_id": channel_id}},
        upsert=True
    )
