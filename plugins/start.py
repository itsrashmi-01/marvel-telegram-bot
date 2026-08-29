from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from plugins.list import RAW_MARVEL_LIST
from database import movies_col

# We create a shared dictionary to store which movie you are about to upload.
UPLOAD_STATE = {}

# Saga Categories mapping (Short code -> Full Name)
SAGA_CATEGORIES = {
    "mcu": "MCU + Defenders Saga",
    "multi": "Multiverse Saga",
    "f4": "Fantastic Four Universe",
    "xmen": "X-Men / Fox Universe"
}

@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    is_admin = (message.from_user.id == Config.ADMIN_ID)
    
    buttons = []
    if is_admin:
        buttons.append([InlineKeyboardButton("📤 Upload Movie", callback_data="upload_menu")])
        buttons.append([InlineKeyboardButton("🔄 Sync / Seed Database", callback_data="seed_database")])
        
    await message.reply_text(
        f"👋 Welcome **{message.from_user.first_name}**!\n\n"
        f"I am the Marvel Universe Media Bot. Click a button below to manage the database.",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )

@Client.on_callback_query(filters.regex("^upload_menu$"))
async def upload_menu_selection(client: Client, query: CallbackQuery):
    """Displays the different Sagas/Labels to choose from."""
    if query.from_user.id != Config.ADMIN_ID:
        await query.answer("Unauthorized", show_alert=True)
        return

    buttons = []
    # Create a button for each Saga category
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(f"📂 {full_name}", callback_data=f"saga_{code}_1")])
        
    buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])

    await query.message.edit_text(
        "📤 **Select a Universe/Saga to view its movies:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^saga_(.+)_(\d+)$"))
async def saga_pagination(client: Client, query: CallbackQuery):
    """Displays the movies inside a selected Saga with 🟢/🔴 status."""
    if query.from_user.id != Config.ADMIN_ID:
        return

    code = query.data.split("_")[1]
    page = int(query.data.split("_")[2])
    full_saga_name = SAGA_CATEGORIES.get(code)
    
    if not full_saga_name:
        await query.answer("Invalid Saga", show_alert=True)
        return

    # 1. Filter the RAW list to only include movies in this Saga
    saga_movies = [m for m in RAW_MARVEL_LIST if m["saga"] == full_saga_name]
    
    # 2. Query MongoDB to find which movies in this saga are already uploaded
    uploaded_docs = await movies_col.find(
        {"saga": full_saga_name, "files": {"$exists": True, "$not": {"$size": 0}}},
        {"watch_order": 1}
    ).to_list(length=100)
    
    # Create a fast lookup set of watch_order numbers that have files
    uploaded_set = {doc["watch_order"] for doc in uploaded_docs}

    # 3. Pagination Logic
    items_per_page = 10
    total_items = len(saga_movies)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_items = saga_movies[start_idx:end_idx]
    
    buttons = []
    
    # 4. Create a button for each movie with status icon
    for item in current_items:
        status_icon = "🟢" if item["order"] in uploaded_set else "🔴"
        btn_text = f"{status_icon} {item['title']}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"setupload_{item['order']}")])
        
    # Navigation buttons
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"saga_{code}_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"saga_{code}_{page+1}"))
    
    if nav:
        buttons.append(nav)
        
    buttons.append([InlineKeyboardButton("🔙 Back to Sagas", callback_data="upload_menu")])

    await query.message.edit_text(
        f"📂 **{full_saga_name}**\n\n"
        f"🟢 = Uploaded | 🔴 = Missing\n"
        f"Select a movie to upload files for:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^setupload_(\d+)$"))
async def prepare_upload(client: Client, query: CallbackQuery):
    """Sets the bot state so it expects a video file for this specific movie."""
    order = int(query.data.split("_")[1])
    
    # Find the title from the raw list
    movie = next((m for m in RAW_MARVEL_LIST if m["order"] == order), None)
    
    if movie:
        # Save state so the bot remembers which movie you clicked
        UPLOAD_STATE[query.from_user.id] = {"watch_order": order, "title": movie["title"]}
        
        await query.message.edit_text(
            f"🎬 **Ready to upload:** {movie['title']}\n"
            f"📂 {movie['saga']}\n\n"
            f"👇 **Please forward or upload the video file now.**"
        )
    else:
        await query.answer("Error: Movie not found.", show_alert=True)

@Client.on_callback_query(filters.regex("^main_menu$"))
async def return_main_menu(client: Client, query: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("📤 Upload Movie", callback_data="upload_menu")],
        [InlineKeyboardButton("🔄 Sync / Seed Database", callback_data="seed_database")]
    ]
    await query.message.edit_text(
        "👋 Welcome back to the main menu!\n\nClick a button below to manage the database.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
