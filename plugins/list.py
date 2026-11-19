from hydrogram import Client, filters
from hydrogram.types import Message
from database import movies_col

# --- RAW MARVEL LIST WITH SAGA LABELS & SAGA RANKS (88 TITLES) ---
RAW_MARVEL_LIST = [
    # MCU + DEFENDERS SAGA (Orders 1 - 40 | Saga Ranks 1 - 40)
    {"order": 1, "saga_rank": 1, "saga": "MCU + Defenders Saga", "title": "Captain America: The First Avenger"},
    {"order": 2, "saga_rank": 2, "saga": "MCU + Defenders Saga", "title": "Agent Carter - Seasons 1-2"},
    {"order": 3, "saga_rank": 3, "saga": "MCU + Defenders Saga", "title": "Captain Marvel"},
    {"order": 4, "saga_rank": 4, "saga": "MCU + Defenders Saga", "title": "Iron Man"},
    {"order": 5, "saga_rank": 5, "saga": "MCU + Defenders Saga", "title": "Iron Man 2"},
    {"order": 6, "saga_rank": 6, "saga": "MCU + Defenders Saga", "title": "The Incredible Hulk"},
    {"order": 7, "saga_rank": 7, "saga": "MCU + Defenders Saga", "title": "Thor"},
    {"order": 8, "saga_rank": 8, "saga": "MCU + Defenders Saga", "title": "The Avengers"},
    {"order": 9, "saga_rank": 9, "saga": "MCU + Defenders Saga", "title": "Iron Man 3"},
    {"order": 10, "saga_rank": 10, "saga": "MCU + Defenders Saga", "title": "Thor: The Dark World"},
    {"order": 11, "saga_rank": 11, "saga": "MCU + Defenders Saga", "title": "Captain America: The Winter Soldier"},
    {"order": 12, "saga_rank": 12, "saga": "MCU + Defenders Saga", "title": "Guardians of the Galaxy"},
    {"order": 13, "saga_rank": 13, "saga": "MCU + Defenders Saga", "title": "Guardians of the Galaxy Vol. 2"},
    {"order": 14, "saga_rank": 14, "saga": "MCU + Defenders Saga", "title": "I Am Groot - Season 1"},
    {"order": 15, "saga_rank": 15, "saga": "MCU + Defenders Saga", "title": "I Am Groot - Season 2"},
    {"order": 16, "saga_rank": 16, "saga": "MCU + Defenders Saga", "title": "Daredevil - Season 1"},
    {"order": 17, "saga_rank": 17, "saga": "MCU + Defenders Saga", "title": "Jessica Jones - Season 1"},
    {"order": 18, "saga_rank": 18, "saga": "MCU + Defenders Saga", "title": "Avengers: Age of Ultron"},
    {"order": 19, "saga_rank": 19, "saga": "MCU + Defenders Saga", "title": "Ant-Man"},
    {"order": 20, "saga_rank": 20, "saga": "MCU + Defenders Saga", "title": "Daredevil - Season 2"},
    {"order": 21, "saga_rank": 21, "saga": "MCU + Defenders Saga", "title": "Luke Cage - Season 1"},
    {"order": 22, "saga_rank": 22, "saga": "MCU + Defenders Saga", "title": "Iron Fist - Season 1"},
    {"order": 23, "saga_rank": 23, "saga": "MCU + Defenders Saga", "title": "The Defenders"},
    {"order": 24, "saga_rank": 24, "saga": "MCU + Defenders Saga", "title": "The Punisher - Season 1"},
    {"order": 25, "saga_rank": 25, "saga": "MCU + Defenders Saga", "title": "Captain America: Civil War"},
    {"order": 26, "saga_rank": 26, "saga": "MCU + Defenders Saga", "title": "Black Widow"},
    {"order": 27, "saga_rank": 27, "saga": "MCU + Defenders Saga", "title": "Black Panther"},
    {"order": 28, "saga_rank": 28, "saga": "MCU + Defenders Saga", "title": "Spider-Man: Homecoming"},
    {"order": 29, "saga_rank": 29, "saga": "MCU + Defenders Saga", "title": "Doctor Strange"},
    {"order": 30, "saga_rank": 30, "saga": "MCU + Defenders Saga", "title": "Jessica Jones - Season 2"},
    {"order": 31, "saga_rank": 31, "saga": "MCU + Defenders Saga", "title": "Luke Cage - Season 2"},
    {"order": 32, "saga_rank": 32, "saga": "MCU + Defenders Saga", "title": "Iron Fist - Season 2"},
    {"order": 33, "saga_rank": 33, "saga": "MCU + Defenders Saga", "title": "Daredevil - Season 3"},
    {"order": 34, "saga_rank": 34, "saga": "MCU + Defenders Saga", "title": "The Punisher - Season 2"},
    {"order": 35, "saga_rank": 35, "saga": "MCU + Defenders Saga", "title": "Jessica Jones - Season 3"},
    {"order": 36, "saga_rank": 36, "saga": "MCU + Defenders Saga", "title": "Thor: Ragnarok"},
    {"order": 37, "saga_rank": 37, "saga": "MCU + Defenders Saga", "title": "Ant-Man and the Wasp"},
    {"order": 38, "saga_rank": 38, "saga": "MCU + Defenders Saga", "title": "Avengers: Infinity War"},
    {"order": 39, "saga_rank": 39, "saga": "MCU + Defenders Saga", "title": "Avengers: Endgame"},
    {"order": 40, "saga_rank": 40, "saga": "MCU + Defenders Saga", "title": "Loki - Season 1"},

    # MULTIVERSE SAGA (Orders 41 - 74 & 76 | Saga Ranks 1 - 36)
    {"order": 41, "saga_rank": 1, "saga": "Multiverse Saga", "title": "What If...? - Season 1"},
    {"order": 42, "saga_rank": 2, "saga": "Multiverse Saga", "title": "Marvel Zombies"},
    {"order": 43, "saga_rank": 3, "saga": "Multiverse Saga", "title": "WandaVision"},
    {"order": 44, "saga_rank": 4, "saga": "Multiverse Saga", "title": "Shang-Chi and the Legend of the Ten Rings"},
    {"order": 45, "saga_rank": 5, "saga": "Multiverse Saga", "title": "The Falcon and the Winter Soldier"},
    {"order": 46, "saga_rank": 6, "saga": "Multiverse Saga", "title": "Spider-Man: Far From Home"},
    {"order": 47, "saga_rank": 7, "saga": "Multiverse Saga", "title": "Eternals"},
    {"order": 48, "saga_rank": 8, "saga": "Multiverse Saga", "title": "Spider-Man: No Way Home"},
    {"order": 49, "saga_rank": 9, "saga": "Multiverse Saga", "title": "Doctor Strange in the Multiverse of Madness"},
    {"order": 50, "saga_rank": 10, "saga": "Multiverse Saga", "title": "Hawkeye"},
    {"order": 51, "saga_rank": 11, "saga": "Multiverse Saga", "title": "Moon Knight"},
    {"order": 52, "saga_rank": 12, "saga": "Multiverse Saga", "title": "Black Panther: Wakanda Forever"},
    {"order": 53, "saga_rank": 13, "saga": "Multiverse Saga", "title": "Echo"},
    {"order": 54, "saga_rank": 14, "saga": "Multiverse Saga", "title": "She-Hulk: Attorney at Law"},
    {"order": 55, "saga_rank": 15, "saga": "Multiverse Saga", "title": "Ms. Marvel"},
    {"order": 56, "saga_rank": 16, "saga": "Multiverse Saga", "title": "Thor: Love and Thunder"},
    {"order": 57, "saga_rank": 17, "saga": "Multiverse Saga", "title": "Ironheart"},
    {"order": 58, "saga_rank": 18, "saga": "Multiverse Saga", "title": "Werewolf by Night"},
    {"order": 59, "saga_rank": 19, "saga": "Multiverse Saga", "title": "The Guardians of the Galaxy Holiday Special"},
    {"order": 60, "saga_rank": 20, "saga": "Multiverse Saga", "title": "Ant-Man and the Wasp: Quantumania"},
    {"order": 61, "saga_rank": 21, "saga": "Multiverse Saga", "title": "Guardians of the Galaxy Vol. 3"},
    {"order": 62, "saga_rank": 22, "saga": "Multiverse Saga", "title": "Secret Invasion"},
    {"order": 63, "saga_rank": 23, "saga": "Multiverse Saga", "title": "The Marvels"},
    {"order": 64, "saga_rank": 24, "saga": "Multiverse Saga", "title": "Loki - Season 2"},
    {"order": 65, "saga_rank": 25, "saga": "Multiverse Saga", "title": "What If...? - Seasons 2-3"},
    {"order": 66, "saga_rank": 26, "saga": "Multiverse Saga", "title": "Agatha All Along"},
    {"order": 67, "saga_rank": 27, "saga": "Multiverse Saga", "title": "Daredevil: Born Again - Season 1"},
    {"order": 68, "saga_rank": 28, "saga": "Multiverse Saga", "title": "Captain America: Brave New World"},
    {"order": 69, "saga_rank": 29, "saga": "Multiverse Saga", "title": "Thunderbolts*"},
    {"order": 70, "saga_rank": 30, "saga": "Multiverse Saga", "title": "Wonder Man"},
    {"order": 71, "saga_rank": 31, "saga": "Multiverse Saga", "title": "Deadpool & Wolverine"},
    {"order": 72, "saga_rank": 32, "saga": "Multiverse Saga", "title": "Daredevil: Born Again - Season 2"},
    {"order": 73, "saga_rank": 33, "saga": "Multiverse Saga", "title": "The Punisher: One Last Kill"},
    {"order": 74, "saga_rank": 34, "saga": "Multiverse Saga", "title": "Spider-Man: Brand New Day"},
    {"order": 75, "saga_rank": 35, "saga": "Multiverse Saga", "title": "VisionQuest"},

    # FANTASTIC FOUR UNIVERSE (Order 76 | Saga Rank 1)
    {"order": 76, "saga_rank": 1, "saga": "Fantastic Four Universe", "title": "The Fantastic Four: First Steps"},

    # X-MEN / FOX UNIVERSE (Orders 77 - 88 | Saga Ranks 1 - 12)
    {"order": 77, "saga_rank": 1, "saga": "X-Men / Fox Universe", "title": "X-Men: First Class"},
    {"order": 78, "saga_rank": 2, "saga": "X-Men / Fox Universe", "title": "X-Men Origins: Wolverine"},
    {"order": 79, "saga_rank": 3, "saga": "X-Men / Fox Universe", "title": "X-Men"},
    {"order": 80, "saga_rank": 4, "saga": "X-Men / Fox Universe", "title": "X2: X-Men United"},
    {"order": 81, "saga_rank": 5, "saga": "X-Men / Fox Universe", "title": "X-Men: The Last Stand"},
    {"order": 82, "saga_rank": 6, "saga": "X-Men / Fox Universe", "title": "The Wolverine"},
    {"order": 83, "saga_rank": 7, "saga": "X-Men / Fox Universe", "title": "X-Men: Days of Future Past"},
    {"order": 84, "saga_rank": 8, "saga": "X-Men / Fox Universe", "title": "X-Men: Apocalypse"},
    {"order": 85, "saga_rank": 9, "saga": "X-Men / Fox Universe", "title": "Dark Phoenix"},
    {"order": 86, "saga_rank": 10, "saga": "X-Men / Fox Universe", "title": "Deadpool"},
    {"order": 87, "saga_rank": 11, "saga": "X-Men / Fox Universe", "title": "Deadpool 2"},
    {"order": 88, "saga_rank": 12, "saga": "X-Men / Fox Universe", "title": "Logan"}
]


