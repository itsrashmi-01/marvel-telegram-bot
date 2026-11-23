import base64
import json
import logging
import os
import re

import aiohttp
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram.errors import MessageNotModified
from config import Config
from plugins.list import RAW_MARVEL_LIST
from database import (
    movies_col,
    get_target_channels,
    add_target_channel,
    remove_target_channel,
    get_movie_by_order,
    init_marvel_list,
)
from template import to_small_caps
from product_service import CATEGORIES, ProductRepository

logger = logging.getLogger(__name__)

UPLOAD_STATE = {}
WAITING_FOR_CHANNEL = {}
PENDING_PRODUCT_LINK = {}
WAITING_FOR_PRODUCT_LINK = {}

products_repo = ProductRepository()
URL_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)

GITHUB_REPO = (getattr(Config, "GITHUB_REPO", "") or os.environ.get("GITHUB_REPO") or "itsrashmi-01/marvel-telegram-bot").strip()
GITHUB_BRANCH = (getattr(Config, "GITHUB_BRANCH", "") or os.environ.get("GITHUB_BRANCH") or "main").strip()
GITHUB_PRODUCTS_PATH = (
    getattr(Config, "GITHUB_PRODUCTS_PATH", "")
    or os.environ.get("GITHUB_PRODUCTS_PATH")
    or "worker/products.json"
).strip().lstrip("/")
GITHUB_TOKEN = (getattr(Config, "GITHUB_TOKEN", "") or os.environ.get("GITHUB_TOKEN") or "").strip()

SAGA_CATEGORIES = {
    "mcu": "MCU + Defenders Saga",
    "multi": "Multiverse Saga",
    "f4": "Fantastic Four Universe",
    "xmen": "X-Men / Fox Universe",
}


def _is_admin(user) -> bool:
    return bool(user and Config.ADMIN_ID and user.id == Config.ADMIN_ID)


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(to_small_caps("📤 ᴜᴘʟᴏᴀᴅ ᴍᴏᴠɪᴇ"), callback_data="upload_menu"),
            InlineKeyboardButton(to_small_caps("🛍️ ᴀᴅᴅ ᴘʀᴏᴅᴜᴄᴛ"), callback_data="add_product_menu"),
        ],
        [
            InlineKeyboardButton(to_small_caps("📝 ᴘᴜʙʟɪsʜ ᴘᴏsᴛs"), callback_data="post_menu_back"),
            InlineKeyboardButton(to_small_caps("📢 ᴍʏ ᴄʜᴀɴɴᴇʟs"), callback_data="manage_channel"),
        ],
        [
            InlineKeyboardButton(to_small_caps("⚙️ sᴇᴛᴛɪɴɢs"), callback_data="settings_menu"),
        ],
    ])


def _has_file_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(to_small_caps("✅ ʏᴇs, ɪ ʜᴀᴠᴇ ғɪʟᴇ"), callback_data="has_file_yes"),
            InlineKeyboardButton(to_small_caps("⏭️ ɴᴏ, sᴋɪᴘ ғɪʟᴇ"), callback_data="has_file_no"),
        ],
        [InlineKeyboardButton(to_small_caps("✘ ᴄᴀɴᴄᴇʟ ᴜᴘʟᴏᴀᴅ"), callback_data="cancel_upload")],
    ])


def _product_category_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for idx in range(0, len(CATEGORIES), 2):
        row = []
        for offset in range(2):
            cat_idx = idx + offset
            if cat_idx < len(CATEGORIES):
                cat_name = CATEGORIES[cat_idx]
                row.append(
                    InlineKeyboardButton(
                        to_small_caps(cat_name),
                        callback_data=f"prod_cat_{cat_idx}",
                    )
                )
        rows.append(row)
    rows.append([InlineKeyboardButton(to_small_caps("✘ ᴄᴀɴᴄᴇʟ"), callback_data="cancel_add_product")])
    return InlineKeyboardMarkup(rows)


