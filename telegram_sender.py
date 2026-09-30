import os
import requests
import json


def send_to_channel(text: str, photo_url: str | None = None) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHANNEL_ID"]
    endpoint = f"https://api.telegram.org/bot{token}/sendRichMessage"
    payload = {
        "chat_id": chat_id,
        "rich_message": json.dumps({"html": text}, ensure_ascii=False),
    }
    response = requests.post(endpoint, data=payload, timeout=5)
    response.raise_for_status()
