import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
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
    base = urlsplit(os.environ["OLX_SEARCH_URL"])
    query = dict(parse_qsl(base.query))
    query["search[order]"] = "created_at:desc"
    urls = []
    for number in range(1, 4):
        query["page"] = str(number)
        urls.append(urlunsplit(base._replace(query=urlencode(query))))

    for url in urls:
        if not url:
            continue
        try:
            ads = collect_ads(page, url)
        except Exception as exc:
            print(f"PAGE_FAILED page={urls.index(url)+1} error={type(exc).__name__}", flush=True)
            continue
        for ad in ads:
            if ad["url"] in seen or not matches_price(ad["text"]):
                continue
            match = re.search(r"Сегодня\s+в\s+(\d{1,2}):(\d{2})", ad["text"], re.IGNORECASE)
            if not match:
                continue
            posted = datetime.now(local_tz).replace(hour=int(match[1]), minute=int(match[2]), second=0, microsecond=0)
            if posted < monitor_since:
                continue
            print(f"FOUND at={datetime.now(local_tz).isoformat()} posted={posted.isoformat()} url={ad['url']}", flush=True)
            try:
                send_to_channel(format_ad(ad))
            except Exception as exc:
                print(f"SEND_FAILED at={datetime.now(local_tz).isoformat()} url={ad['url']} error={type(exc).__name__}", flush=True)
                continue
            seen.add(ad["url"])
            save_seen(seen_path, seen)
            print(f"SENT at={datetime.now(local_tz).isoformat()} url={ad['url']}", flush=True)


with sync_playwright() as p:
    session_dir.mkdir(parents=True, exist_ok=True)
    browser = p.chromium.launch_persistent_context(
        str(session_dir), headless=True, args=["--no-sandbox"], timezone_id="Asia/Tashkent", locale="ru-RU"
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    print(f"Monitoring since {monitor_since.isoformat()}, timezone={page.evaluate('Intl.DateTimeFormat().resolvedOptions().timeZone')}", flush=True)
    while True:
        started = time.monotonic()
        try:
            run_once(page)
        except Exception as exc:
            print(f"Check failed: {type(exc).__name__}", flush=True)
        elapsed = time.monotonic() - started
        delay = max(0, int(os.getenv("CHECK_INTERVAL_SECONDS", "30")) - elapsed)
        print(f"CYCLE seconds={elapsed:.1f} wait={delay:.1f}", flush=True)
        time.sleep(delay)