async def _append_product_to_github_json(item: dict) -> bool:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PRODUCTS_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Jarvis-Bot/1.0",
    }

    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        sha = None
        existing_items = []

        async with session.get(api_url, params={"ref": GITHUB_BRANCH}) as get_resp:
            if get_resp.status == 200:
                payload = await get_resp.json()
                sha = payload.get("sha")
                raw_b64 = (payload.get("content") or "").replace("\n", "")
                if raw_b64:
                    decoded = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
                    parsed = json.loads(decoded)
                    if isinstance(parsed, list):
                        existing_items = parsed
                    elif isinstance(parsed, dict) and isinstance(parsed.get("products"), list):
                        existing_items = parsed["products"]
            elif get_resp.status != 404:
                err_txt = await get_resp.text()
                raise RuntimeError(f"GitHub GET failed ({get_resp.status}): {err_txt}")

        entry = {
            "id": str(item.get("id") or item.get("_id") or f"prod-{len(existing_items) + 1}"),
            "title": str(item.get("title") or "Product").strip(),
            "price": str(item.get("price") or "").strip(),
            "platform": str(item.get("platform") or "Store").strip(),
            "category": str(item.get("category") or "General").strip(),
            "image": str(item.get("image") or "").strip(),
            "url": str(item.get("url") or item.get("source_url") or "#").strip(),
        }

        existing_items = [
            x for x in existing_items
            if not (
                isinstance(x, dict)
                and x.get("url")
                and x.get("url") == entry["url"]
                and x.get("category") == entry["category"]
            )
        ]
        existing_items.append(entry)

        updated_text = json.dumps(existing_items, indent=2, ensure_ascii=False) + "\n"
        encoded_content = base64.b64encode(updated_text.encode("utf-8")).decode("ascii")

        put_body = {
            "message": f"Add product: {entry['title'][:60]}",
            "content": encoded_content,
            "branch": GITHUB_BRANCH,
        }
        if sha:
            put_body["sha"] = sha

        async with session.put(api_url, json=put_body) as put_resp:
            if put_resp.status not in (200, 201):
                err_txt = await put_resp.text()
                raise RuntimeError(f"GitHub PUT failed ({put_resp.status}): {err_txt}")

    return True


async def add_product_to_db(raw_link: str, category: str) -> dict:
    """Fetches product metadata, converts via EarnKaro, and persists to GitHub products.json (with DB save)."""
    saved = await products_repo.save_product(raw_link, category)
    try:
        pushed = await _append_product_to_github_json(saved)
        if not pushed:
            logger.warning("GITHUB_TOKEN not configured; skipped updating %s", GITHUB_PRODUCTS_PATH)
    except Exception as exc:
        logger.warning("Failed updating %s on GitHub: %s", GITHUB_PRODUCTS_PATH, exc)
    return saved


@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    admin = _is_admin(message.from_user)
    first_name = message.from_user.first_name if message.from_user else "User"
    user_name = to_small_caps(first_name)
    text = (
        f"<blockquote>👋 <b>ᴡᴇʟᴄᴏᴍᴇ {user_name}!</b>\n\n"
        f"ɪ ᴀᴍ ᴛʜᴇ ᴍᴀʀᴠᴇʟ ᴜɴɪᴠᴇʀsᴇ ᴍᴇᴅɪᴀ ʙᴏᴛ.\n"
        f"ᴄʟɪᴄᴋ ᴀ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴍᴀɴᴀɢᴇ ᴛʜᴇ ᴅᴀᴛᴀʙᴀsᴇ.</blockquote>"
    )
    await message.reply_text(
        text,
        reply_markup=_main_menu_keyboard() if admin else None,
    )


@Client.on_callback_query(filters.regex("^main_menu$"))
async def return_main_menu(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    user_id = query.from_user.id
    WAITING_FOR_CHANNEL.pop(user_id, None)
    WAITING_FOR_PRODUCT_LINK.pop(user_id, None)
    PENDING_PRODUCT_LINK.pop(user_id, None)

    text = (
        "<blockquote>👋 <b>ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ ᴛᴏ ᴛʜᴇ ᴍᴀɪɴ ᴍᴇɴᴜ!</b>\n\n"
        "ᴄʟɪᴄᴋ ᴀ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴍᴀɴᴀɢᴇ ᴛʜᴇ ᴅᴀᴛᴀʙᴀsᴇ.</blockquote>"
    )
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=_main_menu_keyboard())
    else:
        try:
            await query.message.edit_text(text, reply_markup=_main_menu_keyboard())
        except MessageNotModified:
            pass


