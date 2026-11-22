import os
import re
import json
from html import unescape
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from motor.motor_asyncio import AsyncIOMotorClient

CATEGORIES = [
    "Collectibles",
    "Apparel",
    "Accessories",
    "Gadgets",
    "Home & Decor",
]

EARNKARO_TOKEN = os.getenv("EARNKARO_TOKEN", "")
EARNKARO_CONVERTER_URL = os.getenv(
    "EARNKARO_CONVERTER_URL",
    "https://ekaro-api.affiliaters.in/api/converter/public",
)
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "jarvis_marvel")

FALLBACK_IMAGE = "https://ik.imagekit.io/itsrashmi/Marvel%20Sticker/Avengers.webp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}


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


def _parse_json_ld_product(soup: BeautifulSoup) -> dict:
    title = ""
    image = ""
    price = ""

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
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
                            image = img[0] if isinstance(img[0], str) else img[0].get("url", "")
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
    title = ""
    image = ""
    price = ""

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=12.0) as client:
        resp = await client.get(final_url)
        final_url = str(resp.url)
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    ld = _parse_json_ld_product(soup)

    og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
    og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
    og_price = soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount")

    title = (
        ld["title"]
        or (unescape(og_title["content"]).strip() if og_title and og_title.get("content") else "")
        or (unescape(soup.title.string).strip() if soup.title and soup.title.string else "")
        or "Marvel Product"
    )

    raw_img = (
        ld["image"]
        or (unescape(og_image["content"]).strip() if og_image and og_image.get("content") else "")
    )
    if raw_img:
        try:
            image = urljoin(final_url, raw_img)
        except Exception:
            image = FALLBACK_IMAGE
    else:
        image = FALLBACK_IMAGE

    price = ld["price"] or _clean_price(og_price["content"] if og_price and og_price.get("content") else "")
    if not price:
        price_match = re.search(r"₹\s*[\d,]+(?:\.\d{1,2})?", soup.get_text(" ", strip=True))
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
    if not EARNKARO_TOKEN or not deal_url:
        return deal_url
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                EARNKARO_CONVERTER_URL,
                headers={
                    "Authorization": f"Bearer {EARNKARO_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"deal": deal_url},
            )
            data = resp.json()
            if resp.status_code == 200 and isinstance(data, dict) and data.get("data"):
                return data["data"]
    except Exception:
        pass
    return deal_url


class ProductRepository:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.col = self.db["products"]

    async def save_product(self, raw_link: str, category: str) -> dict:
        details = await fetch_product_details(raw_link)
        profit_url = await convert_earnkaro_link(details["source_url"])

        doc = {
            "title": details["title"],
            "image": details["image"],
            "price": details["price"],
            "platform": details["platform"],
            "category": category,
            "source_url": details["source_url"],
            "url": profit_url,
            "created_at": datetime.now(timezone.utc),
        }
        result = await self.col.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        doc.pop("_id", None)
        doc["created_at"] = doc["created_at"].isoformat()
        return doc

    async def get_grouped_products(self) -> dict:
        cursor = self.col.find({}).sort("created_at", -1)
        items = []
        async for row in cursor:
            items.append({
                "id": str(row["_id"]),
                "title": row.get("title", "Marvel Product"),
                "image": row.get("image") or FALLBACK_IMAGE,
                "price": row.get("price", ""),
                "platform": row.get("platform", "Store"),
                "category": row.get("category", "General"),
                "url": row.get("url") or row.get("source_url") or "#",
            })

        grouped = {}
        for item in items:
            cat = item["category"]
            grouped.setdefault(cat, []).append(item)

        return {
            "categories": [
                {"name": cat, "count": len(list_items), "items": list_items}
                for cat, list_items in grouped.items()
            ],
            "products": items,
        }
