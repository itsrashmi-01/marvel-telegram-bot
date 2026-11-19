from hydrogram import Client, filters
from hydrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from plugins.start import UPLOAD_STATE
from database import save_movie_files, get_movie_by_order
from extractor import extract_file_info
from template import to_small_caps, format_movie_post


def _has_file_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ʏᴇs, ɪ ʜᴀᴠᴇ ғɪʟᴇ", callback_data="has_file_yes"),
            InlineKeyboardButton("⏭️ ɴᴏ, sᴋɪᴘ ғɪʟᴇ", callback_data="has_file_no")
        ],
        [InlineKeyboardButton("✘ ᴄᴀɴᴄᴇʟ ᴜᴘʟᴏᴀᴅ", callback_data="cancel_upload")]
    ])


def _has_link_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ʏᴇs, ᴀᴅᴅ ʟɪɴᴋs", callback_data="has_link_yes"),
            InlineKeyboardButton("⏭️ ɴᴏ, sᴋɪᴘ ʟɪɴᴋs", callback_data="has_link_no")
        ],
        [InlineKeyboardButton("✘ ᴄᴀɴᴄᴇʟ ᴜᴘʟᴏᴀᴅ", callback_data="cancel_upload")]
    ])


def _clean_files_for_save(raw_files: list) -> list:
    """Keeps only non-empty fields so missing file_id or mediafire_link are not saved."""
    cleaned = []
    for f in raw_files:
        entry = {}
        if f.get("quality"):
            entry["quality"] = f["quality"]
        if f.get("file_id"):
            entry["file_id"] = f["file_id"]
        if f.get("msg_id") is not None:
            entry["msg_id"] = f["msg_id"]
        if f.get("mediafire_link"):
            entry["mediafire_link"] = f["mediafire_link"]
        if f.get("file_size") and f["file_size"] != "Unknown Size":
            entry["file_size"] = f["file_size"]

        if entry.get("file_id") or entry.get("mediafire_link"):
            cleaned.append(entry)
    return cleaned


async def _prompt_link_step(client: Client, chat_id: int, user_state: dict, edit_msg=None):
    user_state["status"] = "ask_has_link"
    sc_title = to_small_caps(f"{user_state['title']} {user_state.get('release', '')}".strip())
    file_count = len([f for f in user_state.get("files", []) if f.get("file_id")])

    text = (
        f"<blockquote>🔗 <b>{sc_title}</b>\n\n"
        f"📁 ғɪʟᴇs ᴀᴅᴅᴇᴅ: <b>{file_count}</b>\n"
        f"ᴅᴏ ʏᴏᴜ ʜᴀᴠᴇ <b>ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋs</b> ᴛᴏ ᴀᴅᴅ?</blockquote>"
    )
    if edit_msg:
        await edit_msg.edit_text(text, reply_markup=_has_link_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=_has_link_keyboard())


