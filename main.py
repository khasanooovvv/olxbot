import os
import time
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from olx_monitor import collect_ads, format_ad, load_seen, matches_price, save_seen
from telegram_sender import send_to_channel


load_dotenv()
data_dir = Path(os.getenv("DATA_DIR", "data"))
seen_path = data_dir / "seen_ads.json"
session_dir = data_dir / "session"


def run_once(page) -> None:
    seen = load_seen(seen_path)
    urls = [os.getenv("OLX_SEARCH_URL", "")]
    euro_url = os.getenv("OLX_SEARCH_URL_EUR", "")
    if euro_url and euro_url not in urls:
        urls.append(euro_url)
    for url in urls:
        if not url:
            continue
        for ad in collect_ads(page, url):
            if ad["url"] in seen or not matches_price(ad["text"]):
                continue
            send_to_channel(format_ad(ad))
            seen.add(ad["url"])
            save_seen(seen_path, seen)


with sync_playwright() as p:
    session_dir.mkdir(parents=True, exist_ok=True)
    browser = p.chromium.launch_persistent_context(
        str(session_dir), headless=True, args=["--no-sandbox"]
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    while True:
        try:
            run_once(page)
        except Exception as exc:
            print(f"Check failed: {exc}", flush=True)
        time.sleep(int(os.getenv("CHECK_INTERVAL_SECONDS", "180")))
