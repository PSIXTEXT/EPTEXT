import os
import requests
import json
import pytz
import time
import threading
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import logging

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
RENDER_URL = os.environ.get("RENDER_URL", "https://eptext.onrender.com")

# === ID АДМИНА ===
ADMIN_ID = 483977434

# === КАНАЛЫ ДЛЯ РЕАКЦИЙ ===
REACTION_CHANNELS = [-1002185590715, -1001317416582]

# === YouTube ===
YOUTUBE_CHANNEL_HANDLE = "psixonat"

FOOTER_TEXT = """
Всем приятного просмотра.
Не забываем подписываться, ставить лайки и обязательно комментировать!"""

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
LAST_VIDEOS_FILE = "last_videos.json"

def load_last_videos():
    try:
        with open(LAST_VIDEOS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"youtube_id": None, "last_check": None}

def save_last_videos(data):
    with open(LAST_VIDEOS_FILE, "w") as f:
        json.dump(data, f)

# ========== РЕАКЦИИ ==========
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        if update and "channel_post" in update:
            post = update["channel_post"]
            channel_id = post["chat"]["id"]
            if channel_id in REACTION_CHANNELS:
                message_id = post["message_id"]
                url = f"{API_URL}/setMessageReaction"
                data = {"chat_id": channel_id, "message_id": message_id, "reaction": [{"type": "emoji", "emoji": "🔥"}]}
                requests.post(url, json=data, timeout=5)
                logger.info(f"🔥 Реакция")
        return "OK", 200
    except:
        return "OK", 200

