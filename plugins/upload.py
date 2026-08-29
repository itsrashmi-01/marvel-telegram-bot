from hydrogram import Client, filters
from hydrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from plugins.start import UPLOAD_STATE
from database import add_or_update_file

# Temporary memory to store the file until quality is selected
TEMP_UPLOADS = {}

@Client.on_message(filters.document | filters.video)
async def handle_media(client: Client, message: Message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    # Check if a movie is currently selected for upload in UPLOAD_STATE
    user_state = UPLOAD_STATE.get(message.from_user.id)
    if not user_state:
        await message.reply_text(
            "⚠️ Please select a movie from the /start **Upload Movie** menu before sending a file."
        )
        return
    
    file_id = message.document.file_id if message.document else message.video.file_id
    
    # Extract file size (in MB/GB)
    file_size_bytes = message.document.file_size if message.document else message.video.file_size
    if file_size_bytes > 1024 * 1024 * 1024:
        size_str = f"{file_size_bytes / (1024 * 1024 * 1024):.2f} GB"
    else:
        size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB"
        
    watch_order = user_state["watch_order"]
    title = user_state["title"]

    # Store file temporarily so the user can select the quality
    TEMP_UPLOADS[message.from_user.id] = {
        "file_id": file_id,
        "size_str": size_str,
        "watch_order": watch_order,
        "title": title
    }
    
    # Build Quality Selection Buttons
    buttons = [
        [
            InlineKeyboardButton("480p", callback_data="setquality_480p"),
            InlineKeyboardButton("720p", callback_data="setquality_720p")
        ],
        [
            InlineKeyboardButton("1080p", callback_data="setquality_1080p"),
            InlineKeyboardButton("4K UHD", callback_data="setquality_4K")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_upload")]
    ]
    
    await message.reply_text(
        f"🎬 **{title}**\n"
        f"📦 **Size:** {size_str}\n\n"
        f"Select the resolution/quality for this file:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^setquality_(.+)$"))
async def finalize_upload(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return
        
    quality = query.data.split("_")[1]
    upload_data = TEMP_UPLOADS.get(query.from_user.id)
    
    if not upload_data:
        await query.answer("Session expired or invalid.", show_alert=True)
        return
        
    # Save the file into the database using the new advanced function
    await add_or_update_file(
        watch_order=upload_data["watch_order"],
        quality=quality,
        file_size=upload_data["size_str"],
        file_id=upload_data["file_id"]
    )
    
    # Clear the temporary states
    del TEMP_UPLOADS[query.from_user.id]
    if query.from_user.id in UPLOAD_STATE:
        del UPLOAD_STATE[query.from_user.id]
        
    await query.message.edit_text(
        f"✅ **Upload Complete!**\n\n"
        f"🎬 {upload_data['title']}\n"
        f"📺 Quality: {quality} | {upload_data['size_str']}\n\n"
        f"File saved to database successfully."
    )

@Client.on_callback_query(filters.regex("^cancel_upload$"))
async def cancel_upload(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return
        
    if query.from_user.id in TEMP_UPLOADS:
        del TEMP_UPLOADS[query.from_user.id]
    if query.from_user.id in UPLOAD_STATE:
        del UPLOAD_STATE[query.from_user.id]
        
    await query.message.edit_text("❌ Upload cancelled.")
