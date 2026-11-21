from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import UpdateOne
from config import Config
from database import movies_col

# --- RAW MARVEL LIST WITH SAGA LABELS & SAGA RANKS ---
RAW_MARVEL_LIST = [
    # MCU + DEFENDERS SAGA (Ranks 1 - 37)
    {"order": 1, "saga_rank": 1, "saga": "MCU + Defenders Saga", "title": "Captain America: The First Avenger"},
    {"order": 2, "saga_rank": 2, "saga": "MCU + Defenders Saga", "title": "Captain Marvel"},
    {"order": 3, "saga_rank": 3, "saga": "MCU + Defenders Saga", "title": "Iron Man"},
    {"order": 4, "saga_rank": 4, "saga": "MCU + Defenders Saga", "title": "Iron Man 2"},
    {"order": 5, "saga_rank": 5, "saga": "MCU + Defenders Saga", "title": "The Incredible Hulk"},
    {"order": 6, "saga_rank": 6, "saga": "MCU + Defenders Saga", "title": "Thor"},
    {"order": 7, "saga_rank": 7, "saga": "MCU + Defenders Saga", "title": "The Avengers"},
    {"order": 8, "saga_rank": 8, "saga": "MCU + Defenders Saga", "title": "Iron Man 3"},
    {"order": 9, "saga_rank": 9, "saga": "MCU + Defenders Saga", "title": "Thor: The Dark World"},
    {"order": 10, "saga_rank": 10, "saga": "MCU + Defenders Saga", "title": "Captain America: The Winter Soldier"},
    {"order": 11, "saga_rank": 11, "saga": "MCU + Defenders Saga", "title": "Guardians of the Galaxy"},
    {"order": 12, "saga_rank": 12, "saga": "MCU + Defenders Saga", "title": "Guardians of the Galaxy Vol. 2"},
    {"order": 13, "saga_rank": 13, "saga": "MCU + Defenders Saga", "title": "I Am Groot - Season 1"},
    {"order": 14, "saga_rank": 14, "saga": "MCU + Defenders Saga", "title": "I Am Groot - Season 2"},
    {"order": 15, "saga_rank": 15, "saga": "MCU + Defenders Saga", "title": "Daredevil - Season 1"},
    {"order": 16, "saga_rank": 16, "saga": "MCU + Defenders Saga", "title": "Jessica Jones - Season 1"},
    {"order": 17, "saga_rank": 17, "saga": "MCU + Defenders Saga", "title": "Avengers: Age of Ultron"},
    {"order": 18, "saga_rank": 18, "saga": "MCU + Defenders Saga", "title": "Daredevil - Season 2"},
    {"order": 19, "saga_rank": 19, "saga": "MCU + Defenders Saga", "title": "Luke Cage - Season 1"},
    {"order": 20, "saga_rank": 20, "saga": "MCU + Defenders Saga", "title": "Iron Fist - Season 1"},
    {"order": 21, "saga_rank": 21, "saga": "MCU + Defenders Saga", "title": "The Defenders"},
    {"order": 22, "saga_rank": 22, "saga": "MCU + Defenders Saga", "title": "The Punisher - Season 1"},
    {"order": 23, "saga_rank": 23, "saga": "MCU + Defenders Saga", "title": "Captain America: Civil War"},
    {"order": 24, "saga_rank": 24, "saga": "MCU + Defenders Saga", "title": "Black Widow"},
    {"order": 25, "saga_rank": 25, "saga": "MCU + Defenders Saga", "title": "Black Panther"},
    {"order": 26, "saga_rank": 26, "saga": "MCU + Defenders Saga", "title": "Spider-Man: Homecoming"},
    {"order": 27, "saga_rank": 27, "saga": "MCU + Defenders Saga", "title": "Doctor Strange"},
    {"order": 28, "saga_rank": 28, "saga": "MCU + Defenders Saga", "title": "Jessica Jones - Season 2"},
    {"order": 29, "saga_rank": 29, "saga": "MCU + Defenders Saga", "title": "Luke Cage - Season 2"},
    {"order": 30, "saga_rank": 30, "saga": "MCU + Defenders Saga", "title": "Iron Fist - Season 2"},
    {"order": 31, "saga_rank": 31, "saga": "MCU + Defenders Saga", "title": "Daredevil - Season 3"},
    {"order": 32, "saga_rank": 32, "saga": "MCU + Defenders Saga", "title": "The Punisher - Season 2"},
    {"order": 33, "saga_rank": 33, "saga": "MCU + Defenders Saga", "title": "Jessica Jones - Season 3"},
    {"order": 34, "saga_rank": 34, "saga": "MCU + Defenders Saga", "title": "Thor: Ragnarok"},
    {"order": 35, "saga_rank": 35, "saga": "MCU + Defenders Saga", "title": "Ant-Man and the Wasp"},
    {"order": 36, "saga_rank": 36, "saga": "MCU + Defenders Saga", "title": "Avengers: Infinity War"},
    {"order": 37, "saga_rank": 37, "saga": "MCU + Defenders Saga", "title": "Avengers: Endgame"},

    # MULTIVERSE SAGA (Ranks 1 - 32)
    {"order": 38, "saga_rank": 1, "saga": "Multiverse Saga", "title": "Loki - Season 1"},
    {"order": 39, "saga_rank": 2, "saga": "Multiverse Saga", "title": "What If...? - Season 1"},
    {"order": 40, "saga_rank": 3, "saga": "Multiverse Saga", "title": "WandaVision"},
    {"order": 41, "saga_rank": 4, "saga": "Multiverse Saga", "title": "Shang-Chi and the Legend of the Ten Rings"},
    {"order": 42, "saga_rank": 5, "saga": "Multiverse Saga", "title": "The Falcon and the Winter Soldier"},
    {"order": 43, "saga_rank": 6, "saga": "Multiverse Saga", "title": "Spider-Man: Far From Home"},
    {"order": 44, "saga_rank": 7, "saga": "Multiverse Saga", "title": "Eternals"},
    {"order": 45, "saga_rank": 8, "saga": "Multiverse Saga", "title": "Spider-Man: No Way Home"},
    {"order": 46, "saga_rank": 9, "saga": "Multiverse Saga", "title": "Doctor Strange in the Multiverse of Madness"},
    {"order": 47, "saga_rank": 10, "saga": "Multiverse Saga", "title": "Hawkeye"},
    {"order": 48, "saga_rank": 11, "saga": "Multiverse Saga", "title": "Moon Knight"},
    {"order": 49, "saga_rank": 12, "saga": "Multiverse Saga", "title": "Black Panther: Wakanda Forever"},
    {"order": 50, "saga_rank": 13, "saga": "Multiverse Saga", "title": "Echo"},
    {"order": 51, "saga_rank": 14, "saga": "Multiverse Saga", "title": "She-Hulk: Attorney at Law"},
    {"order": 52, "saga_rank": 15, "saga": "Multiverse Saga", "title": "Ms. Marvel"},
    {"order": 53, "saga_rank": 16, "saga": "Multiverse Saga", "title": "Thor: Love and Thunder"},
    {"order": 54, "saga_rank": 17, "saga": "Multiverse Saga", "title": "Werewolf by Night"},
    {"order": 55, "saga_rank": 18, "saga": "Multiverse Saga", "title": "The Guardians of the Galaxy Holiday Special"},
    {"order": 56, "saga_rank": 19, "saga": "Multiverse Saga", "title": "Ant-Man and the Wasp: Quantumania"},
    {"order": 57, "saga_rank": 20, "saga": "Multiverse Saga", "title": "Guardians of the Galaxy Vol. 3"},
    {"order": 58, "saga_rank": 21, "saga": "Multiverse Saga", "title": "Secret Invasion"},
    {"order": 59, "saga_rank": 22, "saga": "Multiverse Saga", "title": "The Marvels"},
    {"order": 60, "saga_rank": 23, "saga": "Multiverse Saga", "title": "Loki - Season 2"},
    {"order": 61, "saga_rank": 24, "saga": "Multiverse Saga", "title": "What If...? - Season 2"},
    {"order": 62, "saga_rank": 25, "saga": "Multiverse Saga", "title": "What If...? - Season 3"},
    {"order": 63, "saga_rank": 26, "saga": "Multiverse Saga", "title": "Agatha All Along"},
    {"order": 64, "saga_rank": 27, "saga": "Multiverse Saga", "title": "Daredevil: Born Again - Season 1"},
    {"order": 65, "saga_rank": 28, "saga": "Multiverse Saga", "title": "Captain America: Brave New World"},
    {"order": 66, "saga_rank": 29, "saga": "Multiverse Saga", "title": "Thunderbolts*"},
    {"order": 67, "saga_rank": 30, "saga": "Multiverse Saga", "title": "Daredevil: Born Again - Season 2"},
    {"order": 68, "saga_rank": 31, "saga": "Multiverse Saga", "title": "Spider-Man: Brand New Day"},
    {"order": 69, "saga_rank": 32, "saga": "Multiverse Saga", "title": "Vision Quest"},

    # FANTASTIC FOUR UNIVERSE (Rank 1)
    {"order": 70, "saga_rank": 1, "saga": "Fantastic Four Universe", "title": "The Fantastic Four: First Steps"},

    # X-MEN / FOX UNIVERSE (Ranks 1 - 13)
    {"order": 71, "saga_rank": 1, "saga": "X-Men / Fox Universe", "title": "X-Men: First Class"},
    {"order": 72, "saga_rank": 2, "saga": "X-Men / Fox Universe", "title": "X-Men: Days of Future Past"},
    {"order": 73, "saga_rank": 3, "saga": "X-Men / Fox Universe", "title": "X-Men: Apocalypse"},
    {"order": 74, "saga_rank": 4, "saga": "X-Men / Fox Universe", "title": "Dark Phoenix"},
    {"order": 75, "saga_rank": 5, "saga": "X-Men / Fox Universe", "title": "X-Men"},
    {"order": 76, "saga_rank": 6, "saga": "X-Men / Fox Universe", "title": "X2: X-Men United"},
    {"order": 77, "saga_rank": 7, "saga": "X-Men / Fox Universe", "title": "X-Men: The Last Stand"},
    {"order": 78, "saga_rank": 8, "saga": "X-Men / Fox Universe", "title": "X-Men Origins: Wolverine"},
    {"order": 79, "saga_rank": 9, "saga": "X-Men / Fox Universe", "title": "The Wolverine"},
    {"order": 80, "saga_rank": 10, "saga": "X-Men / Fox Universe", "title": "Logan"},
    {"order": 81, "saga_rank": 11, "saga": "X-Men / Fox Universe", "title": "Deadpool"},
    {"order": 82, "saga_rank": 12, "saga": "X-Men / Fox Universe", "title": "Deadpool 2"},
    {"order": 83, "saga_rank": 13, "saga": "X-Men / Fox Universe", "title": "Deadpool & Wolverine"}
]