# ========== YOUTUBE ==========
def get_youtube_channel_id(handle):
    try:
        handle = handle.replace("@", "")
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {"part": "id", "forHandle": handle, "key": YOUTUBE_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data.get("items"):
            return data["items"][0]["id"]
        return None
    except Exception as e:
        logger.error(f"YouTube channel ID ошибка: {e}")
        return None

def get_youtube_videos(channel_id):
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {"part": "snippet", "channelId": channel_id, "maxResults": 5, "order": "date", "type": "video", "key": YOUTUBE_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        videos = []
        for item in data.get("items", []):
            video_id = item["id"]["videoId"]
            videos.append({
                "id": video_id,
                "url": f"https://youtube.com/watch?v={video_id}",
                "title": item["snippet"]["title"],
                "published_at": item["snippet"]["publishedAt"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"]
            })
        return videos
    except Exception as e:
        logger.error(f"YouTube ошибка: {e}")
        return []

def send_youtube_video(thumbnail, video_url, title):
    caption = f"""🎬 <b>НОВОЕ ВИДЕО НА YOUTUBE</b>

📹 {title}

<a href='{video_url}'>▶️ Смотреть на YouTube</a>
{FOOTER_TEXT}"""
    data = {"chat_id": CHANNEL_ID, "photo": thumbnail, "caption": caption, "parse_mode": "HTML"}
    try:
        response = requests.post(f"{API_URL}/sendPhoto", json=data, timeout=15)
        if response.status_code == 200:
            logger.info(f"✅ YouTube видео отправлено: {title}")
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка YouTube: {e}")
        return False

def send_admin_message(text):
    data = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
        logger.info("✅ Сообщение админу отправлено")
    except Exception as e:
        logger.error(f"Ошибка админу: {e}")

# ========== ГЛАВНАЯ ПРОВЕРКА ==========
def check_all():
    logger.info("🔍 НАЧАЛО ПРОВЕРКИ")
    tz = pytz.timezone("Europe/Moscow")
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    if not YOUTUBE_API_KEY:
        send_admin_message(f"⚠️ YOUTUBE_API_KEY не задан\n\nВремя: {now_str}")
        return
    
    channel_id = get_youtube_channel_id(YOUTUBE_CHANNEL_HANDLE)
    if not channel_id:
        send_admin_message(f"❌ YouTube канал не найден\n\nВремя: {now_str}")
        return
    
    videos = get_youtube_videos(channel_id)
    if not videos:
        send_admin_message(f"⚠️ Не удалось получить видео с YouTube\n\nВремя: {now_str}")
        return
    
    video = videos[0]
    last = load_last_videos()
    last_id = last.get("youtube_id")
    
    logger.info(f"Последнее видео: {video['title']} (ID: {video['id']})")
    logger.info(f"Последний отправленный ID: {last_id}")
    
    if last_id != video["id"]:
        logger.info("🎬 Отправляем новое видео...")
        if send_youtube_video(video["thumbnail"], video["url"], video["title"]):
            last["youtube_id"] = video["id"]
            last["last_check"] = now_str
            save_last_videos(last)
            logger.info("✅ Видео отправлено")
            return
    else:
        logger.info("⏭ Видео уже отправлено (ID совпадает)")
    
    send_admin_message(f"📭 Новых видео нет\n\nВремя: {now_str}")

# ========== ПЛАНИРОВЩИК (ежедневно в 15:00 МСК) ==========
def schedule_daily_check():
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Moscow"))
    scheduler.add_job(func=check_all, trigger="cron", hour=15, minute=0, id="daily_check")
    scheduler.start()
    logger.info("⏰ Планировщик запущен. Проверка каждый день в 15:00 по МСК")

# ========== KEEP-ALIVE (сам себя будит каждые 10 минут) ==========
def keep_alive():
    """Каждые 10 минут пингует самого себя, чтобы Render не усыпил"""
    while True:
        time.sleep(600)  # 10 минут
        try:
            url = f"{RENDER_URL}/ping"
            requests.get(url, timeout=10)
            logger.info("🏓 Self-ping")
        except Exception as e:
            logger.error(f"Self-ping ошибка: {e}")

# ========== FLASK МАРШРУТЫ ==========
@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

@app.route("/check", methods=["GET"])
def manual_check():
    threading.Thread(target=check_all).start()
    return "✅ Проверка запущена!", 200

@app.route("/reset", methods=["GET"])
def reset_memory():
    save_last_videos({"youtube_id": None, "last_check": None})
    return "✅ Память сброшена!", 200

@app.route("/force_youtube", methods=["GET"])
def force_youtube():
    save_last_videos({"youtube_id": None, "last_check": None})
    threading.Thread(target=check_all).start()
    return "✅ Принудительная отправка запущена!", 200

@app.route("/debug", methods=["GET"])
def debug():
    info = {
        "memory": load_last_videos(),
        "youtube_handle": YOUTUBE_CHANNEL_HANDLE,
        "channel_id": CHANNEL_ID,
        "admin_id": ADMIN_ID,
        "time": datetime.now(pytz.timezone("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    }
    return json.dumps(info, indent=2, ensure_ascii=False)

# ========== УСТАНОВКА ВЕБХУКА ==========
def setup_webhook():
    webhook_url = f"{RENDER_URL}/{BOT_TOKEN}"
    try:
        requests.get(f"{API_URL}/setWebhook?url={webhook_url}", timeout=10)
        logger.info(f"✅ Вебхук: {webhook_url}")
    except Exception as e:
        logger.error(f"❌ Вебхук ошибка: {e}")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    setup_webhook()
    schedule_daily_check()
    
    # Запускаем keep-alive в фоновом потоке
    threading.Thread(target=keep_alive, daemon=True).start()
    
    logger.info("🚀 ===== БОТ ЗАПУЩЕН =====")
    logger.info(f"🔥 Реакции на каналы: {REACTION_CHANNELS}")
    logger.info(f"📺 YouTube: @{YOUTUBE_CHANNEL_HANDLE}")
    logger.info(f"👤 Админ: {ADMIN_ID}")
    logger.info("⏰ Ежедневная проверка в 15:00 МСК")
    logger.info("🔗 /check - ручная проверка")
    logger.info("🔗 /force_youtube - принудительная отправка")
    logger.info("🔗 /reset - сброс памяти")
    logger.info("🔗 /debug - отладка")
    
    app.run(host="0.0.0.0", port=port)
