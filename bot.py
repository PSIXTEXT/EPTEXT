import os
import requests
from flask import Flask, request
import logging

BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")

TARGET_CHANNELS = [-1001317416582, -1002185590715]

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        if "channel_post" in update:
            post = update["channel_post"]
            channel_id = post["chat"]["id"]
            if channel_id in TARGET_CHANNELS:
                message_id = post["message_id"]
                data = {
                    "chat_id": channel_id,
                    "message_id": message_id,
                    "reaction": [{"type": "emoji", "emoji": "🔥"}]
                }
                requests.post(f"{API_URL}/setMessageReaction", json=data, timeout=5)
                logger.info(f"🔥 Реакция на пост {message_id} в канале {channel_id}")
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return "OK", 200

@app.route("/", methods=["GET"])
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Устанавливаем webhook при запуске
    webhook_url = f"{RENDER_URL}/{BOT_TOKEN}"
    requests.get(f"{API_URL}/setWebhook?url={webhook_url}")
    logger.info(f"Webhook установлен: {webhook_url}")
    app.run(host="0.0.0.0", port=port)
