from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from plugins.list import RAW_MARVEL_LIST
from database import movies_col, get_target_channel, set_target_channel, get_movie_by_order, init_marvel_list

# --- IMPORTING YOUR TEMPLATE FUNCTIONS ---
from template import format_movie_post, to_small_caps

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
        buttons.append([InlineKeyboardButton("📤 ᴜᴘʟᴏᴀᴅ ᴍᴏᴠɪᴇ", callback_data="upload_menu")])
        buttons.append([InlineKeyboardButton("📢 ᴍʏ ᴄʜᴀɴɴᴇʟ", callback_data="manage_channel")])
        
    user_name = to_small_caps(message.from_user.first_name)
    text = (
        f"<blockquote>👋 <b>ᴡᴇʟᴄᴏᴍᴇ {user_name}!</b>\n\n"
        f"ɪ ᴀᴍ ᴛʜᴇ ᴍᴀʀᴠᴇʟ ᴜɴɪᴠᴇʀsᴇ ᴍᴇᴅɪᴀ ʙᴏᴛ.\n"
        f"ᴄʟɪᴄᴋ ᴀ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴍᴀɴᴀɢᴇ ᴛʜᴇ ᴅᴀᴛᴀʙᴀsᴇ.</blockquote>"
    )
    
    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )

@Client.on_callback_query(filters.regex("^main_menu$"))
async def return_main_menu(client: Client, query: CallbackQuery):
    buttons = [
        [InlineKeyboardButton("📤 ᴜᴘʟᴏᴀᴅ ᴍᴏᴠɪᴇ", callback_data="upload_menu")],
        [InlineKeyboardButton("📢 ᴍʏ ᴄʜᴀɴɴᴇʟ", callback_data="manage_channel")]
    ]
    
    text = (
        "<blockquote>👋 <b>ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ ᴛᴏ ᴛʜᴇ ᴍᴀɪɴ ᴍᴇɴᴜ!</b>\n\n"
        "ᴄʟɪᴄᴋ ᴀ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴍᴀɴᴀɢᴇ ᴛʜᴇ ᴅᴀᴛᴀʙᴀsᴇ.</blockquote>"
    )
    
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ==========================================
# 2. UPLOAD MOVIE UI & PREVIEW
# ==========================================
@Client.on_callback_query(filters.regex("^upload_menu$"))
async def upload_menu_selection(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return

    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(to_small_caps(f"📂 {full_name}"), callback_data=f"saga_{code}_1")])
        
    buttons.append([InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu")])

    text = "<blockquote>📤 <b>sᴇʟᴇᴄᴛ ᴀ ᴜɴɪᴠᴇʀsᴇ/sᴀɢᴀ ᴛᴏ ᴠɪᴇᴡ ɪᴛs ᴍᴏᴠɪᴇs:</b></blockquote>"
    
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
        btn_text = f"{status_icon} " + to_small_caps(item['title'])
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"preview_{item['order']}")])
        
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ ᴘʀᴇᴠ", callback_data=f"saga_{code}_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("ɴᴇxᴛ ➡️", callback_data=f"saga_{code}_{page+1}"))
    
    if nav:
        buttons.append(nav)
        
    buttons.append([InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ sᴀɢᴀs", callback_data="upload_menu")])

    sc_saga_name = to_small_caps(full_saga_name)
    text = (
        f"<blockquote>📂 <b>{sc_saga_name}</b>\n\n"
        f"🟢 = ᴜᴘʟᴏᴀᴅᴇᴅ | 🔴 = ᴍɪssɪɴɢ\n"
        f"sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴠɪᴇ ᴛᴏ ᴘʀᴇᴠɪᴇᴡ ᴀɴᴅ ᴜᴘʟᴏᴀᴅ:</blockquote>"
    )
    
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^preview_(\d+)$"))
async def preview_movie(client: Client, query: CallbackQuery):
    order = int(query.data.split("_")[1])
    movie = await get_movie_by_order(order)
    
    if not movie:
        await query.answer("ғᴇᴛᴄʜɪɴɢ ᴛᴍᴅʙ ᴍᴇᴛᴀᴅᴀᴛᴀ... ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ.", show_alert=False)
        
        raw_movie = next((m for m in RAW_MARVEL_LIST if m["order"] == order), None)
        if not raw_movie:
            await query.answer("ᴇʀʀᴏʀ: ᴍᴏᴠɪᴇ ɴᴏᴛ ғᴏᴜɴᴅ.", show_alert=True)
            return
            
        bot_info = await client.get_me()
        await init_marvel_list([raw_movie], bot_username=bot_info.username)
        movie = await get_movie_by_order(order)
        
        if not movie:
            await query.answer("ғᴀɪʟᴇᴅ ᴛᴏ ɪɴɪᴛɪᴀʟɪᴢᴇ ᴍᴏᴠɪᴇ.", show_alert=True)
            return

    # --- USE THE TEMPLATE FOR THE PREVIEW CAPTION ---
    caption = format_movie_post(movie)

    buttons = [
        [InlineKeyboardButton("📥 sᴇɴᴅ ᴀʟʟ ᴍᴏᴠɪᴇ ғɪʟᴇs", callback_data=f"init_upload_{order}")],
        [InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ ʟɪsᴛ", callback_data="upload_menu")]
    ]
    
    poster_url = movie.get("images", {}).get("poster_url", "")
    
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
    order = int(query.data.split("_")[2])
    movie = next((m for m in RAW_MARVEL_LIST if m["order"] == order), None)
    
    if movie:
        UPLOAD_STATE[query.from_user.id] = {"watch_order": order, "title": movie["title"]}
        
        sc_title = to_small_caps(movie["title"])
        text = (
            f"<blockquote>🎬 <b>ʀᴇᴀᴅʏ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ғɪʟᴇs ғᴏʀ:</b> {sc_title}\n\n"
            f"👇 <b>ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴏʀ ᴜᴘʟᴏᴀᴅ ᴛʜᴇ ᴠɪᴅᴇᴏ ғɪʟᴇs ɴᴏᴡ.</b>\n"
            f"(ʏᴏᴜ ᴄᴀɴ sᴇɴᴅ ᴍᴜʟᴛɪᴘʟᴇ ғɪʟᴇs ᴏɴᴇ ᴀғᴛᴇʀ ᴛʜᴇ ᴏᴛʜᴇʀ.)</blockquote>"
        )
        
        await query.message.delete()
        await client.send_message(
            chat_id=query.message.chat.id,
            text=text
        )
    else:
        await query.answer("ᴇʀʀᴏʀ sᴇᴛᴛɪɴɢ ᴜᴘʟᴏᴀᴅ sᴛᴀᴛᴇ.", show_alert=True)


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
    channel_text = f"<code>{current_channel}</code>" if current_channel else "❌ ɴᴏᴛ sᴇᴛ"

    buttons = [
        [InlineKeyboardButton("➕ sᴇᴛ / ᴄʜᴀɴɢᴇ ᴄʜᴀɴɴᴇʟ", callback_data="set_new_channel")],
        [InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu")]
    ]

    text = (
        f"<blockquote>📢 <b>ᴄʜᴀɴɴᴇʟ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ</b>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟ:</b> {channel_text}\n\n"
        f"ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ᴘᴜʙʟɪsʜ ᴀʟʟ ᴍᴏᴠɪᴇ ᴘᴏsᴛs ᴛᴏ ᴛʜɪs ᴄʜᴀɴɴᴇʟ.\n"
        f"ᴍᴀᴋᴇ sᴜʀᴇ ᴛʜᴇ ʙᴏᴛ ɪs ᴀᴅᴅᴇᴅ ᴀs ᴀɴ <b>ᴀᴅᴍɪɴ</b> ɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ!</blockquote>"
    )
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex("^set_new_channel$"))
async def ask_for_channel(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return

    WAITING_FOR_CHANNEL[query.from_user.id] = True

    buttons = [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="manage_channel")]]
    text = (
        "<blockquote>👇 <b>ʜᴏᴡ ᴛᴏ ʟɪɴᴋ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ:</b>\n\n"
        "𝟷. ɢᴏ ᴛᴏ ʏᴏᴜʀ ᴛᴀʀɢᴇᴛ ᴄʜᴀɴɴᴇʟ.\n"
        "𝟸. ғᴏʀᴡᴀʀᴅ ᴀɴʏ ᴍᴇssᴀɢᴇ ғʀᴏᴍ ᴛʜᴀᴛ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴍᴇ ʀɪɢʜᴛ ɴᴏᴡ.\n"
        "(ᴏʀ, ʏᴏᴜ ᴄᴀɴ ᴊᴜsᴛ ᴛʏᴘᴇ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ɪᴅ ɪғ ʏᴏᴜ ᴋɴᴏᴡ ɪᴛ, ᴇ.ɢ., -𝟷𝟶𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿)</blockquote>"
    )
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

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
            await message.reply_text("<blockquote>❌ ɪɴᴠᴀʟɪᴅ ɪɴᴘᴜᴛ. ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴀ ᴍᴇssᴀɢᴇ ғʀᴏᴍ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴏʀ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍᴇʀɪᴄ ɪᴅ sᴛᴀʀᴛɪɴɢ ᴡɪᴛʜ -𝟷𝟶𝟶.</blockquote>")
            return

    await set_target_channel(channel_id)
    del WAITING_FOR_CHANNEL[message.from_user.id]

    buttons = [[InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ ᴄʜᴀɴɴᴇʟ ᴍᴇɴᴜ", callback_data="manage_channel")]]
    text = (
        f"<blockquote>✅ <b>ᴄʜᴀɴɴᴇʟ sᴜᴄᴄᴇssғᴜʟʟʏ ʟɪɴᴋᴇᴅ!</b>\n\n"
        f"sᴀᴠᴇᴅ ɪᴅ: <code>{channel_id}</code>\n\n"
        f"ᴍᴀᴋᴇ sᴜʀᴇ ᴛᴏ ᴀᴅᴅ ᴛʜᴇ ʙᴏᴛ ᴀs ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪs ᴄʜᴀɴɴᴇʟ sᴏ ɪᴛ ᴄᴀɴ ᴘᴏsᴛ.</blockquote>"
    )
    
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
