import json
import html
import os
import re
import time
from pathlib import Path
from playwright.sync_api import Page


def _number(value: str) -> float | None:
    cleaned = re.sub(r"[^0-9.,]", "", value).replace(" ", "")
    if not cleaned:
        return None
    try:
        # OLX usually formats Uzbek sums as 1 500 000 or 1.500.000.
        if cleaned.count(".") > 1 or ("." in cleaned and len(cleaned.rsplit(".", 1)[-1]) == 3):
            cleaned = cleaned.replace(".", "")
        if "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", "")
        return float(cleaned)
    except ValueError:
        return None


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")))


def save_seen(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def collect_ads(page: Page, search_url: str | None = None) -> list[dict]:
    started = time.perf_counter()
    try:
        page.goto(search_url or os.environ["OLX_SEARCH_URL"], wait_until="commit", timeout=0)
    except Exception:
        # Continue with whatever HTML has loaded instead of blocking the cycle.
        pass
    page.wait_for_timeout(1200)
    cards = page.locator("a[href*='/d/obyavlenie/']")
    ads = []
    seen_urls = set()
    for i in range(min(cards.count(), 100)):
        card = cards.nth(i)
        link = card.get_attribute("href")
        if not link:
            continue
        url = link if link.startswith("http") else "https://www.olx.uz" + link
        url = url.split("?")[0].rstrip()
        if url in seen_urls:
            continue
        seen_urls.add(url)
        image_url = ""
        image = card.locator("img").first
        if not image.count():
            parent_for_image = card
            for _ in range(4):
                parent_for_image = parent_for_image.locator("xpath=..")
                image = parent_for_image.locator("img").first
                if image.count():
                    break
        if image.count():
            image_url = image.get_attribute("src") or image.get_attribute("data-src") or ""
        # The price is often on the listing card, not inside the title link.
        text = " ".join(card.inner_text().split())
        parent = card
        for _ in range(4):
            parent = parent.locator("xpath=..")
            candidate = " ".join(parent.inner_text().split())
            if len(candidate) > len(text):
                text = candidate
        ads.append({"url": url, "text": text, "image_url": image_url})
    print(f"OLX tekshirildi: {time.perf_counter() - started:.1f} soniya, {len(ads)} ta e'lon", flush=True)
    return ads


def matches_price(text: str) -> bool:
    lower = text.lower().replace("сўм", "so'm").replace("сум", "so'm")
    euro_values = re.findall(r"([0-9][0-9\s.,]*)\s*(?:€|eur|евро)", lower)
    for raw in euro_values:
        value = _number(raw)
        if value is not None and float(os.getenv("EUR_MIN", "100")) <= value <= float(os.getenv("EUR_MAX", "200")):
            return True

    uzs_values = re.findall(r"([0-9][0-9\s.,]*)\s*(?:so['’`]?m|uzs)", lower)
    for raw in uzs_values:
        value = _number(raw)
        if value is not None and float(os.getenv("UZS_MIN", "1000000")) <= value <= float(os.getenv("UZS_MAX", "2500000")):
            return True
    return False


def format_ad(ad: dict) -> str:
    """Format listing-card data using the requested labels."""
    text = " ".join(ad.get("text", "").split())
    price_match = re.search(
        r"([0-9][0-9\s.,]*)\s*(so['’`]?m|сум|сўм|uzs|€|eur|евро)",
        text,
        re.IGNORECASE,
    )
    price = " ".join(price_match.group(0).split()) if price_match else ""
    time_match = re.search(r"(?:Сегодня|Вчера)\s+в\s+\d{1,2}:\d{2}|\d{1,2}\s+\w+\s+\d{4}\s+г\.?", text, re.IGNORECASE)
    posted_time = time_match.group(0) if time_match else ""
    before_price = text[:price_match.start()].strip() if price_match else text
    brand = before_price.split(" - ")[0].strip() or before_price
    esc = html.escape
    return (
        '<table bordered compact><tr><th colspan="2">📱 OLX e\'lon</th></tr>'
        f'<tr><td>🏷 info</td><td>{esc(brand)}</td></tr>'
        f'<tr><td>💰 narxi</td><td>{esc(price)}</td></tr>'
        f'<tr><td>🕒 vaqt</td><td>{esc(posted_time)}</td></tr>'
        f'<tr><td>🔗 link</td><td><a href="{esc(ad["url"])}">OLX e\'lon</a></td></tr>'
        '</table>'
    )
