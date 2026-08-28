from hydrogram import Client, filters
from hydrogram.types import Message
from config import Config
from database import save_movie

# Temporary memory to store the file_id while waiting for the title
upload_state = {}

@Client.on_message(filters.document | filters.video)
async def handle_media(client: Client, message: Message):
    # Security: Ignore uploads from anyone except you
    if message.from_user.id != Config.ADMIN_ID:
        return
    
    file_id = message.document.file_id if message.document else message.video.file_id
    upload_state[message.from_user.id] = {"file_id": file_id, "type": "Video"}
    
    await message.reply_text("File received! What is the title of this Marvel movie or series?")

@Client.on_message(filters.text & filters.private)
async def handle_text(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != Config.ADMIN_ID:
        return
        
    state = upload_state.get(user_id)
    if state and "file_id" in state:
        title = message.text
        
        # Save to MongoDB using database.py
        await save_movie(title, state["file_id"], state["type"])
        
        # Clear the upload state
        del upload_state[user_id]
        
        await message.reply_text(f"✅ Success! **{title}** has been saved to the MongoDB database.")