def _normalize_list_ranks(raw_list: list) -> list:
    """Recomputes sequential order (1..N) and per-saga rank (1..M) so inserting items stays accurate."""
    normalized = []
    saga_counters = {}
    for idx, entry in enumerate(raw_list, start=1):
        saga = entry["saga"]
        saga_counters[saga] = saga_counters.get(saga, 0) + 1
        normalized.append({
            "order": idx,
            "saga_rank": saga_counters[saga],
            "saga": saga,
            "title": entry["title"]
        })
    return normalized


async def sync_watch_order_to_db() -> dict:
    """
    Syncs RAW_MARVEL_LIST positions to MongoDB without losing uploaded files/metadata.
    Matches existing documents by `title` first, or falls back to `watch_order`.
    """
    synced_items = _normalize_list_ranks(RAW_MARVEL_LIST)
    operations = []
    inserted_count = 0
    updated_count = 0

    for item in synced_items:
        existing_by_title = await movies_col.find_one({"title": item["title"]})
        if existing_by_title:
            operations.append(
                UpdateOne(
                    {"_id": existing_by_title["_id"]},
                    {
                        "$set": {
                            "watch_order": item["order"],
                            "saga_rank": item["saga_rank"],
                            "saga": item["saga"],
                            "title": item["title"]
                        }
                    }
                )
            )
            updated_count += 1
        else:
            operations.append(
                UpdateOne(
                    {"watch_order": item["order"]},
                    {
                        "$set": {
                            "watch_order": item["order"],
                            "saga_rank": item["saga_rank"],
                            "saga": item["saga"],
                            "title": item["title"]
                        },
                        "$setOnInsert": {
                            "files": [],
                            "audio": "Pending...",
                            "release": "N/A"
                        }
                    },
                    upsert=True
                )
            )
            inserted_count += 1

    if operations:
        await movies_col.bulk_write(operations, ordered=False)

    return {
        "total": len(synced_items),
        "updated": updated_count,
        "upserted": inserted_count
    }


