import os
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from olx_monitor import collect_ads, format_ad, matches_price
from telegram_sender import send_to_channel

load_dotenv()
session_dir = Path(os.getenv("DATA_DIR", "data")) / "session"

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(str(session_dir), headless=True, args=["--no-sandbox"])
    page = browser.pages[0] if browser.pages else browser.new_page()
    urls = [os.getenv("OLX_SEARCH_URL", ""), os.getenv("OLX_SEARCH_URL_EUR", "")]
    all_ads = []
    for url in dict.fromkeys(url for url in urls if url):
        all_ads.extend(collect_ads(page, url))
        if len([ad for ad in all_ads if matches_price(ad["text"])]) >= 3:
            break
    print(f"OLX'dan {len(all_ads)} ta e'lon o'qildi.")
    for sample in all_ads[:5]:
        print(f"- {sample['text'][:180]}")
    ads = [ad for ad in all_ads if matches_price(ad["text"])][:3]
    if not ads:
        print("Mos narxdagi e'lon topilmadi.")
    else:
        for ad in ads[:3]:
            send_to_channel(format_ad(ad))
        print(f"{min(3, len(ads))} ta OLX test e'loni kanalga yuborildi.")
    browser.close()
