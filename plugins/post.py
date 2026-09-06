import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from database import movies_col, get_movie_by_order, get_target_channels
from plugins.start import SAGA_CATEGORIES
from template import format_movie_post, get_download_button, to_small_caps

@Client.on_message(filters.command("post") & filters.private)
async def post_command_handler(client: Client, message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(to_small_caps(f"📢 {full_name}"), callback_data=f"post_saga_{code}")])
        
    text = "<blockquote>📢 <b>sᴇʟᴇᴄᴛ ᴀ ᴜɴɪᴠᴇʀsᴇ/sᴀɢᴀ ᴛᴏ ᴘᴜʙʟɪsʜ ᴍᴏᴠɪᴇs ғʀᴏᴍ:</b></blockquote>"
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex("^post_menu_back$"))
async def post_menu_back(client: Client, query: CallbackQuery):
    """Entry point from Main Menu"""
    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(to_small_caps(f"📢 {full_name}"), callback_data=f"post_saga_{code}")])
    buttons.append([InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")])
        
    text = "<blockquote>📢 <b>sᴇʟᴇᴄᴛ ᴀ ᴜɴɪᴠᴇʀsᴇ/sᴀɢᴀ ᴛᴏ ᴘᴜʙʟɪsʜ ᴍᴏᴠɪᴇs ғʀᴏᴍ:</b></blockquote>"
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^post_saga_(.+)$"))
async def post_select_channel(client: Client, query: CallbackQuery):
    """Step 2: Select the target channel to post the saga to."""
    if query.from_user.id != Config.ADMIN_ID: return
    code = query.data.split("_")[2]
    full_saga_name = SAGA_CATEGORIES.get(code)
    
    # Check if movies exist in this saga
    count = await movies_col.count_documents({"saga": full_saga_name, "status": "Available"})
    if count == 0:
        return await query.answer("ɴᴏ ᴍᴏᴠɪᴇs ᴜᴘʟᴏᴀᴅᴇᴅ ɪɴ ᴛʜɪs sᴀɢᴀ ʏᴇᴛ!", show_alert=True)

    channels = await get_target_channels()
    if not channels:
        return await query.answer("ɴᴏ ᴄʜᴀɴɴᴇʟs ᴀᴅᴅᴇᴅ! ɢᴏ ᴛᴏ 'ᴍʏ ᴄʜᴀɴɴᴇʟs' ᴛᴏ ᴀᴅᴅ ᴏɴᴇ.", show_alert=True)

    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(to_small_caps(f"📢 {ch['name']}"), callback_data=f"post_chan_{code}_{ch['id']}")])
    buttons.append([InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ sᴀɢᴀs"), callback_data="post_menu_back")])

    sc_saga = to_small_caps(full_saga_name)
    text = (
        f"<blockquote>📢 <b>{sc_saga} ({count} ᴍᴏᴠɪᴇs)</b>\n\n"
        f"sᴇʟᴇᴄᴛ ᴛʜᴇ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ:</blockquote>"
    )
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^post_chan_(.+)_(.+)$"))
async def post_confirm_upload(client: Client, query: CallbackQuery):
    """Step 3: Confirm Upload"""
    if query.from_user.id != Config.ADMIN_ID: return
    code = query.data.split("_")[2]
    channel_id = query.data.split("_")[3]
    full_saga_name = SAGA_CATEGORIES.get(code)
    
    count = await movies_col.count_documents({"saga": full_saga_name, "status": "Available"})
    sc_saga = to_small_caps(full_saga_name)
    
    buttons = [
        [InlineKeyboardButton(to_small_caps("🚀 ᴜᴘʟᴏᴀᴅ (ᴘᴜʙʟɪsʜ ᴀʟʟ)"), callback_data=f"post_exec_{code}_{channel_id}")],
        [InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ"), callback_data=f"post_saga_{code}")]
    ]
    
    text = (
        f"<blockquote>⚠️ <b>ʀᴇᴀᴅʏ ᴛᴏ ᴜᴘʟᴏᴀᴅ</b>\n\n"
        f"ʏᴏᴜ ᴀʀᴇ ᴀʙᴏᴜᴛ ᴛᴏ ᴘᴜʙʟɪsʜ <b>{count} ᴍᴏᴠɪᴇs</b> ғʀᴏᴍ <b>{sc_saga}</b>.\n\n"
        f"ᴄʟɪᴄᴋ ᴜᴘʟᴏᴀᴅ ᴛᴏ ʙᴇɢɪɴ ᴛʜᴇ ᴘʀᴏᴄᴇss.</blockquote>"
    )
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^post_exec_(.+)_(.+)$"))
async def execute_bulk_post(client: Client, query: CallbackQuery):
    """Step 4: Execute the Loop"""
    if query.from_user.id != Config.ADMIN_ID: return
    code = query.data.split("_")[2]
    channel_id = int(query.data.split("_")[3])
    full_saga_name = SAGA_CATEGORIES.get(code)
    
    available_movies = await movies_col.find(
        {"saga": full_saga_name, "status": "Available"}
    ).sort("saga_rank", 1).to_list(length=100)

    await query.message.edit_text("<blockquote>🚀 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ᴍᴏᴠɪᴇs...</b> ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ.</blockquote>")
    
    for movie in available_movies:
        caption = format_movie_post(movie)
        bot_info = await client.get_me()
        deep_link = f"https://t.me/{bot_info.username}?start=get_{movie['watch_order']}"
        markup = get_download_button(deep_link)
        poster_url = movie.get("images", {}).get("poster_url")
        
        try:
            if poster_url:
                await client.send_photo(channel_id, photo=poster_url, caption=caption, reply_markup=markup)
            else:
                await client.send_message(channel_id, text=caption, reply_markup=markup)
            await asyncio.sleep(2.5) # Prevent flood waits
        except Exception:
            pass 
            
    await query.message.reply_text("<blockquote>✅ <b>ᴀʟʟ ᴍᴏᴠɪᴇs ᴜᴘʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b></blockquote>")

# --- FOR SINGLE UPLOADS TRIGGERED AFTER ADDING MEDIAFIRE LINKS ---
@Client.on_callback_query(filters.regex(r"^select_chan_post_(\d+)$"))
async def select_channel_single(client: Client, query: CallbackQuery):
    """Called from upload.py to select a channel for a single movie"""
    order = int(query.data.split("_")[3])
    channels = await get_target_channels()
    if not channels:
        return await query.answer("ɴᴏ ᴄʜᴀɴɴᴇʟs ᴀᴅᴅᴇᴅ!", show_alert=True)
        
    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(to_small_caps(f"📢 {ch['name']}"), callback_data=f"single_post_{order}_{ch['id']}")])
        
    await query.message.edit_text("<blockquote>📢 <b>sᴇʟᴇᴄᴛ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ:</b></blockquote>", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^single_post_(\d+)_(-?\d+)$"))
async def publish_single_post(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    order = int(query.data.split("_")[2])
    channel_id = int(query.data.split("_")[3])
    
    movie = await get_movie_by_order(order)
    await query.answer("ᴘᴜʙʟɪsʜɪɴɢ...")
    
    caption = format_movie_post(movie)
    bot_info = await client.get_me()
    deep_link = f"https://t.me/{bot_info.username}?start=get_{order}"
    markup = get_download_button(deep_link)
    poster_url = movie.get("images", {}).get("poster_url")

    try:
        if poster_url:
            await client.send_photo(channel_id, photo=poster_url, caption=caption, reply_markup=markup)
        else:
            await client.send_message(channel_id, text=caption, reply_markup=markup)
            
        sc_title = to_small_caps(movie['title'])
        await query.message.edit_text(f"<blockquote>✅ <b>sᴜᴄᴄᴇssғᴜʟʟʏ ᴘᴜʙʟɪsʜᴇᴅ ᴛᴏ ᴄʜᴀɴɴᴇʟ!</b>\n\n🎬 {sc_title}</blockquote>")
    except Exception as e:
        sc_error = to_small_caps(str(e))
        await query.message.edit_text(f"<blockquote>❌ <b>ғᴀɪʟᴇᴅ ᴛᴏ ᴘᴏsᴛ:</b> {sc_error}</blockquote>")
