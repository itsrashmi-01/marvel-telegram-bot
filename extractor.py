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

def extract_file_info(filename: str, file_size: int) -> dict:
    """Automatically extracts rich metadata from a release filename."""
    if not filename:
        return {
            "quality": "Unknown", 
            "release": "Unknown", 
            "audio": "Unknown", 
            "size": get_readable_size(file_size)
        }
        
    # Replace dots and underscores with spaces for significantly better Regex parsing
    name_lower = filename.lower().replace(".", " ").replace("_", " ")
    
    # --- 1. EXTRACT ALL DATA ---
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

    res_val = None
    res_match = re.search(r'\b(480p|720p|1080p|2160p|4k)\b', name_lower)
    if res_match: 
        res = res_match.group(1)
        res_val = "2160p" if res == "4k" else res

    source_val = None
    if re.search(r'\b(web-?dl)\b', name_lower): source_val = "WEB-DL"
    elif re.search(r'\b(web-?rip)\b', name_lower): source_val = "WEBRip"
    elif re.search(r'\b(blu-?ray|brip|brrip|bd-?rip)\b', name_lower): source_val = "BluRay"
    elif re.search(r'\b(hd-?rip)\b', name_lower): source_val = "HDRip"
    elif re.search(r'\b(dvd-?rip)\b', name_lower): source_val = "DVDRip"
    elif re.search(r'\b(hq-?hdts)\b', name_lower): source_val = "HQ HDTS"
    elif re.search(r'\b(hd-?ts|telesync)\b', name_lower): source_val = "HDTS"
    elif re.search(r'\b(hd-?tc)\b', name_lower): source_val = "HDTC"
    elif re.search(r'\b(hd-?cam)\b', name_lower): source_val = "HDCAM"
    elif re.search(r'\b(cam-?rip|cam)\b', name_lower): source_val = "CAM"
    elif re.search(r'\b(hall[\s]?print)\b', name_lower): source_val = "Hall Print"
    elif re.search(r'\b(pre-?dvd)\b', name_lower): source_val = "PreDVD"

    codec_val = None
    if re.search(r'\b(hevc|x265|h265)\b', name_lower): codec_val = "HEVC"
    elif re.search(r'\b(avc|x264|h264)\b', name_lower): codec_val = "AVC"
    elif re.search(r'\b(av1)\b', name_lower): codec_val = "AV1"
    
    audio_codec_val = None
    audio_match = re.search(r'(?<![a-z0-9])(aac5\.1|aac2\.0|aac|ddp5\.1|dd\+|dd|atmos|truehd|dts-hd|dts)(?![a-z0-9])', name_lower)
    if audio_match:
        audio_map = {
            "aac": "AAC", "aac2.0": "AAC 2.0", "aac5.1": "AAC 5.1",
            "dd": "DD", "dd+": "DD+", "ddp5.1": "DDP 5.1",
            "atmos": "Dolby Atmos", "truehd": "TrueHD",
            "dts": "DTS", "dts-hd": "DTS-HD"
        }
        audio_codec_val = audio_map.get(audio_match.group(1), audio_match.group(1).upper())

    bit_depth_val = "10-bit" if re.search(r'\b(10-?bit)\b', name_lower) else "8-bit"

    sub_val = None
    if re.search(r'\b(hc-?e-?sub)\b', name_lower): sub_val = "HC-ESub"
    elif re.search(r'\b(multi-?sub)\b', name_lower): sub_val = "MultiSub"
    elif re.search(r'\b(e-?sub|eng?-?sub)\b', name_lower): sub_val = "ESub"
    elif re.search(r'\b(hc|hardcoded)\b', name_lower): sub_val = "HC"

    ext_val = None
    ext_match = filename.split(".")[-1] if "." in filename else ""
    if ext_match and len(ext_match) <= 4: 
        ext_val = ext_match.upper()

    # --- 2. BUILD DICTIONARY ---
    info = { "Size_Bytes": file_size } 
    
    # Keeping your advanced extractions available
    if langs: info["Languages"] = " + ".join(langs)
    if res_val: info["Resolution"] = res_val
    if source_val: info["Source"] = source_val
    if codec_val: info["Codec"] = codec_val
    if bit_depth_val: info["Bit Depth"] = bit_depth_val
    if audio_codec_val: info["Audio_Codec"] = audio_codec_val
    if sub_val: info["Subtitles"] = sub_val
    if ext_val: info["Extension"] = ext_val

    # CRITICAL: These 4 specific keys are required by upload.py to build the database correctly
    info["quality"] = res_val if res_val else "480p"
    info["release"] = source_val if source_val else "HD"
    info["audio"] = " + ".join(langs) if langs else "English"
    info["size"] = get_readable_size(file_size)

    return info
