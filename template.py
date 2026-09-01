from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ==========================================
# SMALL-CAPS MAPPER (Letters & Numbers)
# ==========================================
SMALL_CAPS_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ',
    'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
    'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ',
    'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
    '0': '𝟶', '1': '𝟷', '2': '𝟸', '3': '𝟹', '4': '𝟺', '5': '𝟻', '6': '𝟼',
    '7': '𝟽', '8': '𝟾', '9': '𝟿'
}

def to_small_caps(text: any) -> str:
    """Converts any string or number to aesthetic small-caps font."""
    if text is None:
        return ""
    return "".join(SMALL_CAPS_MAP.get(c.lower(), c) for c in str(text))

def get_ordinal_suffix(n: int) -> str:
    """Returns number with ordinal suffix in small caps (e.g. 1 -> 𝟷sᴛ)."""
    try:
        n_int = int(n)
        if 11 <= (n_int % 100) <= 13:
            suffix = "TH"
        else:
            suffix = {1: "ST", 2: "ND", 3: "RD"}.get(n_int % 10, "TH")
        return to_small_caps(f"{n_int}{suffix}")
    except (ValueError, TypeError):
        return to_small_caps(str(n))


# ==========================================
# REUSABLE POST / PREVIEW TEMPLATE (HTML FIXED)
# ==========================================
POST_TEMPLATE = """\
<blockquote>📁 <b>sᴀɢᴀ:</b> {saga}

▶️ <b>ᴡᴀᴛᴄʜ ᴏʀᴅᴇʀ:</b> {watch_order}

🎬 <b>ᴛɪᴛʟᴇ:</b> {title}

🗓️ <b>ʏᴇᴀʀ:</b> {year}

🏷️ <b>ɢᴇɴʀᴇs:</b> {genres}

🔊 <b>ᴀᴜᴅɪᴏ:</b> {audio}

📦 <b>ǫᴜᴀʟɪᴛʏ:</b> {qualities}

💾 <b>ғɪʟᴇ sɪᴢᴇ:</b> {file_sizes}</blockquote>"""


def format_movie_post(movie: dict, custom_qualities: str = None, custom_file_sizes: str = None) -> str:
    """
    Fills the template dynamically from the movie dictionary without hardcoded defaults.
    Converts all rendered text and numbers into small-caps.
    """
    # 1. Saga & Watch Order
    saga = to_small_caps(movie.get("saga", ""))
    raw_order = movie.get("saga_rank") or movie.get("watch_order", "")
    watch_order = get_ordinal_suffix(raw_order) if raw_order != "" else ""

    # 2. Movie Metadata
    title = to_small_caps(movie.get("title", ""))
    year = to_small_caps(movie.get("release_year", ""))

    genres_data = movie.get("genres", [])
    if isinstance(genres_data, list):
        genres_str = ", ".join(genres_data)
    else:
        genres_str = str(genres_data)
    genres = to_small_caps(genres_str)

    audio = to_small_caps(movie.get("language", ""))

    # 3. Dynamic Qualities and File Sizes Extraction
    files = movie.get("files", [])

    if custom_qualities is not None:
        qualities = to_small_caps(custom_qualities)
    elif files:
        qualities_list = [f.get("quality", "") for f in files if f.get("quality")]
        qualities = to_small_caps(", ".join(qualities_list))
    else:
        qualities = to_small_caps(movie.get("qualities", ""))

    if custom_file_sizes is not None:
        file_sizes = to_small_caps(custom_file_sizes)
    elif files:
        sizes_list = [f.get("file_size", "") for f in files if f.get("file_size")]
        file_sizes = to_small_caps(", ".join(sizes_list))
    else:
        file_sizes = to_small_caps(movie.get("file_sizes", ""))

    # 4. Fill Placeholders
    return POST_TEMPLATE.format(
        saga=saga,
        watch_order=watch_order,
        title=title,
        year=year,
        genres=genres,
        audio=audio,
        qualities=qualities,
        file_sizes=file_sizes
    )


def get_download_button(deep_link_url: str) -> InlineKeyboardMarkup:
    """Returns the styled single download button."""
    btn_text = to_small_caps("📩 Download Movie (All Qualities)")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, url=deep_link_url)]
    ])
