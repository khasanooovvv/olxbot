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
# New monitoring baseline: listings visible at this deployment are skipped.
baseline_path = data_dir / "baseline_initialized_1808"
session_dir = data_dir / "session"


def run_once(page) -> None:
    seen = load_seen(seen_path)
    urls = [os.getenv("OLX_SEARCH_URL", "")]
    euro_url = os.getenv("OLX_SEARCH_URL_EUR", "")
    if euro_url and euro_url not in urls:
        urls.append(euro_url)

    # On the first run, remember existing listings without sending them.
    # This makes monitoring start from the current moment, not from old ads.
    if not baseline_path.exists():
        current_ads = []
        for url in urls:
            if url:
                current_ads.extend(collect_ads(page, url))
        seen.update(ad["url"] for ad in current_ads)
        save_seen(seen_path, seen)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text("initialized", encoding="utf-8")
        print(f"Boshlang'ich baza yaratildi: {len(current_ads)} ta eski e'lon yuborilmadi.", flush=True)
        return

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
