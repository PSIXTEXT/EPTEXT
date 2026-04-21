import os
import requests
from flask import Flask, request
import logging

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")

# === КАНАЛЫ ДЛЯ РЕАКЦИЙ ===
TARGET_CHANNELS = [
    -1002185590715,   # psixonat_official
    -1001317416582,   # eternalparadise
]

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === СОЗДАЁМ FLASK ПРИЛОЖЕНИЕ ===
app = Flask(__name__)

# === БАЗОВЫЙ URL ДЛЯ API TELEGRAM ===
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# === ВЕБХУК ДЛЯ ПРИЁМА ОБНОВЛЕНИЙ ===
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        
        # Проверяем, что это пост в канале
        if update and "channel_post" in update:
            post = update["channel_post"]
            channel_id = post["chat"]["id"]
            message_id = post["message_id"]
            
            # Если канал в нашем списке - ставим реакцию
            if channel_id in TARGET_CHANNELS:
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
                    logger.error(f"❌ Ошибка API: {response.text}")
        
        return "OK", 200
    except Exception as e:
        logger.error(f"❌ Ошибка webhook: {e}")
        return "OK", 200

# === ПРОВЕРКА ЗДОРОВЬЯ (ДЛЯ RENDER) ===
@app.route("/", methods=["GET"])
def health():
    return "OK", 200

# === УСТАНОВКА ВЕБХУКА ПРИ ЗАПУСКЕ ===
webhook_url = f"{RENDER_URL}/{BOT_TOKEN}"
try:
    response = requests.get(f"{API_URL}/setWebhook?url={webhook_url}")
    if response.status_code == 200 and response.json().get("ok"):
        logger.info(f"✅ Вебхук установлен: {webhook_url}")
    else:
        logger.error(f"❌ Ошибка установки вебхука: {response.text}")
except Exception as e:
    logger.error(f"❌ Не удалось установить вебхук: {e}")

logger.info("🚀 Бот реакций запущен и слушает каналы...")

# === ЗАПУСК (ДЛЯ GUNICORN) ===
if __name__ != "__main__":
    # При запуске через gunicorn — ничего не делаем, Flask уже запущен
    pass
