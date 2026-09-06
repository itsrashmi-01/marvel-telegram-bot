import time
import hashlib
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_movie_by_order
from template import to_small_caps
from config import Config

# ==========================================
# FIRE AND FORGET TASK MANAGER
# ==========================================
# This prevents Python's garbage collector from killing the 5-minute timer early
background_tasks = set()

async def delete_messages_later(client: Client, chat_id: int, message_ids: list, delay: int = 300):
    """Waits for a set time, deletes messages, and notifies the user."""
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_ids)
        await client.send_message(
            chat_id,
            "<blockquote>🗑️ <b>ғɪʟᴇs ᴅᴇʟᴇᴛᴇᴅ!</b>\n\nFᴏʀ sᴇᴄᴜʀɪᴛʏ ʀᴇᴀsᴏɴs, ᴛʜᴇ ʟɪɴᴋs ᴀɴᴅ ғɪʟᴇs ʜᴀᴠᴇ ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ ᴀғᴛᴇʀ 𝟻 ᴍɪɴᴜᴛᴇs.\n\nIғ ʏᴏᴜ ᴍɪssᴇᴅ ᴛʜᴇᴍ, ᴘʟᴇᴀsᴇ ʀᴇǫᴜᴇsᴛ ᴛʜᴇᴍ ᴀɢᴀɪɴ ғʀᴏᴍ ᴛʜᴇ ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ!</blockquote>"
        )
    except Exception as e:
        print(f"Failed to delete messages for {chat_id}: {e}")


# ==========================================
# DEEP LINK HANDLER (Redirect & Direct Files)
# ==========================================
@Client.on_message(filters.regex(r"^/start get_(\d+)") & filters.private)
async def handle_deep_link_download(client: Client, message: Message):
    # 1. Extract the movie watch_order ID from the link
    order = int(message.matches[0].group(1))
    
    # 2. Verify the movie actually exists in the database
    movie = await get_movie_by_order(order)
    
    if not movie or not movie.get("files"):
        return await message.reply_text("<blockquote>❌ <b>sᴏʀʀʏ!</b>\n\nᴛʜɪs ᴍᴏᴠɪᴇ ɪs ᴇɪᴛʜᴇʀ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ ᴏʀ ᴛʜᴇ ʟɪɴᴋ ɪs ʙʀᴏᴋᴇɴ.</blockquote>")

    sc_title = to_small_caps(movie['title'])
    base_url = getattr(Config, "DOWNLOAD_PAGE_URL", "")
    secret_key = getattr(Config, "SECRET_KEY", "")
    
    if not base_url:
        return await message.reply_text("<blockquote>⚠️ <b>ᴇʀʀᴏʀ:</b> ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ ᴜʀʟ ɪs ɴᴏᴛ ᴄᴏɴғɪɢᴜʀᴇᴅ.</blockquote>")
        
    if not secret_key or secret_key == "generate_a_random_password_here":
        return await message.reply_text("<blockquote>⚠️ <b>ᴇʀʀᴏʀ:</b> sᴇᴄʀᴇᴛ_ᴋᴇʏ ɪs ɴᴏᴛ ᴄᴏɴғɪɢᴜʀᴇᴅ ɪɴ ʏᴏᴜʀ ᴇɴᴠɪʀᴏɴᴍᴇɴᴛ.</blockquote>")

    # List to store all message IDs we need to delete later
    messages_to_delete = []

    # 3. Generate Cryptographic Secure Link (Valid for 1 Hour)
    expires = int(time.time()) + 3600 
    hash_data = f"{order}{expires}{secret_key}".encode()
    secure_hash = hashlib.sha256(hash_data).hexdigest()

    # 4. Send the Secure Web URL
    download_link = f"{base_url}?id={order}&t={expires}&hash={secure_hash}"
    text = (
        f"<blockquote>🎬 <b>{sc_title}</b>\n\n"
        f"ʏᴏᴜʀ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ ɪs ʀᴇᴀᴅʏ! ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋs.\n\n"
        f"⏳ <i>ᴛʜɪs ʟɪɴᴋ ɪs sᴇᴄᴜʀᴇ ᴀɴᴅ ᴡɪʟʟ ᴇxᴘɪʀᴇ ɪɴ 𝟷 ʜᴏᴜʀ.</i></blockquote>"
    )
    buttons = [[InlineKeyboardButton(to_small_caps("🌐 ᴏᴘᴇɴ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ"), url=download_link)]]
    
    link_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    messages_to_delete.append(link_msg.id)

    # 5. Send Direct Files from Database
    for f in movie["files"]:
        file_id = f.get("file_id")
        quality = f.get("quality", "Unknown Quality")
        
        if file_id:
            try:
                # Using send_cached_media or send_document handles standard Telegram file_ids
                file_msg = await client.send_document(
                    chat_id=message.chat.id,
                    document=file_id,
                    caption=f"<blockquote>🎬 <b>{sc_title}</b>\n💿 <b>{quality}</b></blockquote>"
                )
                messages_to_delete.append(file_msg.id)
            except Exception as e:
                print(f"Failed to send file {file_id}: {e}")

    # 6. Send Deletion Warning
    warning_text = (
        "<blockquote>⚠️ <b>ᴀᴛᴛᴇɴᴛɪᴏɴ!</b>\n\n"
        "Aʟʟ ғɪʟᴇs ᴀɴᴅ ʟɪɴᴋs ᴀʙᴏᴠᴇ ᴡɪʟʟ ʙᴇ <b>ᴅᴇʟᴇᴛᴇᴅ ɪɴ 𝟻 ᴍɪɴᴜᴛᴇs</b>.\n\n"
        "👉 <i>Pʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇ ғɪʟᴇs ᴛᴏ ʏᴏᴜʀ <b>Sᴀᴠᴇᴅ Mᴇssᴀɢᴇs</b> ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴋᴇᴇᴘ ᴛʜᴇᴍ!</i></blockquote>"
    )
    warning_msg = await message.reply_text(warning_text)
    messages_to_delete.append(warning_msg.id)

    # 7. FIRE AND FORGET THE DELETION TASK
    task = asyncio.create_task(delete_messages_later(client, message.chat.id, messages_to_delete, 300))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


# ==========================================
# FALLBACK HANDLER
# ==========================================
@Client.on_message(filters.private & ~filters.regex(r"^/start get_(\d+)"))
async def file_bot_fallback(client: Client, message: Message):
    await message.reply_text("<blockquote>👋 ɪ ᴀᴍ ᴀ ғɪʟᴇ ᴘʀᴏᴠɪᴅᴇʀ ʙᴏᴛ.\n\nᴘʟᴇᴀsᴇ ᴜsᴇ ᴍʏ ʟɪɴᴋs ɪɴ ᴛʜᴇ ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇs ᴀɴᴅ ɢᴇᴛ ғɪʟᴇs.</blockquote>")
