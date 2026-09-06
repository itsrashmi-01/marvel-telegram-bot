from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_movie_by_order
from template import to_small_caps
from config import Config

# ==========================================
# DEEP LINK HANDLER (Redirect to Website)
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
    
    if not base_url:
        return await message.reply_text("<blockquote>⚠️ <b>ᴇʀʀᴏʀ:</b> ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ ᴜʀʟ ɪs ɴᴏᴛ ᴄᴏɴғɪɢᴜʀᴇᴅ.</blockquote>")

    # 3. Construct the Web URL (e.g., https://site.com/download?id=12)
    download_link = f"{base_url}?id={order}"
    
    text = (
        f"<blockquote>🎬 <b>{sc_title}</b>\n\n"
        f"ʏᴏᴜʀ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ ɪs ʀᴇᴀᴅʏ! ᴄʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇs ᴀɴᴅ ʟɪɴᴋs.</blockquote>"
    )
    
    buttons = [[InlineKeyboardButton(to_small_caps("🌐 ᴏᴘᴇɴ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇ"), url=download_link)]]
    
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ==========================================
# FALLBACK HANDLER
# ==========================================
@Client.on_message(filters.private & ~filters.regex(r"^/start get_(\d+)"))
async def file_bot_fallback(client: Client, message: Message):
    await message.reply_text("<blockquote>👋 ɪ ᴀᴍ ᴀ ғɪʟᴇ ᴘʀᴏᴠɪᴅᴇʀ ʙᴏᴛ.\n\nᴘʟᴇᴀsᴇ ᴜsᴇ ᴍʏ ʟɪɴᴋs ɪɴ ᴛʜᴇ ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴘᴀɢᴇs.</blockquote>")
