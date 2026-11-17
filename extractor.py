import re

# ==========================================
# FILE FORMATTER & METADATA EXTRACTOR
# ==========================================
def get_readable_size(size_in_bytes: int) -> str:
    """Converts bytes to a human-readable format (e.g., 1.5 GB)."""
    if not size_in_bytes:
        return "Unknown Size"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def infer_resolution_from_meta(height: int, width: int, file_size: int) -> str:
    """Fallback: Determines 480p / 720p / 1080p / 2160p from video dimensions or file size."""
    max_dim = max(height or 0, width or 0)
    min_dim = min(height or 0, width or 0)
    
    if max_dim >= 3200 or min_dim >= 1800:
        return "2160p"
    elif max_dim >= 1800 or min_dim >= 950:
        return "1080p"
    elif max_dim >= 1200 or min_dim >= 650:
        return "720p"
    elif max_dim > 0:
        return "480p"

    mb = (file_size or 0) / (1024 * 1024)
    if mb > 3200:
        return "2160p"
    elif mb > 1350:
        return "1080p"
    elif mb > 650:
        return "720p"
    return "480p"

def extract_file_info(filename: str, file_size: int, height: int = 0, width: int = 0) -> dict:
    """Automatically extracts rich metadata from a release filename/caption and video attributes."""
    clean_input = filename or ""
    name_lower = re.sub(r'[._\[\]\(\)\-\+]+', ' ', clean_input.lower())
    
    # --- 1. EXTRACT LANGUAGES ---
    langs = []
    if re.search(r'\b(hin|hindi)\b', name_lower): langs.append("Hindi")
    if re.search(r'\b(eng|english)\b', name_lower): langs.append("English")
    if re.search(r'\b(tam|tamil)\b', name_lower): langs.append("Tamil")
    if re.search(r'\b(tel|telugu)\b', name_lower): langs.append("Telugu")
    if re.search(r'\b(mal|malayalam)\b', name_lower): langs.append("Malayalam")
    if re.search(r'\b(kan|kannada)\b', name_lower): langs.append("Kannada")
    if re.search(r'\b(ben|bengali)\b', name_lower): langs.append("Bengali")
    if re.search(r'\b(mar|marathi)\b', name_lower): langs.append("Marathi")
    if re.search(r'\b(pun|punjabi)\b', name_lower): langs.append("Punjabi")
    if re.search(r'\b(guj|gujarati)\b', name_lower): langs.append("Gujarati")
    if re.search(r'\b(spa|spanish)\b', name_lower): langs.append("Spanish")
    if re.search(r'\b(fre|french)\b', name_lower): langs.append("French")
    if re.search(r'\b(kor|korean)\b', name_lower): langs.append("Korean")
    if re.search(r'\b(jap|japanese)\b', name_lower): langs.append("Japanese")
    if re.search(r'\b(chi|chinese)\b', name_lower): langs.append("Chinese")
    if re.search(r'\b(dual\s*audio)\b', name_lower) and not langs:
        langs = ["Hindi", "English"]

    # --- 2. EXTRACT RESOLUTION ---
    res_val = None
    res_match = re.search(r'(?:^|\s|\b)(480p|540p|720p|1080p|1440p|2160p|4k|uhd)(?:\s|\b|$)', name_lower)
    if res_match:
        res = res_match.group(1)
        res_val = "2160p" if res in ("4k", "uhd") else ("480p" if res == "540p" else res)
    elif re.search(r'1920\s*x\s*\d+', name_lower):
        res_val = "1080p"
    elif re.search(r'1280\s*x\s*\d+', name_lower):
        res_val = "720p"
    elif re.search(r'3840\s*x\s*\d+', name_lower):
        res_val = "2160p"

    if not res_val:
        res_val = infer_resolution_from_meta(height, width, file_size)

    # --- 3. DETECT 10-BIT / HEVC VARIANTS FOR QUALITY LABEL ---
    is_10bit = bool(re.search(r'\b(10\s*bit|10bit|hi10p)\b', name_lower))
    is_hevc = bool(re.search(r'\b(hevc|x265|h265)\b', name_lower))

    quality_label = res_val
    if is_10bit and is_hevc:
        quality_label = f"{res_val} 10bit HEVC"
    elif is_10bit:
        quality_label = f"{res_val} 10bit"
    elif is_hevc:
        quality_label = f"{res_val} HEVC"

    # --- 4. EXTRACT SOURCE ---
    source_val = None
    if re.search(r'\b(web\s*dl)\b', name_lower): source_val = "WEB-DL"
    elif re.search(r'\b(web\s*rip)\b', name_lower): source_val = "WEBRip"
    elif re.search(r'\b(blu\s*ray|brip|brrip|bd\s*rip)\b', name_lower): source_val = "BluRay"
    elif re.search(r'\b(hd\s*rip)\b', name_lower): source_val = "HDRip"
    elif re.search(r'\b(dvd\s*rip)\b', name_lower): source_val = "DVDRip"
    elif re.search(r'\b(hq\s*hdts)\b', name_lower): source_val = "HQ HDTS"
    elif re.search(r'\b(hd\s*ts|telesync)\b', name_lower): source_val = "HDTS"
    elif re.search(r'\b(hd\s*tc)\b', name_lower): source_val = "HDTC"
    elif re.search(r'\b(hd\s*cam)\b', name_lower): source_val = "HDCAM"
    elif re.search(r'\b(cam\s*rip|cam)\b', name_lower): source_val = "CAM"
    elif re.search(r'\b(hall\s*print)\b', name_lower): source_val = "Hall Print"
    elif re.search(r'\b(pre\s*dvd)\b', name_lower): source_val = "PreDVD"

    info = {
        "Size_Bytes": file_size,
        "quality": quality_label,
        "base_resolution": res_val,
        "release": source_val if source_val else "HD",
        "audio": " + ".join(langs) if langs else "English",
        "size": get_readable_size(file_size)
    }
    return info
