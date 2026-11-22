import asyncio
import ipaddress
import json
import logging
import re
import socket

from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import aiohttp

from config import Config
from database import (
    save_product_item,
    get_products_grouped_by_category,
)

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

MAX_HTML_SIZE = 3 * 1024 * 1024
MAX_REDIRECTS = 5

ALLOWED_DOMAINS = (
    "flipkart.com",
    "myntra.com",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}


# --------------------------------------------------
# URL VALIDATION
# --------------------------------------------------

def _validate_hostname(host: str):
    if not host:
        raise ValueError("Invalid URL hostname")

    host = host.lower().rstrip(".")

    if not any(
        host == domain or host.endswith("." + domain)
        for domain in ALLOWED_DOMAINS
    ):
        raise ValueError("Unsupported shopping platform")

    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("Private IP addresses are not allowed")
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise

    return host


async def _validate_url(url: str):
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS URLs are allowed")

    host = _validate_hostname(parsed.hostname or "")

    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not allowed")

    try:
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid URL port")

    if port not in (None, 80, 443):
        raise ValueError("Unsupported URL port")

    # Resolve the hostname and reject private/internal addresses.
    try:
        results = await asyncio.get_running_loop().getaddrinfo(
            host,
            port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise ValueError("Unable to resolve product URL") from exc

    for result in results:
        address = result[4][0].split("%")[0]
        ip = ipaddress.ip_address(address)

        if not ip.is_global:
            raise ValueError("Unsafe destination address")

    return url


# --------------------------------------------------
# HTML PARSER
# --------------------------------------------------

class _PageMetaParser(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.metas = {}
        self.itemprops = {}
        self.json_ld_blocks = []
        self.title_chunks = []
        self.text_chunks = []

        self._in_title = False
        self._in_json_ld = False
        self._skip_text = False

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        attrs = {
            key.lower(): value
            for key, value in attrs
            if value is not None
        }

        if tag == "meta":

            key = (
                attrs.get("property")
                or attrs.get("name")
                or attrs.get("itemprop")
                or ""
            ).strip().lower()

            content = attrs.get("content", "").strip()

            if key and content:
                self.metas.setdefault(key, content)

        elif tag == "title":
            self._in_title = True

        elif tag == "script":

            script_type = attrs.get("type", "").lower()

            if "ld+json" in script_type:
                self._in_json_ld = True
                self.json_ld_blocks.append("")

            self._skip_text = True

        elif tag in ("style", "noscript"):
            self._skip_text = True

        # Extract microdata.
        itemprop = attrs.get("itemprop")

        if itemprop:

            value = (
                attrs.get("content")
                or attrs.get("value")
                or attrs.get("href")
                or attrs.get("src")
            )

            if value:
                self.itemprops.setdefault(
                    itemprop.lower(), value.strip()
                )

    def handle_endtag(self, tag):

        tag = tag.lower()

        if tag == "title":
            self._in_title = False

        elif tag == "script":
            self._in_json_ld = False
            self._skip_text = False

        elif tag in ("style", "noscript"):
            self._skip_text = False

    def handle_data(self, data):

        if self._in_title:
            self.title_chunks.append(data)

        if self._in_json_ld and self.json_ld_blocks:
            self.json_ld_blocks[-1] += data

        elif not self._skip_text:

            value = data.strip()

            if value:
                self.text_chunks.append(value)


# --------------------------------------------------
# PLATFORM DETECTION
# --------------------------------------------------

def detect_platform(url: str) -> str:

    host = (urlparse(url).hostname or "").lower()

    if host == "flipkart.com" or host.endswith(".flipkart.com"):
        return "Flipkart"

    if host == "myntra.com" or host.endswith(".myntra.com"):
        return "Myntra"

    return "Store"


# --------------------------------------------------
# PRICE HELPERS
# --------------------------------------------------

def _parse_decimal(value):

    if value is None:
        return None

    value = unescape(str(value)).strip()

    value = re.sub(
        r"[^\d.]",
        "",
        value.replace(",", "")
    )

    try:
        number = Decimal(value)

        if not number.is_finite() or number <= 0:
            return None

        return number

    except (InvalidOperation, ValueError):
        return None


def _format_price(value):

    number = _parse_decimal(value)

    if number is None:
        return ""

    formatted = format(number, "f")

    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")

    return f"₹{formatted}"


def _clean_price(value):
    return _format_price(value)


def _calculate_discount(price, mrp):

    selling = _parse_decimal(price)
    original = _parse_decimal(mrp)

    if not selling or not original:
        return ""

    if original <= selling:
        return ""

    discount = (
        (original - selling) / original
    ) * Decimal("100")

    return f"{discount.quantize(Decimal('1'))}%"


# --------------------------------------------------
# JSON-LD EXTRACTION
# --------------------------------------------------

def _walk_json(data):

    if isinstance(data, dict):

        yield data

        for value in data.values():
            yield from _walk_json(value)

    elif isinstance(data, list):

        for value in data:
            yield from _walk_json(value)


def _is_product(obj):

    types = obj.get("@type", [])

    if isinstance(types, str):
        types = [types]

    return any(
        str(value).lower() in ("product", "productgroup")
        for value in types
    )


def _extract_image(value):

    if isinstance(value, str):
        return value

    if isinstance(value, list):

        for item in value:
            result = _extract_image(item)

            if result:
                return result

    elif isinstance(value, dict):

        return (
            value.get("url")
            or value.get("contentUrl")
            or value.get("@id")
            or ""
        )

    return ""


def _extract_offer_prices(offers):

    if isinstance(offers, dict):
        offers = [offers]

    if not isinstance(offers, list):
        return "", ""

    selling_prices = []
    original_prices = []

    for offer in offers:

        if not isinstance(offer, dict):
            continue

        price = (
            offer.get("price")
            or offer.get("lowPrice")
            or offer.get("minPrice")
        )

        if price:
            selling_prices.append(price)

        specs = offer.get("priceSpecification", [])

        if isinstance(specs, dict):
            specs = [specs]

        for spec in specs:

            if not isinstance(spec, dict):
                continue

            spec_type = str(
                spec.get("priceType", "")
            ).lower()

            spec_name = str(
                spec.get("name", "")
            ).lower()

            if (
                "listprice" in spec_type
                or "list price" in spec_name
                or "original" in spec_name
                or "regular" in spec_name
            ):
                original_prices.append(spec.get("price"))

        high_price = offer.get("highPrice")

        if high_price and price:
            original_prices.append(high_price)

    selling = (
        _format_price(selling_prices[0])
        if selling_prices else ""
    )

    original = (
        _format_price(original_prices[0])
        if original_prices else ""
    )

    return selling, original


def _parse_json_ld_product(blocks):

    result = {
        "title": "",
        "image": "",
        "price": "",
        "mrp": "",
    }

    for raw in blocks:

        try:
            data = json.loads(raw)

        except (ValueError, TypeError):
            continue

        for obj in _walk_json(data):

            if not _is_product(obj):
                continue

            if not result["title"] and obj.get("name"):
                result["title"] = unescape(
                    str(obj["name"])
                ).strip()

            if not result["image"]:
                result["image"] = _extract_image(
                    obj.get("image")
                )

            selling, original = _extract_offer_prices(
                obj.get("offers")
            )

            if not result["price"] and selling:
                result["price"] = selling

            if not result["mrp"] and original:
                result["mrp"] = original

            if not result["price"]:

                specs = obj.get("offers", {})

                if isinstance(specs, dict):
                    result["price"] = _format_price(
                        specs.get("price")
                    )

    return result


# --------------------------------------------------
# METADATA EXTRACTION
# --------------------------------------------------

def _first_value(data, keys):

    for key in keys:

        value = data.get(key)

        if value:
            return value

    return ""


def _extract_metadata(metas, itemprops):

    price = _first_value(
        metas,
        [
            "product:price:amount",
            "og:price:amount",
            "product:sale_price:amount",
            "twitter:data1",
        ],
    )

    mrp = _first_value(
        metas,
        [
            "product:original_price:amount",
            "product:price:original",
            "product:list_price:amount",
            "og:price:original",
        ],
    )

    price = price or itemprops.get("price", "")

    mrp = mrp or itemprops.get(
        "highprice",
        ""
    )

    return _clean_price(price), _clean_price(mrp)


# --------------------------------------------------
# PRODUCT FETCHER
# --------------------------------------------------

async def _download_html(session, url):

    current_url = url

    for _ in range(MAX_REDIRECTS + 1):

        await _validate_url(current_url)

        async with session.get(
            current_url,
            allow_redirects=False,
        ) as response:

            if response.status in (301, 302, 303, 307, 308):

                location = response.headers.get("Location")

                if not location:
                    raise ValueError("Invalid redirect")

                current_url = urljoin(
                    current_url,
                    location
                )

                continue

            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if "html" not in content_type:
                raise ValueError("URL did not return HTML")

            length = response.content_length

            if length and length > MAX_HTML_SIZE:
                raise ValueError("Product page is too large")

            chunks = []
            size = 0

            async for chunk in response.content.iter_chunked(16384):

                size += len(chunk)

                if size > MAX_HTML_SIZE:
                    raise ValueError("Product page exceeded size limit")

                chunks.append(chunk)

            html = b"".join(chunks).decode(
                response.charset or "utf-8",
                errors="replace"
            )

            return html, str(response.url)

    raise ValueError("Too many redirects")


async def fetch_product_details(url: str) -> dict:

    empty_result = {
        "title": "Product",
        "image": FALLBACK_IMAGE,
        "price": "",
        "mrp": "",
        "discount": "",
        "platform": "Store",
        "source_url": url,
    }

    try:

        timeout = aiohttp.ClientTimeout(
            total=20,
            connect=8,
            sock_read=12,
        )

        connector = aiohttp.TCPConnector(
            limit=10,
            ttl_dns_cache=0,
        )

        async with aiohttp.ClientSession(
            headers=HEADERS,
            timeout=timeout,
            connector=connector,
            trust_env=False,
        ) as session:

            html, final_url = await _download_html(
                session,
                url.strip()
            )

        parser = _PageMetaParser()
        parser.feed(html)
        parser.close()

        metas = parser.metas
        itemprops = parser.itemprops

        ld = _parse_json_ld_product(
            parser.json_ld_blocks
        )

        # Title fallback.
        title = (
            ld["title"]
            or metas.get("og:title")
            or metas.get("twitter:title")
            or metas.get("title")
            or "".join(parser.title_chunks).strip()
            or "Product"
        )

        # Image fallback.
        raw_image = (
            ld["image"]
            or metas.get("og:image")
            or metas.get("og:image:url")
            or metas.get("twitter:image")
            or metas.get("twitter:image:src")
            or ""
        )

        image = FALLBACK_IMAGE

        if raw_image:

            candidate = urljoin(
                final_url,
                raw_image
            )

            parsed_image = urlparse(candidate)

            if parsed_image.scheme in ("http", "https"):
                image = candidate

        # Price fallback.
        meta_price, meta_mrp = _extract_metadata(
            metas,
            itemprops
        )

        price = ld["price"] or meta_price

        mrp = ld["mrp"] or meta_mrp

        # Last-resort visible price extraction.
        if not price:

            text_content = " ".join(
                parser.text_chunks
            )

            match = re.search(
                r"(?:₹|Rs\.?\s*)\s*"
                r"([\d,]+(?:\.\d{1,2})?)",
                text_content,
                re.IGNORECASE,
            )

            if match:
                price = _clean_price(match.group(1))

        discount = _calculate_discount(
            price,
            mrp
        )

        return {
            "title": unescape(str(title)).strip(),
            "image": image,
            "price": price,
            "mrp": mrp,
            "discount": discount,
            "platform": detect_platform(final_url),
            "source_url": final_url,
        }

    except Exception as exc:

        logger.exception(
            "Product extraction failed: %s",
            exc
        )

        return {
            **empty_result,
            "error": str(exc),
        }


# --------------------------------------------------
# EARNKARO LINK CONVERTER
# --------------------------------------------------

async def convert_earnkaro_link(deal_url: str) -> str:

    token = getattr(
        Config,
        "EARNKARO_TOKEN",
        ""
    )

    converter_url = getattr(
        Config,
        "EARNKARO_CONVERTER_URL",
        "https://ekaro-api.affiliaters.in/api/converter/public",
    )

    if not deal_url or not token:
        return deal_url

    try:

        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.post(
                converter_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "deal": deal_url
                },
            ) as response:

                if response.status != 200:

                    logger.warning(
                        "EarnKaro API returned HTTP %s",
                        response.status
                    )

                    return deal_url

                data = await response.json(
                    content_type=None
                )

                if not isinstance(data, dict):
                    return deal_url

                converted = data.get("data")

                # Handle common API response structures.
                if isinstance(converted, dict):

                    converted = (
                        converted.get("url")
                        or converted.get("link")
                        or converted.get("deal")
                    )

                if (
                    isinstance(converted, str)
                    and converted.startswith(("https://", "http://"))
                ):
                    return converted

                logger.warning(
                    "Unexpected EarnKaro response format"
                )

    except Exception:

        logger.exception(
            "EarnKaro link conversion failed"
        )

    return deal_url


# --------------------------------------------------
# PRODUCT REPOSITORY
# --------------------------------------------------

class ProductRepository:

    async def save_product(
        self,
        raw_link: str,
        category: str,
    ) -> dict:

        if category not in CATEGORIES:
            raise ValueError("Invalid product category")

        details = await fetch_product_details(
            raw_link
        )

        if details.get("error"):
            raise ValueError(
                f"Unable to fetch product: {details['error']}"
            )

        profit_url = await convert_earnkaro_link(
            details["source_url"]
        )

        product_data = {
            "title": details["title"],
            "image": details["image"],
            "price": details["price"],
            "mrp": details["mrp"],
            "discount": details["discount"],
            "platform": details["platform"],
            "category": category,
            "source_url": details["source_url"],
            "url": profit_url,
        }

        return await save_product_item(
            product_data
        )

    async def get_grouped_products(self) -> dict:

        return await get_products_grouped_by_category()
