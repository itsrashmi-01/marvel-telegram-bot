import time
import hashlib
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import MessageNotModified
from database import get_movie_by_order
from template import to_small_caps
from config import Config

# ==========================================
# FIRE AND FORGET TASK MANAGER
# ==========================================
background_tasks = set()

async def delete_messages_later(client: Client, chat_id: int, message_ids: list, delay: int = 300):
    """Waits 5 minutes (300s), deletes the messages/files, and notifies the user."""
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_ids)
        await client.send_message(
            chat_id,
            "<blockquote>🗑️ <b>ғɪʟᴇs & ʟɪɴᴋs ᴅᴇʟᴇᴛᴇᴅ!</b>\n\n"
            "ғᴏʀ ᴄᴏᴘʏʀɪɢʜᴛ & sᴇᴄᴜʀɪᴛʏ ʀᴇᴀsᴏɴs, ᴛʜᴇ ᴍᴇssᴀɢᴇs ʜᴀᴠᴇ ʙᴇᴇɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ʀᴇᴍᴏᴠᴇᴅ ᴀғᴛᴇʀ 𝟻 ᴍɪɴᴜᴛᴇs.\n\n"
            "👉 <i>ɪғ ʏᴏᴜ ᴍɪssᴇᴅ ᴛʜᴇᴍ, ᴘʟᴇᴀsᴇ ᴄʟɪᴄᴋ ᴛʜᴇ ᴅᴏᴡɴʟᴏᴀᴅ ʙᴜᴛᴛᴏɴ ᴀɢᴀɪɴ!</i></blockquote>"
        )
    except Exception as e:
        print(f"Failed to delete messages for {chat_id}: {e}")

def schedule_auto_delete(client: Client, chat_id: int, message_ids: list, delay: int = 300):
    task = asyncio.create_task(delete_messages_later(client, chat_id, message_ids, delay))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


# ==========================================
# 1. STEP 1: CHANNEL -> DOWNLOAD PAGE LINK
#    Triggered by: ?start=get_<order>
# ==========================================
@Client.on_message(filters.regex(r"^/start get_(\d+)$") & filters.private)
async def handle_web_page_link(client: Client, message: Message):
    order = int(message.matches[0].group(1))
    movie = await get_movie_by_order(order)
    
    if not movie or not movie.get("files"):
        return await message.reply_text(
            "<blockquote>❌ <b>sᴏʀʀʏ!</b>\n\nᴛʜɪs ᴍᴏᴠɪᴇ ɪs ᴇɪᴛʜᴇʀ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ ᴏʀ ᴛʜᴇ ʟɪɴᴋ ɪs ʙʀᴏᴋᴇɴ.</blockquote>"
        )

    sc_title = to_small_caps(movie["title"])
    base_url = getattr(Config, "DOWNLOAD_PAGE_URL", "")
    secret_key = getattr(Config, "SECRET_KEY", "")
    
    if not base_url:
        return await message.reply_text("<blockquote>⚠️ <b>ᴇʀʀᴏʀ:</b> ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ ᴜʀʟ ɪs ɴᴏᴛ ᴄᴏɴғɪɢᴜʀᴇᴅ.</blockquote>")
        
    if not secret_key or secret_key == "generate_a_random_password_here":
        return await message.reply_text("<blockquote>⚠️ <b>ᴇʀʀᴏʀ:</b> sᴇᴄʀᴇᴛ_ᴋᴇʏ ɪs ɴᴏᴛ ᴄᴏɴғɪɢᴜʀᴇᴅ ɪɴ ʏᴏᴜʀ ᴇɴᴠɪʀᴏɴᴍᴇɴᴛ.</blockquote>")

    # Generate Cryptographic Secure Link (Valid for 1 Hour)
    expires = int(time.time()) + 3600
    hash_data = f"{order}{expires}{secret_key}".encode()
    secure_hash = hashlib.sha256(hash_data).hexdigest()

    download_link = f"{base_url}?id={order}&t={expires}&hash={secure_hash}"
    text = (
        f"<blockquote>🎬 <b>{sc_title}</b>\n\n"
        f"✅ <b>ʏᴏᴜʀ sᴇᴄᴜʀᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ ɪs ʀᴇᴀᴅʏ!</b>\n"
        f"ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴄʜᴏᴏsᴇ <b>ᴅɪʀᴇᴄᴛ ᴅᴏᴡɴʟᴏᴀᴅ</b> ᴏʀ <b>ᴛᴇʟᴇɢʀᴀᴍ ғɪʟᴇ</b>.\n\n"
        f"⏳ <i>ʟɪɴᴋ ᴇxᴘɪʀᴇs ɪɴ 𝟷 ʜᴏᴜʀ • ᴍᴇssᴀɢᴇ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇs ɪɴ 𝟻 ᴍɪɴs.</i></blockquote>"
    )
    buttons = [[InlineKeyboardButton(to_small_caps("🌐 ᴏᴘᴇɴ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ"), url=download_link)]]
    
    link_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    schedule_auto_delete(client, message.chat.id, [link_msg.id], 300)


