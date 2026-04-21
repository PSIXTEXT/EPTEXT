import os
import requests
from flask import Flask, request
import logging

BOT_TOKEN = os.environ.get("BOT_TOKEN")
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
                
                # ПРЯМОЙ ВЫЗОВ API (работает всегда)
                url = f"{API_URL}/setMessageReaction"
                data = {
                    "chat_id": channel_id,
                    "message_id": message_id,
                    "reaction": [{"type": "emoji", "emoji": "🔥"}]
                }
                response = requests.post(url, json=data, timeout=5)
                
                if response.status_code == 200:
                    logger.info(f"🔥 Реакция на пост {message_id} в канале {channel_id}")
                else:
                    logger.error(f"Ошибка API: {response.text}")
                    
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return "OK", 200

@app.route("/", methods=["GET"])
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    # Устанавливаем вебхук
    webhook_url = f"{os.environ.get('RENDER_URL')}/{BOT_TOKEN}"
    requests.get(f"{API_URL}/setWebhook?url={webhook_url}")
    
    logger.info("🚀 Бот реакций запущен")
    app.run(host="0.0.0.0", port=port)
