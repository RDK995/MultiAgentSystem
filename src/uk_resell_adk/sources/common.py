from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import time
from html import unescape
from urllib.parse import urljoin
from urllib.request import Request, urlopen


USER_AGENT = "uk-resell-adk/0.2 (+research assistant)"
LOGGER = logging.getLogger(__name__)
DEBUG_ENABLED = False
DEBUG_DIR = Path("debug/sources")

_CURRENCY_TO_GBP: dict[str, float] = {
    "GBP": 1.0,
    "EUR": 0.86,
    "USD": 0.79,
    "JPY": 0.0053,
}


class SourceBlockedError(RuntimeError):
    pass


def configure_debug(enabled: bool, output_dir: str | Path) -> None:
    global DEBUG_ENABLED, DEBUG_DIR
    DEBUG_ENABLED = enabled
    DEBUG_DIR = Path(output_dir)
    if DEBUG_ENABLED:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def _write_debug_snapshot(source_key: str, label: str, content: str) -> None:
    if not DEBUG_ENABLED:
        return
    ts = int(time.time() * 1000)
    safe_source = source_key or "unknown"
    safe_label = re.sub(r"[^a-zA-Z0-9._-]+", "_", label)[:80]
    out_dir = DEBUG_DIR / safe_source
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{ts}_{safe_label}.html").write_text(content, encoding="utf-8")


def _looks_like_block_page(content: str) -> bool:
    low = content.lower()
    indicators = (
        "robotcheck",
        "/challenge",
        "cf-chl",
        "captcha",
        "attention required",
        "access denied",
        "verify you are human",
    )
    return any(x in low for x in indicators)


def fetch_page(
    url: str,
    timeout_seconds: float = 10,
    retries: int = 2,
    source_key: str = "",
    debug_label: str = "page",
) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                content = response.read().decode("utf-8", errors="ignore")
                _write_debug_snapshot(source_key, f"{debug_label}_attempt{attempt}", content)
                if _looks_like_block_page(content):
                    raise SourceBlockedError(f"Blocked by anti-bot challenge at {url}")
                return content
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(0.3 * (2 ** attempt))
    if last_error is not None:
        raise last_error
    raise RuntimeError("unreachable")


def normalize_text(value: str) -> str:
    return " ".join(unescape(value).replace("\xa0", " ").split())


def extract_number(raw: str) -> float | None:
    match = re.search(r"(\d[\d,]*\.?\d*)", raw)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def currency_to_gbp(amount: float, currency: str | None) -> float:
    if not currency:
        return amount
    rate = _CURRENCY_TO_GBP.get(currency.upper())
    return amount if rate is None else amount * rate


def estimate_shipping_to_uk_gbp(source_price_gbp: float) -> float:
    return round(max(12.0, min(35.0, 12.0 + (source_price_gbp * 0.08))), 2)


def extract_products_from_json_ld(content: str) -> list[dict[str, str | float]]:
    scripts = re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    products: list[dict[str, str | float]] = []

    def walk(obj: object) -> None:
        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return
        if not isinstance(obj, dict):
            return

        t = obj.get("@type")
        is_product = t == "Product" or (isinstance(t, list) and "Product" in t)
        if is_product:
            name = obj.get("name")
            url = obj.get("url")
            offers = obj.get("offers", {})
            price = None
            currency = None
            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency")
            if isinstance(name, str) and isinstance(url, str):
                amount = extract_number(str(price)) if price is not None else None
                if amount is not None:
                    products.append(
                        {
                            "title": normalize_text(name),
                            "url": url,
                            "source_price_gbp": round(currency_to_gbp(amount, str(currency) if currency else None), 2),
                        }
                    )
        for value in obj.values():
            walk(value)

    for script in scripts:
        try:
            payload = json.loads(script.strip())
        except Exception:  # noqa: BLE001
            continue
        walk(payload)
    return products


def extract_products_from_html(content: str, base_url: str) -> list[dict[str, str | float]]:
    candidates: list[dict[str, str | float]] = []
    for match in re.finditer(
        r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        href, inner = match.groups()
        title = normalize_text(re.sub(r"<[^>]+>", " ", inner))
        if len(title) < 8:
            continue
        url = urljoin(base_url, unescape(href))
        window = content[match.end() : match.end() + 450]
        price_match = re.search(r"(£|€|\$|¥|&yen;|JPY|USD|EUR)\s*([\d,]+(?:\.\d{1,2})?)", window, flags=re.IGNORECASE)
        if not price_match:
            continue
        symbol = price_match.group(1).upper()
        currency = {"£": "GBP", "€": "EUR", "$": "USD", "¥": "JPY", "&YEN;": "JPY"}.get(symbol, symbol)
        amount = extract_number(price_match.group(2))
        if amount is None:
            continue
        price_gbp = round(currency_to_gbp(amount, currency), 2)
        if not (5 <= price_gbp <= 3000):
            continue
        candidates.append({"title": title, "url": url, "source_price_gbp": price_gbp})
        if len(candidates) >= 30:
            break
    return candidates


def extract_sitemap_locs(content: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<]+)\s*</loc>", content, flags=re.IGNORECASE)


def fetch_sitemap_product_urls(
    home_url: str,
    url_hints: tuple[str, ...] = (),
    url_excludes: tuple[str, ...] = (),
    limit: int = 200,
    timeout_seconds: float = 10,
    retries: int = 2,
    source_key: str = "",
) -> list[str]:
    root = home_url.rstrip("/")
    queue = [f"{root}/sitemap.xml"]
    seen_sitemaps: set[str] = set()
    urls: list[str] = []
    seen_urls: set[str] = set()
    depth = 0

    while queue and len(urls) < limit and depth < 3:
        depth += 1
        current_batch = list(queue)
        queue.clear()
        for sm in current_batch:
            if sm in seen_sitemaps:
                continue
            seen_sitemaps.add(sm)
            try:
                xml = fetch_page(
                    sm,
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                    source_key=source_key,
                    debug_label="sitemap_index",
                )
            except Exception:  # noqa: BLE001
                continue
            for loc in extract_sitemap_locs(xml):
                if loc.endswith(".xml"):
                    if loc not in seen_sitemaps:
                        queue.append(loc)
                    continue
                if url_hints and not any(h.lower() in loc.lower() for h in url_hints):
                    continue
                if url_excludes and any(h.lower() in loc.lower() for h in url_excludes):
                    continue
                if loc in seen_urls:
                    continue
                seen_urls.add(loc)
                urls.append(loc)
                if len(urls) >= limit:
                    break
    return urls


def extract_first_product_from_page(page_url: str, content: str) -> dict[str, str | float] | None:
    rows = extract_products_from_json_ld(content)
    if rows:
        row = rows[0]
        return {
            "title": str(row["title"]),
            "url": str(row.get("url") or page_url),
            "source_price_gbp": float(row["source_price_gbp"]),
        }
    rows = extract_products_from_html(content, page_url)
    if rows:
        row = rows[0]
        return {
            "title": str(row["title"]),
            "url": str(row.get("url") or page_url),
            "source_price_gbp": float(row["source_price_gbp"]),
        }
    return None