# ==========================================
# 2. STEP 2: WEBSITE TELEGRAM TAB -> ACTUAL FILE
#    Triggered by: ?start=file_<order>_<index>
# ==========================================
@Client.on_message(filters.regex(r"^/start file_(\d+)_(\d+)$") & filters.private)
async def handle_actual_file_delivery(client: Client, message: Message):
    order = int(message.matches[0].group(1))
    file_idx = int(message.matches[0].group(2))
    
    movie = await get_movie_by_order(order)
    if not movie or not movie.get("files"):
        return await message.reply_text(
            "<blockquote>❌ <b>sᴏʀʀʏ!</b>\n\nᴛʜɪs ᴍᴏᴠɪᴇ ɪs ɴᴏ ʟᴏɴɢᴇʀ ᴀᴠᴀɪʟᴀʙʟᴇ.</blockquote>"
        )

    files = movie["files"]
    if file_idx < 0 or file_idx >= len(files):
        return await message.reply_text(
            "<blockquote>❌ <b>ɪɴᴠᴀʟɪᴅ ǫᴜᴀʟɪᴛʏ sᴇʟᴇᴄᴛɪᴏɴ!</b>\n\nᴘʟᴇᴀsᴇ ʀᴇ-ᴏᴘᴇɴ ᴛʜᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.</blockquote>"
        )

    target_file = files[file_idx]
    sc_title = to_small_caps(movie["title"])
    quality = target_file.get("quality", "HD")
    size = target_file.get("file_size") or target_file.get("size") or ""
    audio = movie.get("audio", "English")
    file_id = target_file.get("file_id")
    msg_id = target_file.get("msg_id")

    caption = (
        f"<blockquote>🎬 <b>{sc_title}</b>\n\n"
        f"💿 <b>ǫᴜᴀʟɪᴛʏ:</b> {to_small_caps(quality)}\n"
        f"🔊 <b>ᴀᴜᴅɪᴏ:</b> {to_small_caps(audio)}\n"
        f"{f'📦 <b>sɪᴢᴇ:</b> {to_small_caps(size)}' if size else ''}</blockquote>"
    )

    messages_to_delete = []
    sent_file_msg = None

    try:
        # Method A: If msg_id was stored from DUMP_CHANNEL_ID, copy_message works across different bots
        if msg_id and getattr(Config, "DUMP_CHANNEL_ID", None):
            sent_file_msg = await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=Config.DUMP_CHANNEL_ID,
                message_id=int(msg_id),
                caption=caption
            )
        # Method B: Fallback to send_cached_media / send_document
        elif file_id:
            try:
                sent_file_msg = await client.send_cached_media(
                    chat_id=message.chat.id,
                    file_id=file_id,
                    caption=caption
                )
            except Exception:
                sent_file_msg = await client.send_document(
                    chat_id=message.chat.id,
                    document=file_id,
                    caption=caption
                )
    except Exception as e:
        print(f"Error delivering file for movie {order}: {e}")
        return await message.reply_text(
            "<blockquote>⚠️ <b>ғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ғɪʟᴇ!</b>\n\n"
            "ᴍᴀᴋᴇ sᴜʀᴇ ᴛʜᴇ ғɪʟᴇ sᴛᴏʀᴇ ʙᴏᴛ ɪs ᴀɴ <b>ᴀᴅᴍɪɴ</b> ɪɴ ᴛʜᴇ ᴅᴜᴍᴘ ᴄʜᴀɴɴᴇʟ.</blockquote>"
        )

    if sent_file_msg:
        messages_to_delete.append(sent_file_msg.id)

    # Send 5-Minute Auto-Delete Instructions
    warning_text = (
        "<blockquote>⚠️ <b>ɪᴍᴘᴏʀᴛᴀɴᴛ ɪɴsᴛʀᴜᴄᴛɪᴏɴs</b>\n\n"
        "⏳ ᴛʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ <b>ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ɪɴ 𝟻 ᴍɪɴᴜᴛᴇs</b> ᴛᴏ ᴘʀᴇᴠᴇɴᴛ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs.\n\n"
        "📌 <b>ʜᴏᴡ ᴛᴏ sᴀᴠᴇ:</b>\n"
        "• ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇ ᴀʙᴏᴠᴇ ᴛᴏ ʏᴏᴜʀ <b>sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs</b> ᴏʀ ᴀɴᴏᴛʜᴇʀ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ ɪᴍᴍᴇᴅɪᴀᴛᴇʟʏ.\n"
        "• ᴏɴᴄᴇ ғᴏʀᴡᴀʀᴅᴇᴅ, ʏᴏᴜ ᴄᴀɴ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ᴡᴀᴛᴄʜ ɪᴛ ᴀɴʏᴛɪᴍᴇ!</blockquote>"
    )
    warning_msg = await message.reply_text(warning_text)
    messages_to_delete.append(warning_msg.id)

    # Start 5-minute (300s) deletion timer
    schedule_auto_delete(client, message.chat.id, messages_to_delete, 300)


