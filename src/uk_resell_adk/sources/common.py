from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import re
import time
from html import unescape
from typing import TypeVar
from urllib.parse import urljoin
from urllib.request import Request, urlopen


USER_AGENT = "uk-resell-adk/0.2 (+research assistant)"
LOGGER = logging.getLogger(__name__)
DEBUG_ENABLED = False
DEBUG_DIR = Path("debug/sources")

_DEFAULT_CURRENCY_TO_GBP: dict[str, float] = {
    "GBP": 1.0,
    "EUR": 0.86,
    "USD": 0.79,
    "JPY": 0.0053,
}
_CURRENCY_TO_GBP: dict[str, float] = dict(_DEFAULT_CURRENCY_TO_GBP)
_FX_LAST_REFRESH_TS = 0.0
T = TypeVar("T")


class SourceBlockedError(RuntimeError):
    pass


def _env_truthy(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def refresh_currency_rates(force: bool = False) -> bool:
    """Refresh currency-to-GBP rates from a public FX API.

    Returns True when rates were refreshed in this call.
    """
    global _FX_LAST_REFRESH_TS
    if not _env_truthy("ENABLE_LIVE_FX_RATES", True):
        return False

    now_ts = time.time()
    ttl_raw = os.getenv("FX_REFRESH_SECONDS", "21600").strip()
    try:
        ttl_seconds = max(300, int(ttl_raw))
    except ValueError:
        ttl_seconds = 21600
    if not force and _FX_LAST_REFRESH_TS and (now_ts - _FX_LAST_REFRESH_TS) < ttl_seconds:
        return False

    endpoint = os.getenv("FX_API_URL", "https://api.frankfurter.dev/v1/latest").strip()
    symbols = [k for k in sorted(_DEFAULT_CURRENCY_TO_GBP.keys()) if k != "GBP"]
    query = f"{endpoint}?base=GBP&symbols={','.join(symbols)}"
    request = Request(query, headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("FX refresh failed, keeping fallback currency rates: %s", exc)
        return False

    rates = payload.get("rates", {}) if isinstance(payload, dict) else {}
    if not isinstance(rates, dict):
        return False

    updated: dict[str, float] = {"GBP": 1.0}
    for symbol in symbols:
        raw = rates.get(symbol)
        if raw is None:
            updated[symbol] = _CURRENCY_TO_GBP.get(symbol, _DEFAULT_CURRENCY_TO_GBP[symbol])
            continue
        try:
            as_float = float(raw)
            if as_float <= 0:
                raise ValueError("non-positive FX rate")
            # API returns target-per-GBP; convert to currency-to-GBP.
            updated[symbol] = 1.0 / as_float
        except Exception:  # noqa: BLE001
            updated[symbol] = _CURRENCY_TO_GBP.get(symbol, _DEFAULT_CURRENCY_TO_GBP[symbol])

    _CURRENCY_TO_GBP.update(updated)
    _FX_LAST_REFRESH_TS = now_ts
    return True


def shuffle_for_source(items: Sequence[T], *, source_key: str, purpose: str) -> list[T]:
    shuffled = list(items)
    if len(shuffled) < 2:
        return shuffled
    seed = os.getenv("SOURCE_RANDOM_SEED", "").strip()
    if seed:
        digest = hashlib.sha256(f"{seed}:{source_key}:{purpose}".encode("utf-8")).hexdigest()[:16]
        rng: random.Random = random.Random(int(digest, 16))
    else:
        rng = random.SystemRandom()
    rng.shuffle(shuffled)
    return shuffled


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


def infer_currency_from_price_text(raw_price: str) -> str | None:
    low = raw_price.lower()
    if "$" in raw_price or "usd" in low:
        return "USD"
    if "£" in raw_price or "gbp" in low:
        return "GBP"
    if "€" in raw_price or "eur" in low:
        return "EUR"
    if "¥" in raw_price or "円" in raw_price or "jpy" in low:
        return "JPY"
    return None


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
                price_text = str(price) if price is not None else ""
                amount = extract_number(price_text) if price is not None else None
                if amount is not None:
                    resolved_currency = str(currency) if currency else infer_currency_from_price_text(price_text)
                    products.append(
                        {
                            "title": normalize_text(name),
                            "url": url,
                            "source_price_gbp": round(currency_to_gbp(amount, resolved_currency), 2),
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
        # Some marketplaces place the price before the link or farther away in the card block.
        start = max(0, match.start() - 450)
        end = min(len(content), match.end() + 1400)
        window = content[start:end]
        price_match = re.search(
            r"(£|€|\$|¥|円|&yen;|JPY|USD|EUR)\s*([\d,]+(?:\.\d{1,2})?)|([\d,]+(?:\.\d{1,2})?)\s*(円|JPY|USD|EUR)",
            window,
            flags=re.IGNORECASE,
        )
        if not price_match:
            continue
        if price_match.group(1) and price_match.group(2):
            symbol = price_match.group(1).upper()
            amount_raw = price_match.group(2)
        else:
            symbol = str(price_match.group(4) or "").upper()
            amount_raw = str(price_match.group(3) or "")
        currency = {"£": "GBP", "€": "EUR", "$": "USD", "¥": "JPY", "円": "JPY", "&YEN;": "JPY"}.get(symbol, symbol)
        amount = extract_number(amount_raw)
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