# --- ADD PRODUCT FLOW ---
@Client.on_callback_query(filters.regex("^add_product_menu$"))
async def add_product_menu_handler(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    user_id = query.from_user.id
    WAITING_FOR_CHANNEL.pop(user_id, None)
    PENDING_PRODUCT_LINK.pop(user_id, None)
    WAITING_FOR_PRODUCT_LINK[user_id] = True

    buttons = [[InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")]]
    text = (
        "<blockquote>🛍️ <b>ᴀᴅᴅ ᴘʀᴏᴅᴜᴄᴛ</b>\n\n"
        "sᴇɴᴅ ᴛʜᴇ <b>ᴘʀᴏᴅᴜᴄᴛ ʟɪɴᴋ</b> ɴᴏᴡ.\n"
        "ᴀғᴛᴇʀ ʏᴏᴜ sᴇɴᴅ ᴛʜᴇ ʟɪɴᴋ, ɪ ᴡɪʟʟ sʜᴏᴡ ᴄᴀᴛᴇɢᴏʀɪᴇs ᴛᴏ sᴀᴠᴇ ɪᴛ ᴡɪᴛʜ ᴇᴀʀɴᴋᴀʀᴏ ᴄᴏɴᴠᴇʀsɪᴏɴ.</blockquote>"
    )
    await query.answer()
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        pass


@Client.on_callback_query(filters.regex("^cancel_add_product$"))
async def cancel_add_product_handler(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    user_id = query.from_user.id
    WAITING_FOR_PRODUCT_LINK.pop(user_id, None)
    PENDING_PRODUCT_LINK.pop(user_id, None)
    await query.answer(to_small_caps("ᴄᴀɴᴄᴇʟʟᴇᴅ!"), show_alert=False)
    await return_main_menu(client, query)


@Client.on_callback_query(filters.regex(r"^prod_cat_(\d+)$"))
async def select_product_category_handler(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    user_id = query.from_user.id
    product_url = PENDING_PRODUCT_LINK.get(user_id)
    if not product_url:
        await query.answer(to_small_caps("ʟɪɴᴋ ᴇxᴘɪʀᴇᴅ. sᴇɴᴅ ᴛʜᴇ ᴘʀᴏᴅᴜᴄᴛ ʟɪɴᴋ ᴀɢᴀɪɴ."), show_alert=True)
        return

    cat_idx = int(query.matches[0].group(1))
    if cat_idx < 0 or cat_idx >= len(CATEGORIES):
        await query.answer(to_small_caps("ɪɴᴠᴀʟɪᴅ ᴄᴀᴛᴇɢᴏʀʏ."), show_alert=True)
        return

    chosen_category = CATEGORIES[cat_idx]
    await query.answer(to_small_caps("ғᴇᴛᴄʜɪɴɢ ᴅᴇᴛᴀɪʟs & sᴀᴠɪɴɢ..."), show_alert=False)
    try:
        await query.message.edit_text(
            f"<blockquote>⏳ <b>ᴘʀᴏᴄᴇssɪɴɢ {to_small_caps(chosen_category)}...</b>\n\n"
            f"ғᴇᴛᴄʜɪɴɢ ᴅᴇᴛᴀɪʟs & ɢᴇɴᴇʀᴀᴛɪɴɢ ᴇᴀʀɴᴋᴀʀᴏ ʟɪɴᴋ.</blockquote>"
        )
    except MessageNotModified:
        pass

    try:
        saved = await add_product_to_db(product_url, chosen_category)
        PENDING_PRODUCT_LINK.pop(user_id, None)
        WAITING_FOR_PRODUCT_LINK.pop(user_id, None)

        price_line = f"<b>ᴘʀɪᴄᴇ:</b> <code>{saved['price']}</code>\n" if saved.get("price") else ""
        buttons = [
            [InlineKeyboardButton(to_small_caps("➕ ᴀᴅᴅ ᴀɴᴏᴛʜᴇʀ ᴘʀᴏᴅᴜᴄᴛ"), callback_data="add_product_menu")],
            [InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")],
        ]
        text = (
            f"<blockquote>✔ <b>ᴘʀᴏᴅᴜᴄᴛ sᴀᴠᴇᴅ!</b>\n\n"
            f"<b>ᴄᴀᴛᴇɢᴏʀʏ:</b> {to_small_caps(saved['category'])}\n"
            f"<b>ᴛɪᴛʟᴇ:</b> {to_small_caps(saved['title'])}\n"
            f"{price_line}"
            f"<b>ᴘʟᴀᴛғᴏʀᴍ:</b> {to_small_caps(saved['platform'])}\n"
            f"<b>ʟɪɴᴋ:</b> <code>{saved['url']}</code></blockquote>"
        )
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as exc:
        await query.message.edit_text(
            f"<blockquote>✘ <b>ғᴀɪʟᴇᴅ ᴛᴏ sᴀᴠᴇ ᴘʀᴏᴅᴜᴄᴛ:</b>\n<code>{exc}</code></blockquote>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")]
            ]),
        )


@Client.on_callback_query(filters.regex("^settings_menu$"))
async def settings_menu_handler(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    buttons = [[InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")]]
    text = "<blockquote>⚙️ <b>sᴇᴛᴛɪɴɢs</b>\n\nғᴜᴛᴜʀᴇ ᴄᴏɴғɪɢᴜʀᴀᴛɪᴏɴs ᴀɴᴅ ᴏᴘᴛɪᴏɴs ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ʜᴇʀᴇ.</blockquote>"
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        pass


# --- UPLOAD MENU ---
@Client.on_callback_query(filters.regex("^upload_menu$"))
async def upload_menu_selection(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    buttons = []
    for code, full_name in SAGA_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(to_small_caps(f"📂 {full_name}"), callback_data=f"saga_{code}_1")])
    buttons.append([InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")])

    text = "<blockquote>📤 <b>sᴇʟᴇᴄᴛ ᴀ ᴜɴɪᴠᴇʀsᴇ/sᴀɢᴀ ᴛᴏ ᴠɪᴇᴡ ɪᴛs ᴍᴏᴠɪᴇs:</b></blockquote>"
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified:
            pass


@Client.on_callback_query(filters.regex(r"^saga_(.+)_(\d+)$"))
async def saga_pagination(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    code = query.data.split("_")[1]
    page = int(query.data.split("_")[2])
    full_saga_name = SAGA_CATEGORIES.get(code)

    saga_movies = [m for m in RAW_MARVEL_LIST if m["saga"] == full_saga_name]
    uploaded_docs = await movies_col.find(
        {"saga": full_saga_name, "files": {"$exists": True, "$not": {"$size": 0}}},
        {"watch_order": 1},
    ).to_list(length=100)
    uploaded_set = {doc["watch_order"] for doc in uploaded_docs}

    items_per_page = 10
    total_pages = (len(saga_movies) + items_per_page - 1) // items_per_page
    start_idx = (page - 1) * items_per_page

    buttons = []
    for item in saga_movies[start_idx : start_idx + items_per_page]:
        status_icon = "✔" if item["order"] in uploaded_set else "✘"
        btn_text = f"{status_icon} " + to_small_caps(item["title"])
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"init_upload_{item['order']}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(to_small_caps("⬅️ ᴘʀᴇᴠ"), callback_data=f"saga_{code}_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(to_small_caps("ɴᴇxᴛ ➡️"), callback_data=f"saga_{code}_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ sᴀɢs"), callback_data="upload_menu")])

    sc_saga_name = to_small_caps(full_saga_name)
    text = (
        f"<blockquote>📂 <b>{sc_saga_name}</b>\n\n"
        f"✔ = ᴜᴘʟᴏᴀᴅᴇᴅ | ✘ = ᴍɪssɪɴɢ\n"
        f"sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴠɪᴇ ᴛᴏ ᴜᴘʟᴏᴀᴅ:</blockquote>"
    )
    if query.message.photo:
        await query.message.delete()
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except MessageNotModified:
            pass


@Client.on_callback_query(filters.regex(r"^init_upload_(\d+)$"))
async def init_upload(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    order = int(query.data.split("_")[2])
    raw_movie = next((m for m in RAW_MARVEL_LIST if m["order"] == order), None)

    if raw_movie:
        movie = await get_movie_by_order(order)
        if not movie:
            await query.answer(to_small_caps("ғᴇᴛᴄʜɪɴɢ ᴛᴍᴅʙ ᴍᴇᴛᴀᴅᴀᴛᴀ... ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ."), show_alert=False)
            await init_marvel_list([raw_movie])
        else:
            await query.answer()

        UPLOAD_STATE[query.from_user.id] = {
            "watch_order": order,
            "title": raw_movie["title"],
            "files": [],
            "status": "ask_has_file",
        }
        sc_title = to_small_caps(raw_movie["title"])
        text = (
            f"<blockquote>🎬 <b>{sc_title}</b> (#{order})\n\n"
            f"ᴅᴏ ʏᴏᴜ ʜᴀᴠᴇ <b>ᴠɪᴅᴇᴏ / ᴅᴏᴄᴜᴍᴇɴᴛ ғɪʟᴇs</b> ᴛᴏ ᴜᴘʟᴏᴀᴅ?</blockquote>"
        )
        await query.message.delete()
        await client.send_message(
            chat_id=query.message.chat.id,
            text=text,
            reply_markup=_has_file_keyboard(),
        )
    else:
        await query.answer(to_small_caps("ᴇʀʀᴏʀ ɪɴɪᴛɪᴀᴛɪɴɢ ᴜᴘʟᴏᴀᴅ."), show_alert=True)


# --- CHANNEL MANAGEMENT UI ---
@Client.on_callback_query(filters.regex("^manage_channel$"))
async def channel_manager_menu(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    WAITING_FOR_CHANNEL.pop(query.from_user.id, None)

    channels = await get_target_channels()
    buttons = []
    channel_text = ""

    if channels:
        for ch in channels:
            sc_name = to_small_caps(ch["name"])
            channel_text += f"• <b>{sc_name}</b> (<code>{ch['id']}</code>)\n"
            buttons.append([InlineKeyboardButton(to_small_caps(f"🗑 ᴅᴇʟᴇᴛᴇ {ch['name'][:15]}"), callback_data=f"del_chan_{ch['id']}")])
    else:
        channel_text = "✘ ɴᴏ ᴄʜᴀɴɴᴇʟs ᴀᴅᴅᴇᴅ\n"

    buttons.append([InlineKeyboardButton(to_small_caps("➕ ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ"), callback_data="set_new_channel")])
    buttons.append([InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴍᴇɴᴜ"), callback_data="main_menu")])

    text = (
        f"<blockquote>📢 <b>ᴄʜᴀɴɴᴇʟ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ</b>\n\n"
        f"<b>ʟɪɴᴋᴇᴅ ᴄʜᴀɴɴᴇʟs:</b>\n{channel_text}\n"
        f"ᴍᴀᴋᴇ sᴜʀᴇ ᴛʜᴇ ʙᴏᴛ ɪs ᴀᴅᴅᴇᴅ ᴀs ᴀɴ <b>ᴀᴅᴍɪɴ</b> ɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs!</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        pass


@Client.on_callback_query(filters.regex(r"^del_chan_(-?\d+)$"))
async def delete_channel(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    chan_id = int(query.data.split("_")[2])
    await remove_target_channel(chan_id)
    await query.answer(to_small_caps("ᴄʜᴀɴɴᴇʟ ᴅᴇʟᴇᴛᴇᴅ!"), show_alert=True)
    await channel_manager_menu(client, query)


@Client.on_callback_query(filters.regex("^set_new_channel$"))
async def ask_for_channel(client: Client, query: CallbackQuery):
    if not _is_admin(query.from_user):
        return
    WAITING_FOR_CHANNEL[query.from_user.id] = True
    buttons = [[InlineKeyboardButton(to_small_caps("✘ ᴄᴀɴᴄᴇʟ"), callback_data="manage_channel")]]
    text = (
        "<blockquote>👇 <b>ʜᴏᴡ ᴛᴏ ʟɪɴᴋ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ:</b>\n\n"
        "𝟷. ɢᴏ ᴛᴏ ʏᴏᴜʀ ᴛᴀʀɢᴇᴛ ᴄʜᴀɴɴᴇʟ.\n"
        "𝟸. ғᴏʀᴡᴀʀᴅ ᴀɴʏ ᴍᴇssᴀɢᴇ ғʀᴏᴍ ᴛʜᴀᴛ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴍᴇ ʀɪɢʜᴛ ɴᴏᴡ.\n"
        "(ᴏʀ, ʏᴏᴜ ᴄᴀɴ ᴊᴜsᴛ ᴛʏᴘᴇ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ɪᴅ ɪғ ʏᴏᴜ ᴋɴᴏᴡ ɪᴛ, ᴇ.ɢ., -𝟷𝟶𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿)</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        pass


@Client.on_message(filters.private)
async def capture_admin_input(client: Client, message: Message):
    if not _is_admin(message.from_user):
        message.continue_propagation()
        return

    user_id = message.from_user.id

    if WAITING_FOR_PRODUCT_LINK.get(user_id):
        match = URL_REGEX.search(message.text or "")
        if not match:
            await message.reply_text(
                "<blockquote>✘ ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ <code>http://</code> ᴏʀ <code>https://</code> ᴘʀᴏᴅᴜᴄᴛ ʟɪɴᴋ.</blockquote>"
            )
            return

        product_url = match.group(0).rstrip(".,!?)")
        PENDING_PRODUCT_LINK[user_id] = product_url
        WAITING_FOR_PRODUCT_LINK.pop(user_id, None)

        await message.reply_text(
            f"<blockquote>🗂️ <b>sᴇʟᴇᴄᴛ ᴀ ᴄᴀᴛᴇɢᴏʀʏ:</b>\n\n"
            f"<b>ʟɪɴᴋ:</b> <code>{product_url}</code></blockquote>",
            reply_markup=_product_category_keyboard(),
        )
        return

    if not WAITING_FOR_CHANNEL.get(user_id):
        message.continue_propagation()
        return

    channel_id = None
    if message.forward_from_chat and message.forward_from_chat.type.name == "CHANNEL":
        channel_id = message.forward_from_chat.id
    else:
        try:
            channel_id = int(message.text)
        except (ValueError, TypeError):
            return await message.reply_text("<blockquote>✘ ɪɴᴠᴀʟɪᴅ ɪɴᴘᴜᴛ. ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴀ ᴍᴇssᴀɢᴇ ᴏʀ sᴇɴᴅ ᴀ -𝟷𝟶𝟶 ɪᴅ.</blockquote>")

    try:
        chat = await client.get_chat(channel_id)
        channel_name = chat.title
    except Exception:
        channel_name = f"Unknown Channel ({channel_id})"

    await add_target_channel(channel_id, channel_name)
    WAITING_FOR_CHANNEL.pop(user_id, None)

    sc_channel_name = to_small_caps(channel_name)
    buttons = [[InlineKeyboardButton(to_small_caps("🔙 ʙᴀᴄᴋ ᴛᴏ ᴄʜᴀɴɴᴇʟ ᴍᴇɴᴜ"), callback_data="manage_channel")]]
    text = (
        f"<blockquote>✔ <b>ᴄʜᴀɴɴᴇʟ sᴜᴄᴄᴇssғᴜʟʟʏ ᴀᴅᴅᴇᴅ!</b>\n\n"
        f"<b>ɴᴀᴍᴇ:</b> {sc_channel_name}\n"
        f"<b>ɪᴅ:</b> <code>{channel_id}</code>\n\n"
        f"ᴍᴀᴋᴇ sᴜʀᴇ ᴛᴏ ᴀᴅᴅ ᴛʜᴇ ʙᴏᴛ ᴀs ᴀɴ <b>ᴀᴅᴍɪɴ</b> ɪɴ ᴛʜɪs ᴄʜᴀɴɴᴇʟ sᴏ ɪᴛ ᴄᴀɴ ᴘᴏsᴛ.</blockquote>"
    )
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
