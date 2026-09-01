from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from plugins.list import RAW_MARVEL_LIST
from database import movies_col, get_target_channel, set_target_channel, get_movie_by_order

# --- STATE MEMORY ---
UPLOAD_STATE = {}
WAITING_FOR_CHANNEL = {}

# --- SAGA CATEGORIES ---
SAGA_CATEGORIES = {
    "mcu": "MCU + Defenders Saga",
    "multi": "Multiverse Saga",
    "f4": "Fantastic Four Universe",
    "xmen": "X-Men / Fox Universe"
}

# ==========================================
# 1. MAIN MENU
# ==========================================
@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    is_admin = (message.from_user.id == Config.ADMIN_ID)
    
    buttons = []
    if is_admin:
        buttons.append([InlineKeyboardButton("📤 Upload Movie", callback_data="upload_menu")])
        buttons.append([InlineKeyboardButton("📢 My Channel", callback_data="manage_channel")])
        
    await message.reply_text(
        f"👋 Welcome **{message.from_user.first_name}**!\n\n"
        f"I am the Marvel Universe Media Bot. Click a button below to manage the database.",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )

@Client.on_callback_query(filters.regex("^main_menu$"))
async def return_main_menu(client: Client, query: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("📤 Upload Movie", callback_data="upload_menu")],
        [InlineKeyboardButton("📢 My Channel", callback_data="manage_channel")]
    ]
    # If returning from a photo preview, we need to delete the photo and send text
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, "👋 Welcome back to the main menu!", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query.message.edit_text("👋 Welcome back to the main menu!", reply_markup=InlineKeyboardMarkup(buttons))


