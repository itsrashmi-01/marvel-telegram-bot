from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from plugins.list import RAW_MARVEL_LIST

UPLOAD_STATE = {}

@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    is_admin = (message.from_user.id == Config.ADMIN_ID)
    
    buttons = []
    if is_admin:
        buttons.append([InlineKeyboardButton("📤 Upload Movie", callback_data="upload_page_1")])
        buttons.append([InlineKeyboardButton("🔄 Sync / Seed Database", callback_data="seed_database")])
        
    await message.reply_text(
        f"👋 Welcome **{message.from_user.first_name}**!\n\n"
        f"I am the Marvel Universe Media Bot. Click a button below to manage the database.",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )

def get_short_saga_name(saga_full_name: str) -> str:
    """Helper to abbreviate saga names so they fit nicely on Telegram buttons"""
    if "Defenders" in saga_full_name: return "MCU"
    if "Multiverse" in saga_full_name: return "Multi"
    if "Fantastic" in saga_full_name: return "F4"
    if "X-Men" in saga_full_name: return "XMen"
    return "Movie"

@Client.on_callback_query(filters.regex(r"^upload_page_(\d+)$"))
async def upload_pagination(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        await query.answer("Unauthorized", show_alert=True)
        return

    page = int(query.data.split("_")[2])
    items_per_page = 10
    total_items = len(RAW_MARVEL_LIST)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_items = RAW_MARVEL_LIST[start_idx:end_idx]
    
    buttons = []
    
    for item in current_items:
        # Create a clean button label like "[MCU #1] Captain America"
        short_saga = get_short_saga_name(item['saga'])
        btn_text = f"[{short_saga} #{item['saga_rank']}] {item['title']}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"setupload_{item['order']}")])
        
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"upload_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"upload_page_{page+1}"))
    
    if nav:
        buttons.append(nav)
        
    buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])

    await query.message.edit_text(
        "📤 **Select a movie from the rank lists to upload:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^setupload_(\d+)$"))
async def prepare_upload(client: Client, query: CallbackQuery):
    order = int(query.data.split("_")[1])
    movie = next((m for m in RAW_MARVEL_LIST if m["order"] == order), None)
    
    if movie:
        UPLOAD_STATE[query.from_user.id] = {"watch_order": order, "title": movie["title"]}
        await query.message.edit_text(
            f"🎬 **Ready to upload:** {movie['title']} ({movie['saga']} Rank #{movie['saga_rank']})\n\n"
            f"Please forward or upload the video file now."
        )
    else:
        await query.answer("Error: Movie not found.", show_alert=True)

@Client.on_callback_query(filters.regex("^main_menu$"))
async def return_main_menu(client: Client, query: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("📤 Upload Movie", callback_data="upload_page_1")],
        [InlineKeyboardButton("🔄 Sync / Seed Database", callback_data="seed_database")]
    ]
    await query.message.edit_text(
        "👋 Welcome back to the main menu!\n\nClick a button below to manage the database.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
