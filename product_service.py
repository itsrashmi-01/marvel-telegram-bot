import re
import json
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import aiohttp
from config import Config
from database import save_product_item, get_products_grouped_by_category

CATEGORIES = [
    "Collectibles",
    "Apparel",
    "Accessories",
    "Gadgets",
    "Home & Decor",
]

FALLBACK_IMAGE = "https://ik.imagekit.io/itsrashmi/Marvel%20Sticker/Avengers.webp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}


class _PageMetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas = {}
        self.json_ld_blocks = []
        self.title_chunks = []
        self.text_chunks = []
        self._in_title = False
        self._in_json_ld = False
        self._skip_text = False

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        attr_map = {k.lower(): v for k, v in attrs if v is not None}

        if t == "meta":
            key = (attr_map.get("property") or attr_map.get("name") or "").strip().lower()
            content = (attr_map.get("content") or "").strip()
            if key and content and key not in self.metas:
                self.metas[key] = content
        elif t == "title":
            self._in_title = True
        elif t == "script":
            stype = (attr_map.get("type") or "").strip().lower()
            if "ld+json" in stype:
                self._in_json_ld = True
                self.json_ld_blocks.append("")
            self._skip_text = True
        elif t in ("style", "noscript"):
            self._skip_text = True

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "title":
            self._in_title = False
        elif t == "script":
            self._in_json_ld = False
            self._skip_text = False
        elif t in ("style", "noscript"):
            self._skip_text = False

    def handle_data(self, data):
        if self._in_title:
            self.title_chunks.append(data)
        if self._in_json_ld:
            self.json_ld_blocks[-1] = self.json_ld_blocks[-1] + data
        elif not self._skip_text:
            stripped = data.strip()
            if stripped:
                self.text_chunks.append(stripped)


def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "flipkart" in host or "dl.flipkart" in host:
        return "Flipkart"
    if "amazon" in host or "amzn" in host:
        return "Amazon"
    if "myntra" in host:
        return "Myntra"
    if "ajio" in host:
        return "Ajio"
    return "Store"


def _clean_price(raw_val) -> str:
    if raw_val is None:
        return ""
    s = unescape(str(raw_val)).strip()
    if not s:
        return ""
    if re.fullmatch(r"\d+(?:\.\d{1,2})?", s):
        return f"₹{s}"
    if "₹" not in s and re.search(r"\d", s):
        m = re.search(r"[\d,]+(?:\.\d{1,2})?", s)
        return f"₹{m.group(0)}" if m else s
    return s


def _parse_json_ld_product(blocks: list) -> dict:
    title = ""
    image = ""
    price = ""

    for raw in blocks:
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            candidates = graph if isinstance(graph, list) else [node]
            for obj in candidates:
                if not isinstance(obj, dict):
                    continue
                if str(obj.get("@type", "")).lower() == "product":
                    if not title and obj.get("name"):
                        title = unescape(str(obj["name"])).strip()
                    img = obj.get("image")
                    if not image and img:
                        if isinstance(img, list) and img:
                            first = img[0]
                            image = first if isinstance(first, str) else first.get("url", "")
                        elif isinstance(img, str):
                            image = img
                        elif isinstance(img, dict):
                            image = img.get("url", "")
                    offers = obj.get("offers")
                    if not price and offers:
                        offer_obj = offers[0] if isinstance(offers, list) and offers else offers
                        if isinstance(offer_obj, dict):
                            price = _clean_price(offer_obj.get("price") or offer_obj.get("lowPrice"))

    return {"title": title, "image": image, "price": price}


async def fetch_product_details(url: str) -> dict:
    final_url = url.strip()
    html = ""

    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
        async with session.get(final_url, allow_redirects=True) as resp:
            final_url = str(resp.url)
            html = await resp.text(errors="replace")

    parser = _PageMetaParser()
    parser.feed(html)

    ld = _parse_json_ld_product(parser.json_ld_blocks)
    metas = parser.metas

    og_title = metas.get("og:title") or metas.get("twitter:title") or ""
    og_image = metas.get("og:image") or metas.get("twitter:image") or ""
    og_price = metas.get("product:price:amount") or metas.get("og:price:amount") or ""
    html_title = "".join(parser.title_chunks).strip()

    title = (
        ld["title"]
        or og_title.strip()
        or html_title
        or "Marvel Product"
    )

    raw_img = ld["image"] or og_image.strip()
    if raw_img:
        try:
            image = urljoin(final_url, raw_img)
        except Exception:
            image = FALLBACK_IMAGE
    else:
        image = FALLBACK_IMAGE

    price = ld["price"] or _clean_price(og_price)
    if not price:
        full_text = " ".join(parser.text_chunks)
        price_match = re.search(r"₹\s*[\d,]+(?:\.\d{1,2})?", full_text)
        if price_match:
            price = _clean_price(price_match.group(0))

    return {
        "title": title,
        "image": image,
        "price": price,
        "platform": detect_platform(final_url),
        "source_url": final_url,
    }


async def convert_earnkaro_link(deal_url: str) -> str:
    token = getattr(Config, "EARNKARO_TOKEN", "")
    converter_url = getattr(
        Config,
        "EARNKARO_CONVERTER_URL",
        "https://ekaro-api.affiliaters.in/api/converter/public",
    )
    if not token or not deal_url:
        return deal_url
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                converter_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"deal": deal_url},
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 200 and isinstance(data, dict) and data.get("data"):
                    return data["data"]
    except Exception:
        pass
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
