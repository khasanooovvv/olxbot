# OLX → Telegram bot

1. `.env.example` nusxasini `.env` qilib, Telegram sozlamalarini kiriting.
2. Botni private kanalga administrator qiling.
3. `pip install -r requirements.txt` va `playwright install chromium` bajaring.
4. Birinchi login uchun `python setup_session.py` bajaring, ochilgan brauzerda OLX’ga qo‘lda kiring va terminalda Enter bosing.
5. `python main.py` bilan ishga tushiring.

Railway’da `DATA_DIR=/app/data` qilib Volume ulang. `data/session` va `data/seen_ads.json` shu Volume’da saqlanadi.

Eslatma: OLX sahifa tuzilishi yoki CAPTCHA o‘zgarsa, `olx_monitor.py` selektorlarini moslashtirish kerak bo‘lishi mumkin.
