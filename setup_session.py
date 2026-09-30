import os
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


load_dotenv()
data_dir = Path(os.getenv("DATA_DIR", "data"))
session_dir = data_dir / "session"
session_dir.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        str(session_dir),
        headless=False,
        args=["--start-maximized"],
    )
    page = browser.pages[0] if browser.pages else browser.new_page()
    page.goto("https://www.olx.uz/", wait_until="domcontentloaded")
    print("OLX brauzerda ochildi. Login va CAPTCHA'ni qo'lda bajaring.")
    input("Login tugagach, shu oynada Enter bosing: ")
    print(f"Sessiya saqlandi: {session_dir.resolve()}")
    browser.close()
