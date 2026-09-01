from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from database import movies_col, get_movie_by_order, get_target_channel
from plugins.start import SAGA_CATEGORIES

# --- IMPORTING YOUR TEMPLATE FUNCTIONS ---
from template import format_movie_post, get_download_button, to_small_caps

@Client.on_message(filters.command("post") & filters.private)
async def post_command_handler(client: Client, message: Message):
    """Starts the interactive menu to select a movie to publish to the channel."""
    if message.from_user.id != Config.ADMIN_ID:
        return
        
    # FETCH DYNAMICALLY FROM DATABASE
    target_channel = await get_target_channel()
    if not target_channel:
        text = to_small_caps(
            ">⚠️ **ɴᴏ ᴄʜᴀɴɴᴇʟ ʟɪɴᴋᴇᴅ!**\n"
            ">ᴜsᴇ ᴛʜᴇ '📢 ᴍʏ ᴄʜᴀɴɴᴇʟ' ʙᴜᴛᴛᴏɴ ɪɴ ᴛʜᴇ /sᴛᴀʀᴛ ᴍᴇɴᴜ ᴛᴏ ʟɪɴᴋ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ғɪʀsᴛ."
        )
        await message.reply_text(text)
        return

    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(to_small_caps(f"📢 {full_name}"), callback_data=f"post_saga_{code}_1")])
        
    text = to_small_caps(
        ">📢 **sᴇʟᴇᴄᴛ ᴀ ᴜɴɪᴠᴇʀsᴇ/sᴀɢᴀ ᴛᴏ ᴘᴜʙʟɪsʜ ᴀ ᴍᴏᴠɪᴇ ғʀᴏᴍ:**\n"
        ">(ᴏɴʟʏ ᴍᴏᴠɪᴇs ᴡɪᴛʜ ᴜᴘʟᴏᴀᴅᴇᴅ ғɪʟᴇs ᴡɪʟʟ ʙᴇ sʜᴏᴡɴ ʜᴇʀᴇ)"
    )
    
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^post_saga_(.+)_(\d+)$"))
async def post_saga_pagination(client: Client, query: CallbackQuery):
    """Displays only AVAILABLE movies inside a selected Saga for posting."""
    if query.from_user.id != Config.ADMIN_ID:
        return

    code = query.data.split("_")[2]
    page = int(query.data.split("_")[3])
    full_saga_name = SAGA_CATEGORIES.get(code)
    
    if not full_saga_name:
        await query.answer(to_small_caps("ɪɴᴠᴀʟɪᴅ sᴀɢᴀ"), show_alert=True)
        return

    # Fetch ONLY uploaded/available movies for this saga
    available_movies = await movies_col.find(
        {"saga": full_saga_name, "status": "Available"}
    ).sort("saga_rank", 1).to_list(length=100)

    if not available_movies:
        await query.answer(to_small_caps("ɴᴏ ᴍᴏᴠɪᴇs ᴜᴘʟᴏᴀᴅᴇᴅ ɪɴ ᴛʜɪs sᴀɢᴀ ʏᴇᴛ!"), show_alert=True)
        return

    # Pagination Logic
    items_per_page = 10
    total_items = len(available_movies)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_items = available_movies[start_idx:end_idx]
    
    buttons = []
    for item in current_items:
        btn_text = to_small_caps(f"📢 {item['title']} ({item.get('release_year', '')})")
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"confirm_post_{item['watch_order']}")])
        
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(to_small_caps("⬅️ ᴘʀᴇᴠ"), callback_data=f"post_saga_{code}_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(to_small_caps("ɴᴇxᴛ ➡️"), callback_data=f"post_saga_{code}_{page+1}"))
    
    if nav:
        buttons.append(nav)
        
    buttons.append([InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ sᴀɢᴀs"), callback_data="post_menu_back")])

    sc_saga_name = to_small_caps(full_saga_name)
    text = (
        f">📢 **ᴘᴜʙʟɪsʜɪɴɢ ғʀᴏᴍ: {sc_saga_name}**\n"
        f">\n"
        f">sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴠɪᴇ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴄʜᴀɴɴᴇʟ ᴘᴏsᴛ:"
    )
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^confirm_post_(\d+)$"))
async def publish_to_channel(client: Client, query: CallbackQuery):
    """Generates the formatted post and sends it to the target channel."""
    if query.from_user.id != Config.ADMIN_ID:
        return

    order = int(query.data.split("_")[2])
    movie = await get_movie_by_order(order)
    
    target_channel = await get_target_channel()
    
    if not target_channel:
        await query.answer(to_small_caps("ɴᴏ ᴄʜᴀɴɴᴇʟ ʟɪɴᴋᴇᴅ! ʟɪɴᴋ ɪᴛ ɪɴ /sᴛᴀʀᴛ."), show_alert=True)
        return
        
    if not movie or not movie.get("files"):
        await query.answer(to_small_caps("ᴍᴏᴠɪᴇ ᴏʀ ғɪʟᴇs ɴᴏᴛ ғᴏᴜɴᴅ!"), show_alert=True)
        return

    await query.answer(to_small_caps("ᴘᴜʙʟɪsʜɪɴɢ ᴛᴏ ᴄʜᴀɴɴᴇʟ..."))
    
    # 1. Format the Post Caption using template.py
    caption = format_movie_post(movie)

    # 2. Build the deep-link button using template.py
    bot_info = await client.get_me()
    bot_username = bot_info.username
    deep_link = f"https://t.me/{bot_username}?start=get_{order}"
    
    markup = get_download_button(deep_link)
    poster_url = movie.get("images", {}).get("poster_url")

    try:
        # 3. Send to target_channel
        if poster_url:
            await client.send_photo(
                chat_id=target_channel,
                photo=poster_url,
                caption=caption,
                reply_markup=markup
            )
        else:
            await client.send_message(
                chat_id=target_channel,
                text=caption,
                reply_markup=markup
            )
            
        sc_title = to_small_caps(movie['title'])
        success_text = (
            f">✅ **sᴜᴄᴄᴇssғᴜʟʟʏ ᴘᴜʙʟɪsʜᴇᴅ ᴛᴏ ᴄʜᴀɴɴᴇʟ!**\n"
            f">\n"
            f">🎬 {sc_title}"
        )
        await query.message.edit_text(success_text)
    except Exception as e:
        error_text = to_small_caps(
            f">❌ **ғᴀɪʟᴇᴅ ᴛᴏ ᴘᴏsᴛ:** {e}\n"
            f">\n"
            f">(ᴅɪᴅ ʏᴏᴜ ғᴏʀɢᴇᴛ ᴛᴏ ᴀᴅᴅ ᴛʜᴇ ʙᴏᴛ ᴀs ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ?)"
        )
        await query.message.edit_text(error_text)

@Client.on_callback_query(filters.regex("^post_menu_back$"))
async def post_menu_back(client: Client, query: CallbackQuery):
    """Returns to the main post saga menu."""
    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(to_small_caps(f"📢 {full_name}"), callback_data=f"post_saga_{code}_1")])
        
    text = to_small_caps(">📢 **sᴇʟᴇᴄᴛ ᴀ ᴜɴɪᴠᴇʀsᴇ/sᴀɢᴀ ᴛᴏ ᴘᴜʙʟɪsʜ ᴀ ᴍᴏᴠɪᴇ ғʀᴏᴍ:**")
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
