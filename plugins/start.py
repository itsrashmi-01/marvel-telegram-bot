from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram.errors import MessageNotModified
from config import Config
from plugins.list import RAW_MARVEL_LIST
from database import movies_col, get_target_channels, add_target_channel, remove_target_channel, get_movie_by_order, init_marvel_list
from template import to_small_caps

UPLOAD_STATE = {}
WAITING_FOR_CHANNEL = {}

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
        buttons.append([
            InlineKeyboardButton(to_small_caps("📤 ᴜᴘʟᴏᴀᴅ ᴍᴏᴠɪᴇ"), callback_data="upload_menu"),
            InlineKeyboardButton(to_small_caps("📝 ᴘᴜʙʟɪsʜ ᴘᴏsᴛs"), callback_data="post_menu_back")
        ])
        buttons.append([
            InlineKeyboardButton(to_small_caps("📢 ᴍʏ ᴄʜᴀɴɴᴇʟs"), callback_data="manage_channel"),
            InlineKeyboardButton(to_small_caps("⚙️ sᴇᴛᴛɪɴɢs"), callback_data="settings_menu")
        ])
        
    user_name = to_small_caps(message.from_user.first_name)
    text = (
        f"<blockquote>👋 <b>ᴡᴇʟᴄᴏᴍᴇ {user_name}!</b>\n\n"
        f"ɪ ᴀᴍ ᴛʜᴇ ᴍᴀʀᴠᴇʟ ᴜɴɪᴠᴇʀsᴇ ᴍᴇᴅɪᴀ ʙᴏᴛ.\n"
        f"ᴄʟɪᴄᴋ ᴀ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴍᴀɴᴀɢᴇ ᴛʜᴇ ᴅᴀᴛᴀʙᴀsᴇ.</blockquote>"
    )
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)

@Client.on_callback_query(filters.regex("^main_menu$"))
async def return_main_menu(client: Client, query: CallbackQuery):
    buttons = [
        [
            InlineKeyboardButton(to_small_caps("📤 ᴜᴘʟᴏᴀᴅ ᴍᴏᴠɪᴇ"), callback_data="upload_menu"),
            InlineKeyboardButton(to_small_caps("📝 ᴘᴜʙʟɪsʜ ᴘᴏsᴛs"), callback_data="post_menu_back")
        ],
        [
            InlineKeyboardButton(to_small_caps("📢 ᴍʏ ᴄʜᴀɴɴᴇʟs"), callback_data="manage_channel"),
            InlineKeyboardButton(to_small_caps("⚙️ sᴇᴛᴛɪɴɢs"), callback_data="settings_menu")
        ]
    ]
    text = (
        "<blockquote>👋 <b>ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ ᴛᴏ ᴛʜᴇ ᴍᴀɪɴ ᴍᴇɴᴜ!</b>\n\n"
        "ᴄʟɪᴄᴋ ᴀ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴍᴀɴᴀɢᴇ ᴛʜᴇ ᴅᴀᴛᴀʙᴀsᴇ.</blockquote>"
    )
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        try: await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: pass