# ==========================================
# 2. UPLOAD MOVIE UI & PREVIEW
# ==========================================
@Client.on_callback_query(filters.regex("^upload_menu$"))
async def upload_menu_selection(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return

    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(f"📂 {full_name}", callback_data=f"saga_{code}_1")])
        
    buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])

    text = "📤 **Select a Universe/Saga to view its movies:**"
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^saga_(.+)_(\d+)$"))
async def saga_pagination(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return

    code = query.data.split("_")[1]
    page = int(query.data.split("_")[2])
    full_saga_name = SAGA_CATEGORIES.get(code)
    
    saga_movies = [m for m in RAW_MARVEL_LIST if m["saga"] == full_saga_name]
    
    uploaded_docs = await movies_col.find(
        {"saga": full_saga_name, "files": {"$exists": True, "$not": {"$size": 0}}},
        {"watch_order": 1}
    ).to_list(length=100)
    
    uploaded_set = {doc["watch_order"] for doc in uploaded_docs}

    items_per_page = 10
    total_items = len(saga_movies)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_items = saga_movies[start_idx:end_idx]
    
    buttons = []
    for item in current_items:
        status_icon = "🟢" if item["order"] in uploaded_set else "🔴"
        btn_text = f"{status_icon} {item['title']}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"preview_{item['order']}")])
        
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"saga_{code}_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"saga_{code}_{page+1}"))
    
    if nav:
        buttons.append(nav)
        
    buttons.append([InlineKeyboardButton("🔙 Back to Sagas", callback_data="upload_menu")])

    text = f"📂 **{full_saga_name}**\n\n🟢 = Uploaded | 🔴 = Missing\nSelect a movie to preview and upload:"
    
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^preview_(\d+)$"))
async def preview_movie(client: Client, query: CallbackQuery):
    """Shows the Movie Preview Card with Poster and 'Send Files' button."""
    order = int(query.data.split("_")[1])
    movie = await get_movie_by_order(order)
    
    if not movie:
        await query.answer("Movie not found in database.", show_alert=True)
        return

    poster_url = movie.get("images", {}).get("poster_url", "")
    genres_str = ", ".join(movie.get("genres", []))
    
    caption = (
        f"🎬 **{movie['title']} ({movie.get('release_year', 'N/A')})**\n\n"
        f"📂 **Saga:** {movie.get('saga')}\n"
        f"🏷️ **Genres:** {genres_str}\n"
        f"⭐ **Rating:** {movie.get('rating', 'N/A')}/10\n\n"
        f"👇 Click the button below when you are ready to upload files."
    )
    
    buttons = [
        [InlineKeyboardButton("📥 Send All Movie Files", callback_data=f"init_upload_{order}")],
        [InlineKeyboardButton("🔙 Back to List", callback_data="upload_menu")]
    ]
    
    await query.message.delete()
    if poster_url:
        await client.send_photo(
            chat_id=query.message.chat.id,
            photo=poster_url,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await client.send_message(
            chat_id=query.message.chat.id,
            text=caption,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@Client.on_callback_query(filters.regex(r"^init_upload_(\d+)$"))
async def init_upload(client: Client, query: CallbackQuery):
    """Activates UPLOAD_STATE and tells upload.py to start intercepting files."""
    order = int(query.data.split("_")[2])
    movie = next((m for m in RAW_MARVEL_LIST if m["order"] == order), None)
    
    if movie:
        UPLOAD_STATE[query.from_user.id] = {"watch_order": order, "title": movie["title"]}
        
        await query.message.delete()
        await client.send_message(
            chat_id=query.message.chat.id,
            text=f"🎬 **Ready to receive files for:** {movie['title']}\n\n"
                 f"👇 **Please forward or upload the video files now.**\n"
                 f"(You can send multiple files one after the other.)"
        )
    else:
        await query.answer("Error setting upload state.", show_alert=True)


# ==========================================
# 3. CHANNEL MANAGEMENT UI
# ==========================================
@Client.on_callback_query(filters.regex("^manage_channel$"))
async def channel_manager_menu(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return

    if query.from_user.id in WAITING_FOR_CHANNEL:
        del WAITING_FOR_CHANNEL[query.from_user.id]

    current_channel = await get_target_channel()
    channel_text = f"`{current_channel}`" if current_channel else "❌ Not Set"

    buttons = [
        [InlineKeyboardButton("➕ Set / Change Channel", callback_data="set_new_channel")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]

    await query.message.edit_text(
        f"📢 **Channel Management**\n\n"
        f"**Current Linked Channel:** {channel_text}\n\n"
        f"The bot will publish all movie posts to this channel. Make sure the bot is added as an **Admin** in the channel!",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex("^set_new_channel$"))
async def ask_for_channel(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return

    WAITING_FOR_CHANNEL[query.from_user.id] = True

    buttons = [[InlineKeyboardButton("❌ Cancel", callback_data="manage_channel")]]
    await query.message.edit_text(
        "👇 **How to link your channel:**\n\n"
        "1. Go to your target channel.\n"
        "2. Forward ANY message from that channel to me right now.\n"
        "(Or, you can just type the channel ID if you know it, e.g., -100123456789)",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_message(filters.private & filters.user(Config.ADMIN_ID))
async def capture_channel_input(client: Client, message: Message):
    if not WAITING_FOR_CHANNEL.get(message.from_user.id):
        message.continue_propagation()
        return

    channel_id = None
    if message.forward_from_chat and message.forward_from_chat.type.name == "CHANNEL":
        channel_id = message.forward_from_chat.id
    else:
        try:
            channel_id = int(message.text)
        except (ValueError, TypeError):
            await message.reply_text("❌ Invalid input. Please forward a message from your channel or send a valid numeric ID starting with -100.")
            return

    await set_target_channel(channel_id)
    del WAITING_FOR_CHANNEL[message.from_user.id]

    buttons = [[InlineKeyboardButton("🔙 Back to Channel Menu", callback_data="manage_channel")]]
    await message.reply_text(
        f"✅ **Channel successfully linked!**\n\n"
        f"Saved ID: `{channel_id}`\n\n"
        f"Make sure to add the bot as an Admin in this channel so it can post.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
