import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_movie_by_order
from template import to_small_caps

# ==========================================
# BACKGROUND AUTO-DELETE TASK
# ==========================================
async def delete_after_delay(client: Client, chat_id: int, message_ids: list, delay_seconds: int):
    """Waits for the specified time and then deletes the messages."""
    await asyncio.sleep(delay_seconds)
    for msg_id in message_ids:
        try:
            await client.delete_messages(chat_id=chat_id, message_ids=msg_id)
        except Exception as e:
            print(f"Failed to delete message {msg_id}: {e}")
            pass

# ==========================================
# DEEP LINK HANDLER
# ==========================================
@Client.on_message(filters.regex(r"^/start get_(\d+)") & filters.private)
async def handle_deep_link_download(client: Client, message: Message):
    # 1. Extract the watch order from the regex match
    order = int(message.matches[0].group(1))
    
    # 2. Fetch the movie from the database
    movie = await get_movie_by_order(order)
    if not movie or not movie.get("files"):
        text = "<blockquote>❌ <b>sᴏʀʀʏ!</b>\n\nᴛʜɪs ᴍᴏᴠɪᴇ ɪs ᴇɪᴛʜᴇʀ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ ᴏʀ ᴛʜᴇ ʟɪɴᴋ ɪs ʙʀᴏᴋᴇɴ.</blockquote>"
        await message.reply_text(text)
        return

    # 3. Send a warning message about the 5-minute auto-delete
    sc_title = to_small_caps(movie['title'])
    warning_text = (
        f"<blockquote>⚠️ <b>ᴀᴛᴛᴇɴᴛɪᴏɴ!</b>\n\n"
        f"ʏᴏᴜ ᴀʀᴇ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ: <b>{sc_title}</b>\n\n"
        f"ᴛᴏ ᴘʀᴏᴛᴇᴄᴛ ᴀɢᴀɪɴsᴛ ᴄᴏᴘʏʀɪɢʜᴛ sᴛʀɪᴋᴇs, ᴛʜᴇsᴇ ғɪʟᴇs ᴀɴᴅ ʟɪɴᴋs ᴡɪʟʟ ʙᴇ <b>ᴅᴇʟᴇᴛᴇᴅ ɪɴ 𝟻 ᴍɪɴᴜᴛᴇs</b>.\n\n"
        f"👉 ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇᴍ ᴛᴏ ʏᴏᴜʀ 'sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs' ᴏʀ ᴅᴏᴡɴʟᴏᴀᴅ ᴛʜᴇᴍ ɪᴍᴍᴇᴅɪᴀᴛᴇʟʏ!</blockquote>"
    )
    warning_msg = await message.reply_text(warning_text)
    
    # Keep track of all messages to delete them later
    messages_to_delete = [warning_msg.id, message.id] 

    # 4. Loop through the database files and send them
    for f in movie["files"]:
        quality = to_small_caps(f.get("quality", "Unknown"))
        size = to_small_caps(f.get("file_size", "Unknown"))
        
        # Build the MediaFire button
        buttons = []
        if f.get("mediafire_link"):
            buttons.append([InlineKeyboardButton(to_small_caps(f"🔗 ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋ ({quality})"), url=f["mediafire_link"])])
        
        markup = InlineKeyboardMarkup(buttons) if buttons else None
        
        caption = (
            f"<blockquote>🎬 <b>{sc_title}</b>\n\n"
            f"📦 <b>ǫᴜᴀʟɪᴛʏ:</b> {quality}\n"
            f"💾 <b>sɪᴢᴇ:</b> {size}</blockquote>"
        )

        try:
            # send_cached_media automatically detects if it's a video or document based on file_id
            sent_msg = await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=f["file_id"],
                caption=caption,
                reply_markup=markup
            )
            messages_to_delete.append(sent_msg.id)
            # Short sleep to prevent flood limits when sending multiple qualities
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Error sending file_id {f.get('file_id')}: {e}")

    # 5. Trigger the auto-delete countdown in the background (300 seconds = 5 minutes)
    if len(messages_to_delete) > 2: # Ensures we actually sent files
        asyncio.create_task(delete_after_delay(client, message.chat.id, messages_to_delete, 300))