@Client.on_callback_query(filters.regex("^settings_menu$"))
async def settings_menu_handler(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    buttons = [[InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")]]
    text = "<blockquote>⚙️ <b>sᴇᴛᴛɪɴɢs</b>\n\nғᴜᴛᴜʀᴇ ᴄᴏɴғɪɢᴜʀᴀᴛɪᴏɴs ᴀɴᴅ ᴏᴘᴛɪᴏɴs ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ʜᴇʀᴇ.</blockquote>"
    try: await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified: pass

# --- UPLOAD MENU ---
@Client.on_callback_query(filters.regex("^upload_menu$"))
async def upload_menu_selection(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(to_small_caps(f"📂 {full_name}"), callback_data=f"saga_{code}_1")])
    buttons.append([InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")])

    text = "<blockquote>📤 <b>sᴇʟᴇᴄᴛ ᴀ ᴜɴɪᴠᴇʀsᴇ/sᴀɢᴀ ᴛᴏ ᴠɪᴇᴡ ɪᴛs ᴍᴏᴠɪᴇs:</b></blockquote>"
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        try: await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: pass

@Client.on_callback_query(filters.regex(r"^saga_(.+)_(\d+)$"))
async def saga_pagination(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
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
    total_pages = (len(saga_movies) + items_per_page - 1) // items_per_page
    start_idx = (page - 1) * items_per_page
    
    buttons = []
    for item in saga_movies[start_idx : start_idx + items_per_page]:
        status_icon = "🟢" if item["order"] in uploaded_set else "🔴"
        btn_text = f"{status_icon} " + to_small_caps(item['title'])
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"init_upload_{item['order']}")])
        
    nav = []
    if page > 1: nav.append(InlineKeyboardButton(to_small_caps("⬅️ ᴘʀᴇᴠ"), callback_data=f"saga_{code}_{page-1}"))
    if page < total_pages: nav.append(InlineKeyboardButton(to_small_caps("ɴᴇxᴛ ➡️"), callback_data=f"saga_{code}_{page+1}"))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ sᴀɢᴀs"), callback_data="upload_menu")])

    sc_saga_name = to_small_caps(full_saga_name)
    text = (
        f"<blockquote>📂 <b>{sc_saga_name}</b>\n\n"
        f"🟢 = ᴜᴘʟᴏᴀᴅᴇᴅ | 🔴 = ᴍɪssɪɴɢ\n"
        f"sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴠɪᴇ ᴛᴏ ᴜᴘʟᴏᴀᴅ:</blockquote>"
    )
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        try: await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified: pass

@Client.on_callback_query(filters.regex(r"^init_upload_(\d+)$"))
async def init_upload(client: Client, query: CallbackQuery):
    order = int(query.data.split("_")[2])
    raw_movie = next((m for m in RAW_MARVEL_LIST if m["order"] == order), None)
    
    if raw_movie:
        movie = await get_movie_by_order(order)
        if not movie:
            await query.answer(to_small_caps("ғᴇᴛᴄʜɪɴɢ ᴛᴍᴅʙ ᴍᴇᴛᴀᴅᴀᴛᴀ... ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ."), show_alert=False)
            bot_info = await client.get_me()
            await init_marvel_list([raw_movie], bot_username=bot_info.username)
            
        UPLOAD_STATE[query.from_user.id] = {"watch_order": order, "title": raw_movie["title"]}
        sc_title = to_small_caps(raw_movie["title"])
        text = (
            f"<blockquote>🎬 <b>ʀᴇᴀᴅʏ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ғɪʟᴇs ғᴏʀ:</b> {sc_title}\n\n"
            f"👇 <b>ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴏʀ ᴜᴘʟᴏᴀᴅ ᴛʜᴇ ᴠɪᴅᴇᴏ ғɪʟᴇs ɴᴏᴡ.</b>\n"
            f"(ʏᴏᴜ ᴄᴀɴ sᴇɴᴅ ᴍᴜʟᴛɪᴘʟᴇ ғɪʟᴇs ᴏɴᴇ ᴀғᴛᴇʀ ᴛʜᴇ ᴏᴛʜᴇʀ.)</blockquote>"
        )
        await query.message.delete()
        await client.send_message(chat_id=query.message.chat.id, text=text)
    else:
        await query.answer("ᴇʀʀᴏʀ ɪɴɪᴛɪᴀᴛɪɴɢ ᴜᴘʟᴏᴀᴅ.", show_alert=True)

# --- CHANNEL MANAGEMENT UI ---
@Client.on_callback_query(filters.regex("^manage_channel$"))
async def channel_manager_menu(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    if query.from_user.id in WAITING_FOR_CHANNEL: del WAITING_FOR_CHANNEL[query.from_user.id]
    
    channels = await get_target_channels()
    buttons = []
    channel_text = ""
    
    if channels:
        for ch in channels:
            sc_name = to_small_caps(ch['name'])
            channel_text += f"• <b>{sc_name}</b> (<code>{ch['id']}</code>)\n"
            buttons.append([InlineKeyboardButton(to_small_caps(f"🗑 ᴅᴇʟᴇᴛᴇ {ch['name'][:15]}"), callback_data=f"del_chan_{ch['id']}")])
    else:
        channel_text = "❌ ɴᴏ ᴄʜᴀɴɴᴇʟs ᴀᴅᴅᴇᴅ\n"
        
    buttons.append([InlineKeyboardButton(to_small_caps("➕ ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ"), callback_data="set_new_channel")])
    buttons.append([InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")])
    
    text = (
        f"<blockquote>📢 <b>ᴄʜᴀɴɴᴇʟ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ</b>\n\n"
        f"<b>ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟs:</b>\n{channel_text}\n"
        f"ᴍᴀᴋᴇ sᴜʀᴇ ᴛʜᴇ ʙᴏᴛ ɪs ᴀᴅᴅᴇᴅ ᴀs ᴀɴ <b>ᴀᴅᴍɪɴ</b> ɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs!</blockquote>"
    )
    try: await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified: pass

@Client.on_callback_query(filters.regex(r"^del_chan_(-?\d+)$"))
async def delete_channel(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    chan_id = int(query.data.split("_")[2])
    await remove_target_channel(chan_id)
    await query.answer(to_small_caps("ᴄʜᴀɴɴᴇʟ ᴅᴇʟᴇᴛᴇᴅ!"), show_alert=True)
    await channel_manager_menu(client, query)

@Client.on_callback_query(filters.regex("^set_new_channel$"))
async def ask_for_channel(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    WAITING_FOR_CHANNEL[query.from_user.id] = True
    buttons = [[InlineKeyboardButton(to_small_caps("❌ ᴄᴀɴᴄᴇʟ"), callback_data="manage_channel")]]
    text = (
        "<blockquote>👇 <b>ʜᴏᴡ ᴛᴏ ʟɪɴᴋ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ:</b>\n\n"
        "𝟷. ɢᴏ ᴛᴏ ʏᴏᴜʀ ᴛᴀʀɢᴇᴛ ᴄʜᴀɴɴᴇʟ.\n"
        "𝟸. ғᴏʀᴡᴀʀᴅ ᴀɴʏ ᴍᴇssᴀɢᴇ ғʀᴏᴍ ᴛʜᴀᴛ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴍᴇ ʀɪɢʜᴛ ɴᴏᴡ.\n"
        "(ᴏʀ, ʏᴏᴜ ᴄᴀɴ ᴊᴜsᴛ ᴛʏᴘᴇ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ɪᴅ ɪғ ʏᴏᴜ ᴋɴᴏᴡ ɪᴛ, ᴇ.ɢ., -𝟷𝟶𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿)</blockquote>"
    )
    try: await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified: pass

@Client.on_message(filters.private & filters.user(Config.ADMIN_ID))
async def capture_channel_input(client: Client, message: Message):
    if not WAITING_FOR_CHANNEL.get(message.from_user.id):
        message.continue_propagation()
        return
    
    channel_id = None
    if message.forward_from_chat and message.forward_from_chat.type.name == "CHANNEL":
        channel_id = message.forward_from_chat.id
    else:
        try: channel_id = int(message.text)
        except (ValueError, TypeError):
            return await message.reply_text("<blockquote>❌ ɪɴᴠᴀʟɪᴅ ɪɴᴘᴜᴛ. ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴀ ᴍᴇssᴀɢᴇ ᴏʀ sᴇɴᴅ ᴀ -𝟷𝟶𝟶 ɪᴅ.</blockquote>")
            
    try:
        chat = await client.get_chat(channel_id)
        channel_name = chat.title
    except Exception:
        channel_name = f"Unknown Channel ({channel_id})"
        
    await add_target_channel(channel_id, channel_name)
    del WAITING_FOR_CHANNEL[message.from_user.id]
    
    sc_channel_name = to_small_caps(channel_name)
    buttons = [[InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴄʜᴀɴɴᴇʟ ᴍᴇɴᴜ"), callback_data="manage_channel")]]
    text = (
        f"<blockquote>✅ <b>ᴄʜᴀɴɴᴇʟ sᴜᴄᴄᴇssғᴜʟʟʏ ᴀᴅᴅᴇᴅ!</b>\n\n"
        f"<b>ɴᴀᴍᴇ:</b> {sc_channel_name}\n"
        f"<b>ɪᴅ:</b> <code>{channel_id}</code>\n\n"
        f"ᴍᴀᴋᴇ sᴜʀᴇ ᴛᴏ ᴀᴅᴅ ᴛʜᴇ ʙᴏᴛ ᴀs ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜɪs ᴄʜᴀɴɴᴇʟ sᴏ ɪᴛ ᴄᴀɴ ᴘᴏsᴛ.</blockquote>"
    )
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