async def _show_final_preview(client: Client, chat_id: int, user_state: dict):
    order = user_state["watch_order"]
    db_movie = await get_movie_by_order(order) or {"title": user_state["title"], "watch_order": order}

    clean_files = _clean_files_for_save(user_state.get("files", []))
    user_state["files"] = clean_files

    db_movie["files"] = clean_files
    if user_state.get("audio"):
        db_movie["audio"] = user_state["audio"]
    if user_state.get("release"):
        db_movie["release"] = user_state["release"]

    caption = format_movie_post(db_movie)
    poster_url = db_movie.get("images", {}).get("poster_url", "")

    buttons = [
        [InlineKeyboardButton(to_small_caps("💾 sᴀᴠᴇ ᴛᴏ ᴅᴀᴛᴀʙᴀsᴇ"), callback_data=f"save_db_{order}")],
        [InlineKeyboardButton("✘ ᴄᴀɴᴄᴇʟ", callback_data="cancel_upload")]
    ]

    if poster_url:
        await client.send_photo(chat_id, photo=poster_url, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await client.send_message(chat_id, text=caption, reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex("^has_file_(yes|no)$"))
async def handle_has_file_choice(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return
    user_state = UPLOAD_STATE.get(query.from_user.id)
    if not user_state:
        return await query.answer(to_small_caps("sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ."), show_alert=True)

    choice = query.matches[0].group(1)
    user_state.setdefault("files", [])

    if choice == "yes":
        user_state["status"] = "receiving"
        sc_title = to_small_caps(user_state["title"])
        await query.message.edit_text(
            f"<blockquote>📥 <b>{sc_title}</b>\n\n"
            f"ᴘʟᴇᴀsᴇ sᴇɴᴅ ʏᴏᴜʀ <b>ᴠɪᴅᴇᴏ / ᴅᴏᴄᴜᴍᴇɴᴛ ғɪʟᴇ(s)</b> ɴᴏᴡ.</blockquote>"
        )
    else:
        user_state["has_file"] = False
        await _prompt_link_step(client, query.message.chat.id, user_state, edit_msg=query.message)

    await query.answer()


@Client.on_message((filters.document | filters.video) & filters.private)
async def handle_media(client: Client, message: Message):
    if message.from_user.id != Config.ADMIN_ID:
        return
    user_state = UPLOAD_STATE.get(message.from_user.id)
    if not user_state:
        await message.reply_text("<blockquote>⚠️ ᴘʟᴇᴀsᴇ sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴠɪᴇ ғʀᴏᴍ ᴛʜᴇ /start ᴍᴇɴᴜ ғɪʀsᴛ.</blockquote>")
        return

    if user_state.get("status") != "receiving":
        await message.reply_text("<blockquote>⚠️ ɴᴏᴛ ᴄᴜʀʀᴇɴᴛʟʏ ᴄᴏʟʟᴇᴄᴛɪɴɢ ғɪʟᴇs. ᴘʟᴇᴀsᴇ ғᴏʟʟᴏᴡ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴘʀᴏᴍᴘᴛ.</blockquote>")
        return

    user_state.setdefault("files", [])
    doc = message.document or message.video
    raw_file_name = getattr(doc, "file_name", "") or ""
    caption_text = message.caption or ""
    combined_meta_text = f"{raw_file_name} {caption_text}".strip()
    file_size = getattr(doc, "file_size", 0) or 0
    vid_height = getattr(doc, "height", 0) or 0
    vid_width = getattr(doc, "width", 0) or 0

    info = extract_file_info(combined_meta_text, file_size, vid_height, vid_width)

    if "audio" not in user_state:
        user_state["audio"] = info["audio"]
        user_state["release"] = info["release"]
    elif "Hindi" in info["audio"] and "Hindi" not in user_state["audio"]:
        user_state["audio"] = "English + Hindi"

    dump_msg = await message.forward(Config.DUMP_CHANNEL_ID)
    secure_file_id = dump_msg.document.file_id if dump_msg.document else dump_msg.video.file_id

    base_q = info["quality"]
    final_q = base_q
    existing_qualities = {f["quality"] for f in user_state["files"]}
    counter = 2
    while final_q in existing_qualities:
        final_q = f"{base_q} #{counter}"
        counter += 1

    user_state["files"].append({
        "quality": final_q,
        "file_id": secure_file_id,
        "msg_id": dump_msg.id,
        "file_size": info["size"]
    })

    sc_title = to_small_caps(f"{user_state['title']} {user_state.get('release', '')}".strip())
    count = len(user_state["files"])
    qualities_str = to_small_caps(", ".join(f"{f['quality']} ({f['file_size']})" for f in user_state["files"]))

    summary_text = (
        f"<blockquote>📥 <b>{sc_title}</b>\n\n"
        f"✅ {count} ғɪʟᴇ(s) ʀᴇᴄᴇɪᴠᴇᴅ & ғᴏʀᴡᴀʀᴅᴇᴅ.\n"
        f"📺 <b>ǫᴜᴀʟɪᴛɪᴇs:</b> {qualities_str}\n\n"
        f"sᴇɴᴅ ᴍᴏʀᴇ ғɪʟᴇs, ᴏʀ ᴄʟɪᴄᴋ ᴄᴏɴғɪʀᴍ.</blockquote>"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✔ ᴄᴏɴғɪʀᴍ ғɪʟᴇs", callback_data="confirm_files")],
        [InlineKeyboardButton("✘ ᴄᴀɴᴄᴇʟ ᴜᴘʟᴏᴀᴅ", callback_data="cancel_upload")]
    ])

    if "status_msg_id" in user_state:
        try:
            await client.edit_message_text(
                chat_id=message.chat.id,
                message_id=user_state["status_msg_id"],
                text=summary_text,
                reply_markup=markup
            )
            return
        except Exception:
            pass

    status_msg = await message.reply_text(summary_text, reply_markup=markup)
    user_state["status_msg_id"] = status_msg.id


@Client.on_callback_query(filters.regex("^confirm_files$"))
async def confirm_files_step(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return
    user_state = UPLOAD_STATE.get(query.from_user.id)
    if not user_state:
        return await query.answer(to_small_caps("sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ."), show_alert=True)

    await _prompt_link_step(client, query.message.chat.id, user_state, edit_msg=query.message)
    await query.answer()


@Client.on_callback_query(filters.regex("^has_link_(yes|no)$"))
async def handle_has_link_choice(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return
    user_state = UPLOAD_STATE.get(query.from_user.id)
    if not user_state:
        return await query.answer(to_small_caps("sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ."), show_alert=True)

    choice = query.matches[0].group(1)

    if choice == "no":
        user_state["status"] = "preview_ready"
        await query.message.edit_text("<blockquote>⏭️ <b>ʟɪɴᴋs sᴋɪᴘᴘᴇᴅ.</b> ᴘʀᴇᴘᴀʀɪɴɢ ᴘʀᴇᴠɪᴇᴡ...</blockquote>")
        await _show_final_preview(client, query.message.chat.id, user_state)
        await query.answer()
        return

    # Choice == "yes"
    if user_state.get("files"):
        user_state["status"] = "waiting_for_mediafire"
        user_state["mf_index"] = 0
        first_file = user_state["files"][0]
        await query.message.edit_text(
            f"<blockquote>🔗 <b>ᴍᴇᴅɪᴀғɪʀᴇ ʟɪɴᴋ ʀᴇǫᴜɪʀᴇᴅ</b>\n\n"
            f"sᴇɴᴅ ᴛʜᴇ ʟɪɴᴋ ғᴏʀ 👉 <b>{to_small_caps(first_file['quality'])}</b> ({to_small_caps(first_file.get('file_size', ''))})</blockquote>"
        )
    else:
        # No files were uploaded, so ask for quality + link in one message (e.g. "1080p https://...")
        user_state["status"] = "waiting_standalone_links"
        await query.message.edit_text(
            "<blockquote>🔗 <b>ᴀᴅᴅ ʟɪɴᴋs ᴡɪᴛʜᴏᴜᴛ ғɪʟᴇs</b>\n\n"
            "sᴇɴᴅ ᴇᴀᴄʜ ʟɪɴᴋ ᴀs: <code>1080p https://mediafire.com/...</code>\n"
            "ᴛʏᴘᴇ <code>/done</code> ᴡʜᴇɴ ғɪɴɪsʜᴇᴅ.</blockquote>"
        )

    await query.answer()


@Client.on_message(filters.text & filters.private)
async def handle_text_links(client: Client, message: Message):
    if message.from_user.id != Config.ADMIN_ID:
        message.continue_propagation()
        return

    user_state = UPLOAD_STATE.get(message.from_user.id)
    status = user_state.get("status") if user_state else None

    if status == "waiting_for_mediafire":
        idx = user_state["mf_index"]
        raw_text = message.text.strip()
        if raw_text.lower() not in ("skip", "-"):
            user_state["files"][idx]["mediafire_link"] = raw_text
        user_state["mf_index"] += 1

        if user_state["mf_index"] < len(user_state["files"]):
            next_file = user_state["files"][user_state["mf_index"]]
            await message.reply_text(
                f"<blockquote>✅ ᴜᴘᴅᴀᴛᴇᴅ.\n\n"
                f"sᴇɴᴅ ᴛʜᴇ ʟɪɴᴋ ғᴏʀ 👉 <b>{to_small_caps(next_file['quality'])}</b> ({to_small_caps(next_file.get('file_size', ''))})\n"
                f"<i>(sᴇɴᴅ <code>skip</code> ᴛᴏ ʟᴇᴀᴠᴇ ᴡɪᴛʜᴏᴜᴛ ʟɪɴᴋ)</i></blockquote>"
            )
        else:
            user_state["status"] = "preview_ready"
            await _show_final_preview(client, message.chat.id, user_state)
        return

    if status == "waiting_standalone_links":
        text = message.text.strip()
        if text.lower() == "/done":
            user_state["status"] = "preview_ready"
            await _show_final_preview(client, message.chat.id, user_state)
            return

        parts = text.split(maxsplit=1)
        if len(parts) == 2 and parts[1].startswith(("http://", "https://")):
            q_label, url_val = parts[0].strip(), parts[1].strip()
            user_state.setdefault("files", []).append({
                "quality": q_label,
                "mediafire_link": url_val
            })
            await message.reply_text(
                f"<blockquote>✅ ᴀᴅᴅᴇᴅ <b>{to_small_caps(q_label)}</b>.\n"
                f"sᴇɴᴅ ᴀɴᴏᴛʜᴇʀ ᴏʀ ᴛʏᴘᴇ <code>/done</code>.</blockquote>"
            )
        else:
            await message.reply_text(
                "<blockquote>⚠️ ғᴏʀᴍᴀᴛ: <code>1080p https://...</code> ᴏʀ ᴛʏᴘᴇ <code>/done</code>.</blockquote>"
            )
        return

    message.continue_propagation()


@Client.on_callback_query(filters.regex(r"^save_db_(\d+)$"))
async def save_to_database(client: Client, query: CallbackQuery):
    if query.from_user.id != Config.ADMIN_ID:
        return
    user_state = UPLOAD_STATE.get(query.from_user.id)
    if not user_state:
        return await query.answer(to_small_caps("sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ."), show_alert=True)

    clean_files = _clean_files_for_save(user_state.get("files", []))
    await save_movie_files(
        user_state["watch_order"],
        clean_files,
        user_state.get("audio"),
        user_state.get("release")
    )

    await query.message.edit_reply_markup(reply_markup=None)
    sc_title = to_small_caps(f"{user_state['title']} {user_state.get('release', '')}".strip())
    await client.send_message(
        query.message.chat.id,
        f"<blockquote>✅ <b>sᴀᴠᴇᴅ ᴛᴏ ᴅᴀᴛᴀʙᴀsᴇ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n🎬 {sc_title}</blockquote>"
    )
    del UPLOAD_STATE[query.from_user.id]
    await query.answer()


@Client.on_callback_query(filters.regex("^cancel_upload$"))
async def cancel_upload(client: Client, query: CallbackQuery):
    if query.from_user.id == Config.ADMIN_ID and query.from_user.id in UPLOAD_STATE:
        del UPLOAD_STATE[query.from_user.id]
        if query.message.photo:
            await query.message.delete()
            await client.send_message(query.message.chat.id, "<blockquote>✘ ᴜᴘʟᴏᴀᴅ ᴄᴀɴᴄᴇʟʟᴇᴅ. sᴇssɪᴏɴ ᴄʟᴇᴀʀᴇᴅ.</blockquote>")
        else:
            await query.message.edit_text("<blockquote>✘ ᴜᴘʟᴏᴀᴅ ᴄᴀɴᴄᴇʟʟᴇᴅ. sᴇssɪᴏɴ ᴄʟᴇᴀʀᴇᴅ.</blockquote>")
    await query.answer()
