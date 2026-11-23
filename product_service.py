import json
import logging
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import aiohttp
from config import Config
from database import save_product_item, get_products_grouped_by_category

logger = logging.getLogger(__name__)

CATEGORIES = [
    "Collectibles",
    "Apparel",
    "Accessories",
    "Gadgets",
    "Home & Decor",
]

FALLBACK_IMAGE = (
    "https://ik.imagekit.io/itsrashmi/"
    "Marvel%20Sticker/Avengers.webp"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}

PRODUCT_IMG_REGEX = re.compile(
    r"https?://(?:rukminim[12]\.flixcart\.com|m\.media-amazon\.com|assets\.myntassets\.com)/[^\"'\s<>\\]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\"'\s<>\\]*)?",
    re.IGNORECASE,
)


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas = {}
        self.json_ld = []
        self.title_parts = []
        self.text_parts = []
        self.candidate_images = []
        self._in_title = False
        self._in_ld = False
        self._skip = False

    def _record_image(self, raw_src: str):
        s = (raw_src or "").strip()
        if not s or s.startswith("data:"):
            return
        low = s.lower()
        if any(skip in low for skip in ("sprite", "logo", "icon", "svg", "1x1", "placeholder", "spinner")):
            return
        if s not in self.candidate_images:
            self.candidate_images.append(s)

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        amap = {k.lower(): v for k, v in attrs if v is not None}

        if t == "meta":
            k = (amap.get("property") or amap.get("name") or amap.get("itemprop") or "").strip().lower()
            c = (amap.get("content") or "").strip()
            if k and c and k not in self.metas:
                self.metas[k] = c
        elif t == "title":
            self._in_title = True
        elif t == "img":
            for attr in ("src", "data-src", "data-original", "srcset", "data-srcset"):
                val = amap.get(attr)
                if val:
                    first_part = val.split(",")[0].strip().split(" ")[0].strip()
                    self._record_image(first_part)
        elif t == "script":
            if "ld+json" in (amap.get("type") or "").lower():
                self._in_ld = True
                self.json_ld.append("")
            self._skip = True
        elif t in ("style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "title":
            self._in_title = False
        elif t == "script":
            self._in_ld = False
            self._skip = False
        elif t in ("style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._in_ld and self.json_ld:
            self.json_ld[-1] += data
        elif not self._skip:
            s = data.strip()
            if s:
                self.text_parts.append(s)


def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "flipkart" in host or "fkrt" in host:
        return "Flipkart"
    if "myntra" in host:
        return "Myntra"
    if "amazon" in host or "amzn" in host:
        return "Amazon"
    return "Store"


def _clean_price(val) -> str:
    if not val:
        return ""
    m = re.search(r"[\d,]+(?:\.\d{1,2})?", unescape(str(val)))
    if not m:
        return ""
    num = m.group(0).replace(",", "")
    return f"₹{num}" if num else ""


def _parse_json_ld(blocks: list) -> dict:
    out = {"title": "", "image": "", "price": ""}
    for raw in blocks:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list):
                stack.extend(cur)
            elif isinstance(cur, dict):
                if isinstance(cur.get("@graph"), list):
                    stack.extend(cur["@graph"])
                types = cur.get("@type", [])
                if isinstance(types, str):
                    types = [types]
                if any(str(x).lower() in ("product", "productgroup") for x in types):
                    if not out["title"] and cur.get("name"):
                        out["title"] = unescape(str(cur["name"])).strip()
                    if not out["image"] and cur.get("image"):
                        img = cur["image"]
                        if isinstance(img, list) and img:
                            first = img[0]
                            out["image"] = first if isinstance(first, str) else first.get("url", "")
                        elif isinstance(img, str):
                            out["image"] = img
                        elif isinstance(img, dict):
                            out["image"] = img.get("url", "")
                    if not out["price"] and cur.get("offers"):
                        offers = cur["offers"]
                        offer = offers[0] if isinstance(offers, list) and offers else offers
                        if isinstance(offer, dict):
                            out["price"] = _clean_price(offer.get("price") or offer.get("lowPrice"))
    return out


def _title_from_url_slug(url: str) -> str:
    path = urlparse(url).path or ""
    parts = [p for p in path.split("/") if p and p not in ("p", "itm")]
    if not parts:
        return ""
    slug = re.sub(r"[-_]+", " ", parts[0]).strip()
    return slug.title() if len(slug) > 3 else ""


def _pick_best_product_image(
    parser: _MetaParser,
    html: str,
    final_url: str,
    ld_image: str,
    meta_image: str,
) -> str:
    pid_match = re.search(r"[?&]pid=([A-Za-z0-9]+)", final_url)
    pid = pid_match.group(1).lower() if pid_match else ""

    raw_candidates = []
    for raw in (ld_image, meta_image):
        if raw:
            raw_candidates.append(raw.strip())

    raw_candidates.extend(parser.candidate_images)

    unescaped_html = unescape(html).replace("\\/", "/")
    for match in PRODUCT_IMG_REGEX.findall(unescaped_html):
        if match not in raw_candidates:
            raw_candidates.append(match)

    scored = []
    for raw_img in raw_candidates:
        resolved = urljoin(final_url, raw_img)
        parsed = urlparse(resolved)
        if parsed.scheme not in ("http", "https"):
            continue

        low = resolved.lower()
        score = 0
        if "/image/" in low:
            score += 60
        if "rukminim2.flixcart.com/image/" in low:
            score += 15
        if "rukminim" in low or "myntassets" in low or "media-amazon" in low:
            score += 20
        if pid and pid in low:
            score += 40
        if "/promos/" in low or "promo" in low or "banner" in low:
            score -= 120

        scored.append((score, resolved))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored[0][0] > -50:
            return scored[0][1]

    return FALLBACK_IMAGE


async def fetch_product_details(url: str) -> dict:
    clean_url = url.strip()
    final_url = clean_url
    html = ""

    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
            async with session.get(clean_url, allow_redirects=True) as resp:
                final_url = str(resp.url)
                html = await resp.text(errors="replace")
    except Exception as exc:
        logger.warning("HTTP fetch error for %s: %s", clean_url, exc)

    parser = _MetaParser()
    parser.feed(html)
    parser.close()

    ld = _parse_json_ld(parser.json_ld)
    metas = parser.metas

    raw_html_title = "".join(parser.title_parts).strip()
    if "online shopping india" in raw_html_title.lower() and "buy mobiles" in raw_html_title.lower():
        raw_html_title = ""

    title = (
        ld["title"]
        or metas.get("og:title")
        or metas.get("twitter:title")
        or raw_html_title
        or _title_from_url_slug(final_url)
        or "Product Deal"
    )

    meta_img = metas.get("og:image") or metas.get("twitter:image") or ""
    image = _pick_best_product_image(parser, html, final_url, ld["image"], meta_img)

    price = (
        ld["price"]
        or _clean_price(metas.get("product:price:amount") or metas.get("og:price:amount") or "")
    )
    if not price:
        m = re.search(
            r"(?:₹|Rs\.?)\s*([\d,]+(?:\.\d{1,2})?)(?!\s*/\s*(?:mo|month|yr|day))",
            " ".join(parser.text_parts),
            re.IGNORECASE,
        )
        if m:
            price = _clean_price(m.group(1))

    return {
        "title": unescape(title).strip(),
        "image": image,
        "price": price,
        "platform": detect_platform(final_url),
        "source_url": final_url,
    }


async def convert_earnkaro_link(deal_url: str) -> str:
    token = (getattr(Config, "EARNKARO_TOKEN", "") or "").strip()
    api_url = (
        getattr(Config, "EARNKARO_CONVERTER_URL", "")
        or "https://ekaro-api.affiliaters.in/api/converter/public"
    ).strip()

    if not deal_url:
        print("[EARNKARO] Empty deal_url, skipping conversion", flush=True)
        return deal_url
    if not token:
        print("[EARNKARO] EARNKARO_TOKEN is missing/empty; returning original link", flush=True)
        return deal_url

    payload = {
        "deal": deal_url,
        "convert_option": "convert_only",
    }

    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as resp:
                raw_text = await resp.text()
                print(f"[EARNKARO] HTTP {resp.status} -> {raw_text}", flush=True)
                logger.info("EarnKaro HTTP %s -> %s", resp.status, raw_text)

                try:
                    data = json.loads(raw_text)
                except Exception:
                    data = None

                if resp.status == 200 and isinstance(data, dict):
                    profit = data.get("data")
                    if isinstance(profit, dict):
                        profit = (
                            profit.get("url")
                            or profit.get("link")
                            or profit.get("deal")
                            or profit.get("short_url")
                            or profit.get("profit_link")
                        )
                    if not profit:
                        profit = data.get("url") or data.get("link") or data.get("short_url")

                    if isinstance(profit, str) and profit.strip().startswith(("http://", "https://")):
                        converted = profit.strip()
                        print(f"[EARNKARO] Converted link -> {converted}", flush=True)
                        return converted
    except Exception as exc:
        print(f"[EARNKARO] Exception: {exc}", flush=True)
        logger.warning("EarnKaro conversion error: %s", exc)

    return deal_url


class ProductRepository:
    async def save_product(self, raw_link: str, category: str) -> dict:
        details = await fetch_product_details(raw_link)
        profit_url = await convert_earnkaro_link(details["source_url"])
        return await save_product_item({
            "title": details["title"],
            "image": details["image"],
            "price": details["price"],
            "platform": details["platform"],
            "category": category,
            "source_url": details["source_url"],
            "url": profit_url,
        })

    async def get_grouped_products(self) -> dict:
        return await get_products_grouped_by_category()
