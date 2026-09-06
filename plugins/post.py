import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from database import movies_col, get_movie_by_order, get_target_channel
from plugins.start import SAGA_CATEGORIES
from template import format_movie_post, get_download_button, to_small_caps

@Client.on_message(filters.command("post") & filters.private)
async def post_command_handler(client: Client, message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    target_channel = await get_target_channel()
    if not target_channel:
        text = (
            "<blockquote>⚠️ <b>ɴᴏ ᴄʜᴀɴɴᴇʟ ʟɪɴᴋᴇᴅ!</b>\n"
            "ᴜsᴇ ᴛʜᴇ '📢 ᴍʏ ᴄʜᴀɴɴᴇʟ' ʙᴜᴛᴛᴏɴ ɪɴ ᴛʜᴇ /start ᴍᴇɴᴜ ᴛᴏ ʟɪɴᴋ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ғɪʀsᴛ.</blockquote>"
        )
        return await message.reply_text(text)

    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(to_small_caps(f"📢 {full_name}"), callback_data=f"post_saga_{code}_1")])
        
    text = (
        "<blockquote>📢 <b>sᴇʟᴇᴄᴛ ᴀ ᴜɴɪᴠᴇʀsᴇ/sᴀɢᴀ ᴛᴏ ᴘᴜʙʟɪsʜ ᴀ ᴍᴏᴠɪᴇ ғʀᴏᴍ:</b>\n"
        "(ᴏɴʟʏ ᴍᴏᴠɪᴇs ᴡɪᴛʜ ᴜᴘʟᴏᴀᴅᴇᴅ ғɪʟᴇs ᴡɪʟʟ ʙᴇ sʜᴏᴡɴ ʜᴇʀᴇ)</blockquote>"
    )
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^post_saga_(.+)_(\d+)$"))
async def post_saga_pagination(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    code = query.data.split("_")[2]
    page = int(query.data.split("_")[3])
    full_saga_name = SAGA_CATEGORIES.get(code)
    
    if not full_saga_name:
        return await query.answer("ɪɴᴠᴀʟɪᴅ sᴀɢᴀ", show_alert=True)

    available_movies = await movies_col.find(
        {"saga": full_saga_name, "status": "Available"}
    ).sort("saga_rank", 1).to_list(length=100)

    if not available_movies:
        return await query.answer("ɴᴏ ᴍᴏᴠɪᴇs ᴜᴘʟᴏᴀᴅᴇᴅ ɪɴ ᴛʜɪs sᴀɢᴀ ʏᴇᴛ!", show_alert=True)

    items_per_page = 10
    total_pages = (len(available_movies) + items_per_page - 1) // items_per_page
    start_idx = (page - 1) * items_per_page
    
    buttons = []
    # --- BULK POST ALL BUTTON ---
    buttons.append([InlineKeyboardButton(to_small_caps(f"🚀 ᴘᴏsᴛ ᴀʟʟ {full_saga_name} ᴍᴏᴠɪᴇs"), callback_data=f"post_bulk_{code}")])
    
    for item in available_movies[start_idx : start_idx + items_per_page]:
        btn_text = to_small_caps(f"📢 {item['title']} ({item.get('release_year', '')})")
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"confirm_post_{item['watch_order']}")])
        
    nav = []
    if page > 1: nav.append(InlineKeyboardButton("⬅️ ᴘʀᴇᴠ", callback_data=f"post_saga_{code}_{page-1}"))
    if page < total_pages: nav.append(InlineKeyboardButton("ɴᴇxᴛ ➡️", callback_data=f"post_saga_{code}_{page+1}"))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ sᴀɢᴀs", callback_data="post_menu_back")])

    sc_saga_name = to_small_caps(full_saga_name)
    text = (
        f"<blockquote>📢 <b>ᴘᴜʙʟɪsʜɪɴɢ ғʀᴏᴍ: {sc_saga_name}</b>\n\n"
        f"sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴠɪᴇ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴀ ᴄʜᴀɴɴᴇʟ ᴘᴏsᴛ:</blockquote>"
    )
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^post_bulk_(.+)$"))
async def bulk_publish_saga(client: Client, query: CallbackQuery):
    """Posts all available movies in a saga to the channel."""
    if query.from_user.id != Config.ADMIN_ID: return
    code = query.data.split("_")[2]
    full_saga_name = SAGA_CATEGORIES.get(code)
    target_channel = await get_target_channel()
    
    available_movies = await movies_col.find(
        {"saga": full_saga_name, "status": "Available"}
    ).sort("saga_rank", 1).to_list(length=100)

    sc_saga = to_small_caps(full_saga_name)
    await query.message.edit_text(f"<blockquote>🚀 <b>ᴘᴏsᴛɪɴɢ {len(available_movies)} ᴍᴏᴠɪᴇs ғʀᴏᴍ {sc_saga}...</b> ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ.</blockquote>")
    
    for movie in available_movies:
        caption = format_movie_post(movie)
        bot_info = await client.get_me()
        deep_link = f"https://t.me/{bot_info.username}?start=get_{movie['watch_order']}"
        markup = get_download_button(deep_link)
        poster_url = movie.get("images", {}).get("poster_url")
        
        try:
            if poster_url:
                await client.send_photo(target_channel, photo=poster_url, caption=caption, reply_markup=markup)
            else:
                await client.send_message(target_channel, text=caption, reply_markup=markup)
            await asyncio.sleep(2.5) # Prevent flood waits
        except Exception as e:
            pass # Skips over errors quietly to continue the loop
            
    await query.message.reply_text("<blockquote>✅ <b>ᴀʟʟ ᴍᴏᴠɪᴇs ᴘᴜʙʟɪsʜᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b></blockquote>")

