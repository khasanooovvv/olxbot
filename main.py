import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from olx_monitor import collect_ads, format_ad, load_seen, matches_price, save_seen
from telegram_sender import send_to_channel


load_dotenv()
data_dir = Path(os.getenv("DATA_DIR", "data"))
seen_path = data_dir / "seen_ads.json"
monitor_since = datetime.fromisoformat(os.getenv("MONITOR_SINCE", "2026-09-30T18:08:00+05:00"))
local_tz = timezone(timedelta(hours=5))
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
            match = re.search(r"Сегодня\s+в\s+(\d{1,2}):(\d{2})", ad["text"], re.IGNORECASE)
            if not match:
                continue
            posted = datetime.now(local_tz).replace(hour=int(match[1]), minute=int(match[2]), second=0, microsecond=0)
            if posted < monitor_since:
                continue
            send_to_channel(format_ad(ad))
            seen.add(ad["url"])
            save_seen(seen_path, seen)


with sync_playwright() as p:
    session_dir.mkdir(parents=True, exist_ok=True)
    browser = p.chromium.launch_persistent_context(
        str(session_dir), headless=True, args=["--no-sandbox"], timezone_id="Asia/Tashkent", locale="ru-RU"
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    print(f"Monitoring since {monitor_since.isoformat()}, timezone={page.evaluate('Intl.DateTimeFormat().resolvedOptions().timeZone')}", flush=True)
    while True:
        try:
            run_once(page)
        except Exception as exc:
            print(f"Check failed: {exc}", flush=True)
        time.sleep(int(os.getenv("CHECK_INTERVAL_SECONDS", "180")))
