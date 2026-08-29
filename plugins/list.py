from hydrogram import Client, filters
from hydrogram.types import Message
from database import movies_col

# --- SIMPLIFIED RAW MARVEL LIST (Only Order and Title) ---
RAW_MARVEL_LIST = [
    {"order": 1, "title": "Captain America: The First Avenger"},
    {"order": 2, "title": "Captain Marvel"},
    {"order": 3, "title": "Iron Man"},
    {"order": 4, "title": "Iron Man 2"},
    {"order": 5, "title": "The Incredible Hulk"},
    {"order": 6, "title": "Thor"},
    {"order": 7, "title": "The Avengers"},
    {"order": 8, "title": "Iron Man 3"},
    {"order": 9, "title": "Thor: The Dark World"},
    {"order": 10, "title": "Captain America: The Winter Soldier"},
    {"order": 11, "title": "Guardians of the Galaxy"},
    {"order": 12, "title": "Guardians of the Galaxy Vol. 2"},
    {"order": 13, "title": "I Am Groot - Season 1"},
    {"order": 14, "title": "I Am Groot - Season 2"},
    {"order": 15, "title": "Daredevil - Season 1"},
    {"order": 16, "title": "Jessica Jones - Season 1"},
    {"order": 17, "title": "Avengers: Age of Ultron"},
    {"order": 18, "title": "Daredevil - Season 2"},
    {"order": 19, "title": "Luke Cage - Season 1"},
    {"order": 20, "title": "Iron Fist - Season 1"},
    {"order": 21, "title": "The Defenders"},
    {"order": 22, "title": "The Punisher - Season 1"},
    {"order": 23, "title": "Captain America: Civil War"},
    {"order": 24, "title": "Black Widow"},
    {"order": 25, "title": "Black Panther"},
    {"order": 26, "title": "Spider-Man: Homecoming"},
    {"order": 27, "title": "Doctor Strange"},
    {"order": 28, "title": "Jessica Jones - Season 2"},
    {"order": 29, "title": "Luke Cage - Season 2"},
    {"order": 30, "title": "Iron Fist - Season 2"},
    {"order": 31, "title": "Daredevil - Season 3"},
    {"order": 32, "title": "The Punisher - Season 2"},
    {"order": 33, "title": "Jessica Jones - Season 3"},
    {"order": 34, "title": "Thor: Ragnarok"},
    {"order": 35, "title": "Ant-Man and the Wasp"},
    {"order": 36, "title": "Avengers: Infinity War"},
    {"order": 37, "title": "Avengers: Endgame"},
    {"order": 38, "title": "Loki - Season 1"},
    {"order": 39, "title": "What If...? - Season 1"},
    {"order": 40, "title": "WandaVision"},
    {"order": 41, "title": "Shang-Chi and the Legend of the Ten Rings"},
    {"order": 42, "title": "The Falcon and the Winter Soldier"},
    {"order": 43, "title": "Spider-Man: Far From Home"},
    {"order": 44, "title": "Eternals"},
    {"order": 45, "title": "Spider-Man: No Way Home"},
    {"order": 46, "title": "Doctor Strange in the Multiverse of Madness"},
    {"order": 47, "title": "Hawkeye"},
    {"order": 48, "title": "Moon Knight"},
    {"order": 49, "title": "Black Panther: Wakanda Forever"},
    {"order": 50, "title": "Echo"},
    {"order": 51, "title": "She-Hulk: Attorney at Law"},
    {"order": 52, "title": "Ms. Marvel"},
    {"order": 53, "title": "Thor: Love and Thunder"},
    {"order": 54, "title": "Werewolf by Night"},
    {"order": 55, "title": "The Guardians of the Galaxy Holiday Special"},
    {"order": 56, "title": "Ant-Man and the Wasp: Quantumania"},
    {"order": 57, "title": "Guardians of the Galaxy Vol. 3"},
    {"order": 58, "title": "Secret Invasion"},
    {"order": 59, "title": "The Marvels"},
    {"order": 60, "title": "Loki - Season 2"},
    {"order": 61, "title": "What If...? - Season 2"},
    {"order": 62, "title": "What If...? - Season 3"},
    {"order": 63, "title": "Agatha All Along"},
    {"order": 64, "title": "Daredevil: Born Again - Season 1"},
    {"order": 65, "title": "Captain America: Brave New World"},
    {"order": 66, "title": "Thunderbolts*"},
    {"order": 67, "title": "Daredevil: Born Again - Season 2"},
    {"order": 68, "title": "Spider-Man: Brand New Day"},
    {"order": 69, "title": "The Fantastic Four: First Steps"},
    {"order": 70, "title": "X-Men: First Class"},
    {"order": 71, "title": "X-Men: Days of Future Past"},
    {"order": 72, "title": "X-Men: Apocalypse"},
    {"order": 73, "title": "Dark Phoenix"},
    {"order": 74, "title": "X-Men"},
    {"order": 75, "title": "X2: X-Men United"},
    {"order": 76, "title": "X-Men: The Last Stand"},
    {"order": 77, "title": "X-Men Origins: Wolverine"},
    {"order": 78, "title": "The Wolverine"},
    {"order": 79, "title": "Logan"},
    {"order": 80, "title": "Deadpool"},
    {"order": 81, "title": "Deadpool 2"},
    {"order": 82, "title": "Deadpool & Wolverine"}
]

@Client.on_message(filters.command("list") & filters.private)
async def list_movies(client: Client, message: Message):
    status_msg = await message.reply_text("⏳ Checking upload status from MongoDB...")
    
    # Query uploaded items
    uploaded_movies = await movies_col.find(
        {"files": {"$exists": True, "$not": {"$size": 0}}},
        {"watch_order": 1}
    ).to_list(length=200)
    
    uploaded_set = {doc["watch_order"] for doc in uploaded_movies}
    
    output = "🎬 **MARVEL COMPLETE WATCH ORDER & STATUS**\n"
    output += "🟢 = Available | 🔴 = Pending Upload\n\n"
    
    for item in RAW_MARVEL_LIST:
        order = item["order"]
        title = item["title"]
        
        if order in uploaded_set:
            output += f"🟢 `{order}.` {title}\n"
        else:
            output += f"🔴 `{order}.` {title}\n"

    await status_msg.delete()

    if len(output) > 4096:
        chunks = [output[i:i+4000] for i in range(0, len(output), 4000)]
        for chunk in chunks:
            await message.reply_text(chunk)
    else:
        await message.reply_text(output)