@Client.on_callback_query(filters.regex(r"^confirm_post_(\d+)$"))
async def publish_single_post(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    order = int(query.data.split("_")[2])
    movie = await get_movie_by_order(order)
    target_channel = await get_target_channel()
    
    if not target_channel:
        return await query.answer("ɴᴏ ᴄʜᴀɴɴᴇʟ ʟɪɴᴋᴇᴅ! ʟɪɴᴋ ɪᴛ ɪɴ /start.", show_alert=True)
    if not movie or not movie.get("files"):
        return await query.answer("ᴍᴏᴠɪᴇ ᴏʀ ғɪʟᴇs ɴᴏᴛ ғᴏᴜɴᴅ!", show_alert=True)

    await query.answer("ᴘᴜʙʟɪsʜɪɴɢ ᴛᴏ ᴄʜᴀɴɴᴇʟ...")
    caption = format_movie_post(movie)
    bot_info = await client.get_me()
    deep_link = f"https://t.me/{bot_info.username}?start=get_{order}"
    markup = get_download_button(deep_link)
    poster_url = movie.get("images", {}).get("poster_url")

    try:
        if poster_url:
            await client.send_photo(target_channel, photo=poster_url, caption=caption, reply_markup=markup)
        else:
            await client.send_message(target_channel, text=caption, reply_markup=markup)
            
        sc_title = to_small_caps(movie['title'])
        await query.message.edit_text(f"<blockquote>✅ <b>sᴜᴄᴄᴇssғᴜʟʟʏ ᴘᴜʙʟɪsʜᴇᴅ ᴛᴏ ᴄʜᴀɴɴᴇʟ!</b>\n\n🎬 {sc_title}</blockquote>")
    except Exception as e:
        sc_error = to_small_caps(str(e))
        await query.message.edit_text(f"<blockquote>❌ <b>ғᴀɪʟᴇᴅ ᴛᴏ ᴘᴏsᴛ:</b> {sc_error}\n\n(ᴅɪᴅ ʏᴏᴜ ғᴏʀɢᴇᴛ ᴛᴏ ᴀᴅᴅ ᴛʜᴇ ʙᴏᴛ ᴀs ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ?)</blockquote>")

@Client.on_callback_query(filters.regex("^post_menu_back$"))
async def post_menu_back(client: Client, query: CallbackQuery):
    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(to_small_caps(f"📢 {full_name}"), callback_data=f"post_saga_{code}_1")])
    text = "<blockquote>📢 <b>sᴇʟᴇᴄᴛ ᴀ ᴜɴɪᴠᴇʀsᴇ/sᴀɢᴀ ᴛᴏ ᴘᴜʙʟɪsʜ ᴀ ᴍᴏᴠɪᴇ ғʀᴏᴍ:</b></blockquote>"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
