from hydrogram import Client, filters
from hydrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from plugins.start import UPLOAD_STATE
from database import save_movie_files
from extractor import extract_file_info
from template import to_small_caps # --- IMPORTED TO_SMALL_CAPS ---

@Client.on_message((filters.document | filters.video) & filters.private)
async def handle_media(client: Client, message: Message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    user_state = UPLOAD_STATE.get(message.from_user.id)
    if not user_state:
        await message.reply_text(">⚠️ ᴘʟᴇᴀsᴇ sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴠɪᴇ ғʀᴏᴍ ᴛʜᴇ /start ᴍᴇɴᴜ ғɪʀsᴛ.")
        return

    # Initialize the file array and status if this is the first file
    if "files" not in user_state:
        user_state["files"] = []
        user_state["status"] = "receiving"

    if user_state["status"] != "receiving":
        await message.reply_text(">⚠️ ᴄᴜʀʀᴇɴᴛʟʏ ᴡᴀɪᴛɪɴɢ ғᴏʀ ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋs. ᴘʟᴇᴀsᴇ ғɪɴɪsʜ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ sᴛᴇᴘ.")
        return

    # 1. Extract File Metadata
    doc = message.document or message.video
    file_name = getattr(doc, "file_name", "")
    file_size = getattr(doc, "file_size", 0)
    
    info = extract_file_info(file_name, file_size)
    quality = info.get("Resolution", "Unknown")

    # 2. Forward to Dump Channel to get secure file_id
    dump_msg = await message.forward(Config.DUMP_CHANNEL_ID)
    secure_file_id = dump_msg.document.file_id if dump_msg.document else dump_msg.video.file_id

    # 3. Store in temporary session
    user_state["files"].append({
        "quality": quality,
        "file_size": info["Size"],
        "file_id": secure_file_id,
        "mediafire_link": None
    })

    # 4. Generate Summary Text
    sc_title = to_small_caps(user_state["title"])
    count = len(user_state["files"])
    qualities = [f["quality"] for f in user_state["files"]]
    sc_qualities = to_small_caps(', '.join(qualities))
    
    summary_text = (
        f">📥 **{sc_title}**\n"
        f">\n"
        f">✅ {count} ғɪʟᴇ(s) ʀᴇᴄᴇɪᴠᴇᴅ & ғᴏʀᴡᴀʀᴅᴇᴅ.\n"
        f">📺 **ǫᴜᴀʟɪᴛɪᴇs:** {sc_qualities}\n"
        f">\n"
        f">sᴇɴᴅ ᴍᴏʀᴇ ғɪʟᴇs, ᴏʀ ᴄʟɪᴄᴋ ᴄᴏɴғɪʀᴍ."
    )
    
    buttons = [
        [InlineKeyboardButton("✅ ᴄᴏɴғɪʀᴍ & ᴀᴅᴅ ʟɪɴᴋs", callback_data="confirm_files")],
        [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ ᴜᴘʟᴏᴀᴅ", callback_data="cancel_upload")]
    ]
    markup = InlineKeyboardMarkup(buttons)

    # 5. Edit the existing status message or send a new one
    if "status_msg_id" in user_state:
        await client.edit_message_text(
            chat_id=message.chat.id,
            message_id=user_state["status_msg_id"],
            text=summary_text,
            reply_markup=markup
        )
    else:
        status_msg = await message.reply_text(summary_text, reply_markup=markup)
        user_state["status_msg_id"] = status_msg.id


@Client.on_callback_query(filters.regex("^confirm_files$"))
async def start_mediafire_collection(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return
        
    user_state = UPLOAD_STATE.get(query.from_user.id)
    if not user_state or not user_state.get("files"):
        await query.answer(to_small_caps("ɴᴏ ғɪʟᴇs ғᴏᴜɴᴅ."), show_alert=True)
        return

    # Transition state to asking for links
    user_state["status"] = "waiting_for_mediafire"
    user_state["mf_index"] = 0
    
    first_file = user_state["files"][0]
    sc_quality = to_small_caps(first_file['quality'])
    sc_size = to_small_caps(first_file['file_size'])
    
    text = (
        f">🔗 **ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋs ʀᴇǫᴜɪʀᴇᴅ**\n"
        f">\n"
        f">ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋ ғᴏʀ:\n"
        f">👉 **{sc_quality}** ({sc_size})"
    )
    await query.message.edit_text(text)

@Client.on_message(filters.text & filters.private)
async def handle_mediafire_links(client: Client, message: Message):
    if message.from_user.id != Config.ADMIN_ID:
        # Allow start.py and channel.py to process other text messages
        message.continue_propagation()
        return
        
    user_state = UPLOAD_STATE.get(message.from_user.id)
    if not user_state or user_state.get("status") != "waiting_for_mediafire":
        message.continue_propagation()
        return

    idx = user_state["mf_index"]
    
    # Save the link
    user_state["files"][idx]["mediafire_link"] = message.text
    user_state["mf_index"] += 1

    # Check if we need more links
    if user_state["mf_index"] < len(user_state["files"]):
        next_file = user_state["files"][user_state["mf_index"]]
        sc_quality = to_small_caps(next_file['quality'])
        sc_size = to_small_caps(next_file['file_size'])
        
        text = (
            f">✅ ʟɪɴᴋ sᴀᴠᴇᴅ.\n"
            f">\n"
            f">ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋ ғᴏʀ:\n"
            f">👉 **{sc_quality}** ({sc_size})"
        )
        await message.reply_text(text)
    else:
        # All links collected! Save to Database
        await save_movie_files(user_state["watch_order"], user_state["files"])
        
        sc_title = to_small_caps(user_state['title'])
        text = (
            f">🎉 **ᴜᴘʟᴏᴀᴅ ᴄᴏᴍᴘʟᴇᴛᴇ!**\n"
            f">\n"
            f">🎬 {sc_title}\n"
            f">✅ {len(user_state['files'])} ǫᴜᴀʟɪᴛɪᴇs sᴀᴠᴇᴅ ᴛᴏ ᴅᴀᴛᴀʙᴀsᴇ.\n"
            f">\n"
            f">ᴜsᴇ `/post` ᴛᴏ ᴘᴜʙʟɪsʜ ᴛʜɪs ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ."
        )
        await message.reply_text(text)
        
        # Clear state
        del UPLOAD_STATE[message.from_user.id]

@Client.on_callback_query(filters.regex("^cancel_upload$"))
async def cancel_upload(client: Client, query: CallbackQuery):
    if query.from_user.id == Config.ADMIN_ID and query.from_user.id in UPLOAD_STATE:
        del UPLOAD_STATE[query.from_user.id]
        await query.message.edit_text(">❌ ᴜᴘʟᴏᴀᴅ ᴄᴀɴᴄᴇʟʟᴇᴅ. sᴇssɪᴏɴ ᴄʟᴇᴀʀᴇᴅ.")
