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
claimed_path = data_dir / "claimed_ads.json"
checkpoint_path = data_dir / "last_check_at.txt"
local_tz = timezone(timedelta(hours=5))
session_dir = data_dir / "session"


def load_checkpoint() -> datetime:
    if checkpoint_path.exists():
        return datetime.fromisoformat(checkpoint_path.read_text(encoding="utf-8").strip())
    now = datetime.now(local_tz)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(now.isoformat(), encoding="utf-8")
    return now


def save_checkpoint(value: datetime) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(value.isoformat(), encoding="utf-8")


def run_once(page, window_start: datetime) -> bool:
    seen = load_seen(seen_path)
    claimed = load_seen(claimed_path)
    all_pages_ok = True
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
            all_pages_ok = False
            print(f"PAGE_FAILED page={urls.index(url)+1} error={type(exc).__name__}", flush=True)
            continue
        for ad in ads:
            if ad["url"] in seen or ad["url"] in claimed or not matches_price(ad["text"]):
                continue
            match = re.search(r"Сегодня\s+в\s+(\d{1,2}):(\d{2})", ad["text"], re.IGNORECASE)
            if not match:
                continue
            posted = datetime.now(local_tz).replace(hour=int(match[1]), minute=int(match[2]), second=0, microsecond=0)
            if posted < window_start - timedelta(minutes=1):
                print(f"SKIP_OLD posted={posted.isoformat()} window={window_start.isoformat()} url={ad['url']}", flush=True)
                continue
            claimed.add(ad["url"])
            save_seen(claimed_path, claimed)
            print(f"FOUND at={datetime.now(local_tz).isoformat()} posted={posted.isoformat()} url={ad['url']}", flush=True)
            try:
                send_to_channel(format_ad(ad))
            except Exception as exc:
                print(f"SEND_FAILED at={datetime.now(local_tz).isoformat()} url={ad['url']} error={type(exc).__name__}", flush=True)
                continue
            seen.add(ad["url"])
            save_seen(seen_path, seen)
            print(f"SENT at={datetime.now(local_tz).isoformat()} url={ad['url']}", flush=True)
    return all_pages_ok


with sync_playwright() as p:
    session_dir.mkdir(parents=True, exist_ok=True)
    browser = p.chromium.launch_persistent_context(
        str(session_dir), headless=True, args=["--no-sandbox"], timezone_id="Asia/Tashkent", locale="ru-RU"
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    checkpoint = load_checkpoint()
    print(f"Monitoring new ads after {checkpoint.isoformat()}, timezone={page.evaluate('Intl.DateTimeFormat().resolvedOptions().timeZone')}", flush=True)
    while True:
        started = time.monotonic()
        try:
            if run_once(page, checkpoint):
                checkpoint = datetime.now(local_tz)
                save_checkpoint(checkpoint)
        except Exception as exc:
            print(f"Check failed: {type(exc).__name__}", flush=True)
        elapsed = time.monotonic() - started
        delay = max(0, int(os.getenv("CHECK_INTERVAL_SECONDS", "30")) - elapsed)
        print(f"CYCLE seconds={elapsed:.1f} wait={delay:.1f}", flush=True)
        time.sleep(delay)
