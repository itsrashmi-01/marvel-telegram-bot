from hydrogram import Client, filters
from hydrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from plugins.start import UPLOAD_STATE
from database import save_movie_files, get_movie_by_order
from extractor import extract_file_info
from template import to_small_caps, format_movie_post

@Client.on_message((filters.document | filters.video) & filters.private)
async def handle_media(client: Client, message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    user_state = UPLOAD_STATE.get(message.from_user.id)
    if not user_state:
        await message.reply_text("<blockquote>⚠️ ᴘʟᴇᴀsᴇ sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴠɪᴇ ғʀᴏᴍ ᴛʜᴇ /start ᴍᴇɴᴜ ғɪʀsᴛ.</blockquote>")
        return
    if "files" not in user_state:
        user_state["files"] = []
        user_state["status"] = "receiving"

    if user_state["status"] != "receiving":
        await message.reply_text("<blockquote>⚠️ ᴄᴜʀʀᴇɴᴛʟʏ ᴡᴀɪᴛɪɴɢ ғᴏʀ ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋs. ᴘʟᴇᴀsᴇ ғɪɴɪsʜ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ sᴛᴇᴘ.</blockquote>")
        return

    doc = message.document or message.video
    file_name = getattr(doc, "file_name", "")
    file_size = getattr(doc, "file_size", 0)
    info = extract_file_info(file_name, file_size)

    dump_msg = await message.forward(Config.DUMP_CHANNEL_ID)
    secure_file_id = dump_msg.document.file_id if dump_msg.document else dump_msg.video.file_id

    user_state["files"].append({
        "quality": info["quality"],
        "file_id": secure_file_id,
        "mediafire_link": None,
        "file_size": info["size"],
        "release": info["release"],
        "audio": info["audio"]
    })

    sc_title = to_small_caps(user_state["title"])
    count = len(user_state["files"])
    qualities = [f["quality"] for f in user_state["files"]]
    sc_qualities = to_small_caps(', '.join(qualities))
    
    summary_text = (
        f"<blockquote>📥 <b>{sc_title}</b>\n\n"
        f"✅ {count} ғɪʟᴇ(s) ʀᴇᴄᴇɪᴠᴇᴅ & ғᴏʀᴡᴀʀᴅᴇᴅ.\n"
        f"📺 <b>ǫᴜᴀʟɪᴛɪᴇs:</b> {sc_qualities}\n\n"
        f"sᴇɴᴅ ᴍᴏʀᴇ ғɪʟᴇs, ᴏʀ ᴄʟɪᴄᴋ ᴄᴏɴғɪʀᴍ.</blockquote>"
    )
    buttons = [
        [InlineKeyboardButton("✅ ᴄᴏɴғɪʀᴍ & ᴀᴅᴅ ʟɪɴᴋs", callback_data="confirm_files")],
        [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ ᴜᴘʟᴏᴀᴅ", callback_data="cancel_upload")]
    ]
    markup = InlineKeyboardMarkup(buttons)

    if "status_msg_id" in user_state:
        await client.edit_message_text(chat_id=message.chat.id, message_id=user_state["status_msg_id"], text=summary_text, reply_markup=markup)
    else:
        status_msg = await message.reply_text(summary_text, reply_markup=markup)
        user_state["status_msg_id"] = status_msg.id

@Client.on_callback_query(filters.regex("^confirm_files$"))
async def start_mediafire_collection(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    user_state = UPLOAD_STATE.get(query.from_user.id)
    if not user_state or not user_state.get("files"):
        return await query.answer(to_small_caps("ɴᴏ ғɪʟᴇs ғᴏᴜɴᴅ."), show_alert=True)

    user_state["status"] = "waiting_for_mediafire"
    user_state["mf_index"] = 0
    first_file = user_state["files"][0]
    sc_quality = to_small_caps(first_file['quality'])
    sc_size = to_small_caps(first_file['file_size'])
    sc_release = to_small_caps(first_file['release'])
    
    text = (
        f"<blockquote>🔗 <b>ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋs ʀᴇǫᴜɪʀᴇᴅ</b>\n\n"
        f"ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋ ғᴏʀ:\n"
        f"👉 <b>{sc_quality} {sc_release}</b> ({sc_size})</blockquote>"
    )
    await query.message.edit_text(text)

@Client.on_message(filters.text & filters.private)
async def handle_mediafire_links(client: Client, message: Message):
    if message.from_user.id != Config.ADMIN_ID:
        message.continue_propagation()
        return
    user_state = UPLOAD_STATE.get(message.from_user.id)
    if not user_state or user_state.get("status") != "waiting_for_mediafire":
        message.continue_propagation()
        return

    idx = user_state["mf_index"]
    user_state["files"][idx]["mediafire_link"] = message.text
    user_state["mf_index"] += 1

    if user_state["mf_index"] < len(user_state["files"]):
        next_file = user_state["files"][user_state["mf_index"]]
        sc_quality = to_small_caps(next_file['quality'])
        sc_size = to_small_caps(next_file['file_size'])
        sc_release = to_small_caps(next_file['release'])
        
        text = (
            f"<blockquote>✅ ʟɪɴᴋ sᴀᴠᴇᴅ.\n\n"
            f"ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋ ғᴏʀ:\n"
            f"👉 <b>{sc_quality} {sc_release}</b> ({sc_size})</blockquote>"
        )
        await message.reply_text(text)
    else:
        # All links collected! Generate Final Preview
        order = user_state["watch_order"]
        db_movie = await get_movie_by_order(order)
        
        # Temporarily merge extracted files into movie dict for preview formatting
        db_movie["files"] = user_state["files"] 
        caption = format_movie_post(db_movie)
        poster_url = db_movie.get("images", {}).get("poster_url", "")
        
        buttons = [
            [InlineKeyboardButton(to_small_caps("💾 sᴀᴠᴇ ᴛᴏ ᴅᴀᴛᴀʙᴀsᴇ"), callback_data=f"save_db_{order}")],
            [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_upload")]
        ]
        
        if poster_url:
            await client.send_photo(message.chat.id, photo=poster_url, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await client.send_message(message.chat.id, text=caption, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^save_db_(\d+)$"))
async def save_to_database(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID: return
    order = int(query.data.split("_")[2])
    user_state = UPLOAD_STATE.get(query.from_user.id)
    
    if not user_state:
        return await query.answer("sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ.", show_alert=True)
        
    await save_movie_files(order, user_state["files"])
    await query.message.edit_reply_markup(reply_markup=None) # Remove buttons
    await client.send_message(query.message.chat.id, "<blockquote>✅ <b>sᴀᴠᴇᴅ ᴛᴏ ᴅᴀᴛᴀʙᴀsᴇ sᴜᴄᴄᴇssғᴜʟʟʏ!</b></blockquote>")
    del UPLOAD_STATE[query.from_user.id]

@Client.on_callback_query(filters.regex("^cancel_upload$"))
async def cancel_upload(client: Client, query: CallbackQuery):
    if query.from_user.id == Config.ADMIN_ID and query.from_user.id in UPLOAD_STATE:
        del UPLOAD_STATE[query.from_user.id]
        if query.message.photo:
            await query.message.delete()
            await client.send_message(query.message.chat.id, "<blockquote>❌ ᴜᴘʟᴏᴀᴅ ᴄᴀɴᴄᴇʟʟᴇᴅ. sᴇssɪᴏɴ ᴄʟᴇᴀʀᴇᴅ.</blockquote>")
        else:
            await query.message.edit_text("<blockquote>❌ ᴜᴘʟᴏᴀᴅ ᴄᴀɴᴄᴇʟʟᴇᴅ. sᴇssɪᴏɴ ᴄʟᴇᴀʀᴇᴅ.</blockquote>")