@Client.on_message(filters.command("list") & filters.private)
async def list_movies(client: Client, message: Message):
    status_msg = await message.reply_text("⏳ Checking upload status from MongoDB...")

    uploaded_movies = await movies_col.find(
        {"files": {"$exists": True, "$not": {"$size": 0}}},
        {"watch_order": 1}
    ).to_list(length=300)

    uploaded_set = {doc["watch_order"] for doc in uploaded_movies}

    output = f"🎬 **MARVEL WATCH ORDER ({len(RAW_MARVEL_LIST)})**\n"
    output += "✔ = Available | ✘ = Pending Upload\n\n"

    current_saga = ""
    for item in RAW_MARVEL_LIST:
        if item["saga"] != current_saga:
            current_saga = item["saga"]
            output += f"\n📂 **{current_saga.upper()}**\n"

        order = item["order"]
        saga_rank = item["saga_rank"]
        title = item["title"]
        mark = "✔" if order in uploaded_set else "✘"
        output += f"{mark} `{saga_rank}.` {title} *(O:{order})*\n"

    await status_msg.delete()

    if len(output) > 4096:
        chunks = [output[i:i + 4000] for i in range(0, len(output), 4000)]
        for chunk in chunks:
            await message.reply_text(chunk)
    else:
        await message.reply_text(output)
