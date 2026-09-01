from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
# IMPORT get_target_channel from database
from database import movies_col, get_movie_by_order, get_target_channel
from plugins.start import SAGA_CATEGORIES

@Client.on_message(filters.command("post") & filters.private)
async def post_command_handler(client: Client, message: Message):
    """Starts the interactive menu to select a movie to publish to the channel."""
    if message.from_user.id != Config.ADMIN_ID:
        return
        
    # FETCH DYNAMICALLY FROM DATABASE
    target_channel = await get_target_channel()
    if not target_channel:
        await message.reply_text("⚠️ **No channel linked!**\nUse the '📢 My Channel' button in the /start menu to link your channel first.")
        return

    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(f"📢 {full_name}", callback_data=f"post_saga_{code}_1")])
        
    await message.reply_text(
        "📢 **Select a Universe/Saga to publish a movie from:**\n"
        "(Only movies with uploaded files will be shown here)",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^post_saga_(.+)_(\d+)$"))
async def post_saga_pagination(client: Client, query: CallbackQuery):
    """Displays only AVAILABLE movies inside a selected Saga for posting."""
    if query.from_user.id != Config.ADMIN_ID:
        return

    code = query.data.split("_")[2]
    page = int(query.data.split("_")[3])
    full_saga_name = SAGA_CATEGORIES.get(code)
    
    if not full_saga_name:
        await query.answer("Invalid Saga", show_alert=True)
        return

    # Fetch ONLY uploaded/available movies for this saga
    available_movies = await movies_col.find(
        {"saga": full_saga_name, "status": "Available"}
    ).sort("saga_rank", 1).to_list(length=100)

    if not available_movies:
        await query.answer("No movies uploaded in this saga yet!", show_alert=True)
        return

    # Pagination Logic
    items_per_page = 10
    total_items = len(available_movies)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_items = available_movies[start_idx:end_idx]
    
    buttons = []
    for item in current_items:
        btn_text = f"📢 {item['title']} ({item.get('release_year', '')})"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"confirm_post_{item['watch_order']}")])
        
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"post_saga_{code}_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"post_saga_{code}_{page+1}"))
    
    if nav:
        buttons.append(nav)
        
    buttons.append([InlineKeyboardButton("🔙 Back to Sagas", callback_data="post_menu_back")])

    await query.message.edit_text(
        f"📢 **Publishing from: {full_saga_name}**\n\n"
        f"Select a movie to generate a channel post:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^confirm_post_(\d+)$"))
async def publish_to_channel(client: Client, query: CallbackQuery):
    """Generates the formatted post and sends it to the target channel."""
    if query.from_user.id != Config.ADMIN_ID:
        return

    order = int(query.data.split("_")[2])
    movie = await get_movie_by_order(order)
    
    # FETCH DYNAMICALLY FROM DATABASE
    target_channel = await get_target_channel()
    
    if not target_channel:
        await query.answer("No channel linked! Link it in /start.", show_alert=True)
        return
        
    if not movie or not movie.get("files"):
        await query.answer("Movie or files not found!", show_alert=True)
        return

    await query.answer("Publishing to channel...")
    
    # 1. Format the Post Caption
    genres_str = ", ".join(movie.get("genres", []))
    caption = (
        f"🎬 **{movie['title']} ({movie.get('release_year', 'N/A')})**\n\n"
        f"📂 **Saga:** {movie.get('saga')}\n"
        f"🔊 **Audio:** {movie.get('language')}\n"
        f"🏷️ **Genres:** {genres_str}\n"
        f"⭐ **Rating:** {movie.get('rating', 'N/A')}/10\n\n"
        f"📝 **Synopsis:**\n_{movie.get('overview', 'No synopsis available.')}_\n\n"
        f"👇 **Click below to get your files!**"
    )

    # 2. Build the deep-link button
    bot_info = await client.get_me()
    bot_username = bot_info.username
    deep_link = f"https://t.me/{bot_username}?start=get_{order}"
    
    buttons = [
        [InlineKeyboardButton("📥 Download Movie (All Qualities)", url=deep_link)]
    ]
    
    markup = InlineKeyboardMarkup(buttons)
    poster_url = movie.get("images", {}).get("poster_url")

    try:
        # 3. Send to target_channel
        if poster_url:
            await client.send_photo(
                chat_id=target_channel,
                photo=poster_url,
                caption=caption,
                reply_markup=markup
            )
        else:
            await client.send_message(
                chat_id=target_channel,
                text=caption,
                reply_markup=markup
            )
            
        await query.message.edit_text(
            f"✅ **Successfully published to channel!**\n\n"
            f"🎬 {movie['title']}"
        )
    except Exception as e:
        await query.message.edit_text(f"❌ **Failed to post:** {e}\n\n(Did you forget to add the bot as an Admin in the channel?)")

@Client.on_callback_query(filters.regex("^post_menu_back$"))
async def post_menu_back(client: Client, query: CallbackQuery):
    """Returns to the main post saga menu."""
    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(f"📢 {full_name}", callback_data=f"post_saga_{code}_1")])
        
    await query.message.edit_text(
        "📢 **Select a Universe/Saga to publish a movie from:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
