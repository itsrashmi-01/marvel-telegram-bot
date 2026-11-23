import json
import re
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

FALLBACK_IMAGE = (
    "https://ik.imagekit.io/itsrashmi/"
    "Marvel%20Sticker/Avengers.webp"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas = {}
        self.json_ld = []
        self.title_parts = []
        self.text_parts = []
        self._in_title = False
        self._in_ld = False
        self._skip = False

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
    except Exception:
        pass

    parser = _MetaParser()
    parser.feed(html)
    parser.close()

    ld = _parse_json_ld(parser.json_ld)
    metas = parser.metas

    title = (
        ld["title"]
        or metas.get("og:title")
        or metas.get("twitter:title")
        or "".join(parser.title_parts).strip()
        or "Product Deal"
    )

    raw_img = ld["image"] or metas.get("og:image") or metas.get("twitter:image") or ""
    image = urljoin(final_url, raw_img) if raw_img else FALLBACK_IMAGE

    price = (
        ld["price"]
        or _clean_price(metas.get("product:price:amount") or metas.get("og:price:amount") or "")
    )
    if not price:
        m = re.search(r"(?:₹|Rs\.?)\s*([\d,]+(?:\.\d{1,2})?)", " ".join(parser.text_parts), re.IGNORECASE)
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
    token = getattr(Config, "EARNKARO_TOKEN", "")
    api_url = getattr(
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
                api_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"deal": deal_url},
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 200 and isinstance(data, dict):
                    profit = data.get("data")
                    if isinstance(profit, dict):
                        profit = profit.get("url") or profit.get("link") or profit.get("deal")
                    if isinstance(profit, str) and profit.startswith(("http://", "https://")):
                        return profit
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