@Client.on_message(filters.command("sync_order") & filters.private)
async def sync_order_command(client: Client, message: Message):
    if hasattr(Config, "ADMIN_ID") and message.from_user.id != Config.ADMIN_ID:
        return
    wait_msg = await message.reply_text("🔄 Syncing watch order numbers with MongoDB...")
    stats = await sync_watch_order_to_db()
    await wait_msg.edit_text(
        f"✅ **Watch Order Synced!**\n\n"
        f"• Total Titles: `{stats['total']}`\n"
        f"• Updated Existing: `{stats['updated']}`\n"
        f"• Added / Upserted: `{stats['upserted']}`"
    )


@Client.on_callback_query(filters.regex("^sync_watch_order$"))
async def sync_order_callback(client: Client, query: CallbackQuery):
    if hasattr(Config, "ADMIN_ID") and query.from_user.id != Config.ADMIN_ID:
        return
    await query.answer("Syncing watch order...", show_alert=False)
    stats = await sync_watch_order_to_db()
    await query.message.reply_text(
        f"✅ **Watch Order Synced!** (`{stats['total']}` titles updated in DB)"
    )


@Client.on_message(filters.command("list") & filters.private)
async def list_movies(client: Client, message: Message):
    status_msg = await message.reply_text("⏳ Checking upload status from MongoDB...")

    # Automatically keep DB watch_order numbers aligned with RAW_MARVEL_LIST
    await sync_watch_order_to_db()

    synced_items = _normalize_list_ranks(RAW_MARVEL_LIST)

    # Query uploaded items
    uploaded_movies = await movies_col.find(
        {"files": {"$exists": True, "$not": {"$size": 0}}},
        {"watch_order": 1, "title": 1}
    ).to_list(length=300)

    uploaded_orders = {doc.get("watch_order") for doc in uploaded_movies if doc.get("watch_order") is not None}
    uploaded_titles = {doc.get("title") for doc in uploaded_movies if doc.get("title")}

    output = "🎬 **MARVEL COMPLETE WATCH ORDER**\n"
    output += "✔ = Available | ✘ = Pending Upload\n\n"

    current_saga = ""
    for item in synced_items:
        if item["saga"] != current_saga:
            current_saga = item["saga"]
            output += f"\n📂 **{current_saga.upper()}**\n"

        order = item["order"]
        saga_rank = item["saga_rank"]
        title = item["title"]

        is_available = (order in uploaded_orders) or (title in uploaded_titles)
        mark = "✔" if is_available else "✘"
        output += f"{mark} `{saga_rank}.` {title}\n"

    await status_msg.delete()

    sync_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Sync Watch Order Now", callback_data="sync_watch_order")]
    ])

    if len(output) > 4096:
        chunks = [output[i:i + 4000] for i in range(0, len(output), 4000)]
        for idx, chunk in enumerate(chunks):
            reply_markup = sync_btn if idx == len(chunks) - 1 else None
            await message.reply_text(chunk, reply_markup=reply_markup)
    else:
        await message.reply_text(output, reply_markup=sync_btn)