# ==========================================
# 3. EMPTY /start COMMAND & START MENU UI
# ==========================================
def get_start_menu_Payload(user_first_name: str):
    sc_name = to_small_caps(user_first_name or "User")
    web_url = getattr(Config, "DOWNLOAD_PAGE_URL", "https://itsrashmi.in")
    main_channel_url = getattr(Config, "MAIN_CHANNEL_URL", "https://t.me/")

    text = (
        f"<blockquote>👋 <b>ʜᴇʟʟᴏ {sc_name}!</b>\n"
        f"ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ <b>ᴛʜᴇ ᴍᴏᴠɪᴇ ɢᴜʏ — ғɪʟᴇ sᴛᴏʀᴇ ʙᴏᴛ</b> 🎬\n\n"
        f"ɪ ᴀᴍ ᴛʜᴇ ᴏғғɪᴄɪᴀʟ ʜɪɢʜ-sᴘᴇᴇᴅ ғɪʟᴇ ᴅᴇʟɪᴠᴇʀʏ ʙᴏᴛ ғᴏʀ ᴛʜᴇ <b>ᴍᴀʀᴠᴇʟ ᴜɴɪᴠᴇʀsᴇ ᴡᴀᴛᴄʜ ᴏʀᴅᴇʀ</b>.\n\n"
        f"🔹 <b>ʜᴏᴡ ᴛᴏ ɢᴇᴛ ᴍᴏᴠɪᴇs:</b>\n"
        f"𝟷. ᴠɪsɪᴛ ᴏᴜʀ ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ ᴏʀ ᴡᴇʙ ʀᴏᴀᴅᴍᴀᴘ.\n"
        f"𝟸. ᴄʟɪᴄᴋ ᴛʜᴇ <b>ᴅᴏᴡɴʟᴏᴀᴅ</b> ʙᴜᴛᴛᴏɴ ᴏɴ ᴀɴʏ ᴍᴏᴠɪᴇ.\n"
        f"𝟹. ᴄʜᴏᴏsᴇ ʏᴏᴜʀ ᴘʀᴇғᴇʀʀᴇᴅ ǫᴜᴀʟɪᴛʏ (𝟺𝟾𝟶ᴘ / 𝟽𝟸𝟶ᴘ / 𝟷𝟶𝟾𝟶ᴘ) ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ɪɴsᴛᴀɴᴛ ғɪʟᴇs!</blockquote>"
    )
    buttons = [
        [
            InlineKeyboardButton(to_small_caps("📢 ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ"), url=main_channel_url),
            InlineKeyboardButton(to_small_caps("🌐 ᴡᴇʙ ʀᴏᴀᴅᴍᴀᴘ"), url=web_url)
        ],
        [
            InlineKeyboardButton(to_small_caps("📖 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ"), callback_data="fs_help"),
            InlineKeyboardButton(to_small_caps("ℹ️ ᴀʙᴏᴜᴛ ʙᴏᴛ"), callback_data="fs_about")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

@Client.on_message(filters.command("start") & filters.private)
async def handle_empty_start(client: Client, message: Message):
    # Ignore if it has a deep-link parameter handled above
    if len(message.command) > 1 and (
        message.command[1].startswith("get_") or message.command[1].startswith("file_")
    ):
        return

    text, markup = get_start_menu_Payload(message.from_user.first_name)
    await message.reply_text(text, reply_markup=markup)

@Client.on_callback_query(filters.regex(r"^fs_(home|help|about)$"))
async def handle_start_menu_callbacks(client: Client, query: CallbackQuery):
    action = query.data.split("_")[1]
    
    if action == "home":
        text, markup = get_start_menu_Payload(query.from_user.first_name)
    elif action == "help":
        text = (
            "<blockquote>📖 <b>ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ᴍᴏᴠɪᴇs</b>\n\n"
            "𝟷️⃣ <b>ғʀᴏᴍ ᴛᴇʟᴇɢʀᴀᴍ ᴄʜᴀɴɴᴇʟ:</b>\n"
            "ᴄʟɪᴄᴋ ᴛʜᴇ <b>ᴅᴏᴡɴʟᴏᴀᴅ</b> ʙᴜᴛᴛᴏɴ ᴜɴᴅᴇʀ ᴀɴʏ ᴍᴏᴠɪᴇ ᴘᴏsᴛ. ɪ ᴡɪʟʟ ɢᴇɴᴇʀᴀᴛᴇ ᴀ sᴇᴄᴜʀᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ ʟɪɴᴋ ғᴏʀ ʏᴏᴜ.\n\n"
            "𝟸️⃣ <b>ᴄʜᴏᴏsᴇ ᴅɪʀᴇᴄᴛ ᴏʀ ᴛᴇʟᴇɢʀᴀᴍ:</b>\n"
            "• <b>ᴅɪʀᴇᴄᴛ ᴛᴀʙ:</b> ᴅᴏᴡɴʟᴏᴀᴅs ɪɴsᴛᴀɴᴛʟʏ ɪɴ ʏᴏᴜʀ ʙʀᴏᴡsᴇʀ.\n"
            "• <b>ᴛᴇʟᴇɢʀᴀᴍ ᴛᴀʙ:</b> sᴇɴᴅs ᴛʜᴇ ᴠɪᴅᴇᴏ ғɪʟᴇ ᴅɪʀᴇᴄᴛʟʏ ɪɴ ᴛʜɪs ᴄʜᴀᴛ.\n\n"
            "⏳ <b>sᴀᴠᴇ ʏᴏᴜʀ ғɪʟᴇs:</b>\n"
            "ᴀʟʟ ғɪʟᴇs ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴀғᴛᴇʀ <b>𝟻 ᴍɪɴᴜᴛᴇs</b>. ғᴏʀᴡᴀʀᴅ ᴛʜᴇᴍ ᴛᴏ <b>sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs</b> ᴛᴏ ᴋᴇᴇᴘ ᴛʜᴇᴍ ғᴏʀᴇᴠᴇʀ!</blockquote>"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ"), callback_data="fs_home")]])
    else:
        text = (
            "<blockquote>ℹ️ <b>ᴀʙᴏᴜᴛ ᴛʜᴇ ᴍᴏᴠɪᴇ ɢᴜʏ ʙᴏᴛ</b>\n\n"
            "🤖 <b>ɴᴀᴍᴇ:</b> ᴛʜᴇ ᴍᴏᴠɪᴇ ɢᴜʏ (ғɪʟᴇ sᴛᴏʀᴇ)\n"
            "⚡ <b>sᴇᴄᴜʀɪᴛʏ:</b> sʜᴀ-𝟸𝟻𝟼 ᴛᴏᴋᴇɴ ᴘʀᴏᴛᴇᴄᴛᴇᴅ\n"
            "☁️ <b>ɢᴀᴛᴇᴡᴀʏ:</b> ᴄʟᴏᴜᴅғʟᴀʀᴇ ᴡᴏʀᴋᴇʀs + ᴍᴏɴɢᴏᴅʙ\n"
            "👨‍💻 <b>ᴅᴇᴠᴇʟᴏᴘᴇʀ:</b> ᴛʜᴇ ᴍᴏᴠɪᴇ ɢᴜʏ</blockquote>"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ"), callback_data="fs_home")]])

    try:
        await query.message.edit_text(text, reply_markup=markup)
    except MessageNotModified:
        pass
    await query.answer()


# ==========================================
# 4. FALLBACK FOR OTHER RANDOM MESSAGES
# ==========================================
@Client.on_message(filters.private & ~filters.command("start"))
async def file_bot_fallback(client: Client, message: Message):
    buttons = [[InlineKeyboardButton(to_small_caps("🏠 ᴏᴘᴇɴ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="fs_home")]]
    await message.reply_text(
        "<blockquote>👋 <b>ɪ ᴀᴍ ᴀɴ ᴀᴜᴛᴏᴍᴀᴛᴇᴅ ғɪʟᴇ ᴘʀᴏᴠɪᴅᴇʀ ʙᴏᴛ.</b>\n\n"
        "ᴘʟᴇᴀsᴇ ᴜsᴇ ᴛʜᴇ ᴅᴏᴡɴʟᴏᴀᴅ ʙᴜᴛᴛᴏɴs ɪɴ ᴏᴜʀ ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ ᴏʀ ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴠɪᴇᴡ ᴛʜᴇ ᴍᴇɴᴜ.</blockquote>",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
