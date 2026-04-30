import os
import requests
import json
import pytz
import time
import threading
from datetime import datetime
from flask import Flask, request
import logging

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
RENDER_URL = os.environ.get("RENDER_URL", "https://eptext.onrender.com")

# === ID АДМИНА (куда отправлять уведомления) ===
ADMIN_ID = 483977434

# === КАНАЛЫ ДЛЯ РЕАКЦИЙ ===
REACTION_CHANNELS = [-1002185590715, -1001317416582]

# === YouTube КАНАЛ ===
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
        return {"youtube_id": None, "last_check": None, "last_video_title": None, "last_video_date": None}

def save_last_videos(data):
    with open(LAST_VIDEOS_FILE, "w") as f:
        json.dump(data, f)

# ========== РЕАКЦИИ НА ПОСТЫ ==========
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
                data = {
                    "chat_id": channel_id,
                    "message_id": message_id,
                    "reaction": [{"type": "emoji", "emoji": "🔥"}]
                }
                requests.post(url, json=data, timeout=5)
                logger.info(f"🔥 Реакция на пост {message_id} в канале {channel_id}")
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка webhook: {e}")
        return "OK", 200

# ========== YOUTUBE ==========
def get_youtube_channel_id(handle):
    try:
        handle = handle.replace("@", "")
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "part": "id",
            "forHandle": handle,
            "key": YOUTUBE_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data.get("items"):
            return data["items"][0]["id"]
        logger.error(f"YouTube канал не найден: {handle}")
        return None
    except Exception as e:
        logger.error(f"Ошибка YouTube channel ID: {e}")
        return None

def get_youtube_videos(channel_id):
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "maxResults": 10,
            "order": "date",
            "type": "video",
            "key": YOUTUBE_API_KEY
        }
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
    data = {
    "chat_id": CHANNEL_ID,
        "photo": thumbnail,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(f"{API_URL}/sendPhoto", json=data, timeout=15)
        if response.status_code == 200:
            logger.info(f"✅ YouTube видео отправлено: {title}")
            return True
        else:
            logger.error(f"❌ Ошибка YouTube: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки YouTube: {e}")
        return False

def send_admin_message(text):
    """Отправляет сообщение админу в личку"""
    data = {
        "chat_id": ADMIN_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
        logger.info("✅ Сообщение админу отправлено")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки админу: {e}")
        return False

# ========== ГЛАВНАЯ ПРОВЕРКА (находит САМОЕ СВЕЖЕЕ ВИДЕО) ==========
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
    
    # Находим самое свежее видео (по дате публикации)
    newest_video = None
    newest_date = None
    
    for video in videos:
        pub_date = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00')).astimezone(tz)
        if newest_date is None or pub_date > newest_date:
            newest_date = pub_date
            newest_video = video
    
    if not newest_video:
        send_admin_message(f"⚠️ Не удалось определить самое свежее видео\n\nВремя: {now_str}")
        return
    
    pub_date_str = newest_date.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Самое свежее видео: {newest_video['title']}")
    logger.info(f"Дата публикации: {pub_date_str}")
    
    last = load_last_videos()
    last_id = last.get("youtube_id")
    
    logger.info(f"ID видео: {newest_video['id']}")
    logger.info(f"Последний отправленный ID: {last_id}")
    
    # Если ID не совпадает — отправляем
    if last_id != newest_video["id"]:
        logger.info("🎬 Отправляем новое видео...")
        if send_youtube_video(newest_video["thumbnail"], newest_video["url"], newest_video["title"]):
            last["youtube_id"] = newest_video["id"]
            last["last_check"] = now_str
            last["last_video_title"] = newest_video["title"]
            last["last_video_date"] = pub_date_str
            save_last_videos(last)
            logger.info("✅ Видео отправлено")
            return
    else:
        logger.info("⏭ Видео уже отправлено (ID совпадает)")
    
    # Если дошли сюда — новых видео нет
    send_admin_message(f"📭 Новых видео нет\n\nПоследнее отправленное: {last.get('last_video_title', 'нет')}\nСамое свежее на YouTube: {newest_video['title']}\nВремя: {now_str}")

# ========== KEEP-ALIVE (сам себя будит каждые 10 минут) ==========
def keep_alive():
    """Каждые 10 минут пингует самого себя, чтобы Render не усыпил"""
    while True:
        time.sleep(600)  # 10 минут
        try:
            url = f"{RENDER_URL}/ping"
            response = requests.get(url, timeout=10)
            logger.info(f"🏓 Self-ping: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Self-ping ошибка: {e}")

# ========== FLASK МАРШРУТЫ ==========
@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route("/ping", methods=["GET"])
def ping():
    """Для keep-alive"""
    return "pong", 200

@app.route("/check", methods=["GET"])
def manual_check():
    """Ручная проверка (без сброса памяти)"""
    threading.Thread(target=check_all).start()
    return "✅ Проверка запущена! Смотрите логи.", 200

@app.route("/reset", methods=["GET"])
def reset_memory():
    """Сброс памяти бота"""
    save_last_videos({"youtube_id": None, "last_check": None, "last_video_title": None, "last_video_date": None})
    return "✅ Память бота сброшена! При следующей проверке бот отправит последнее видео.", 200

@app.route("/force_youtube", methods=["GET"])
def force_youtube():
    """Принудительная отправка последнего видео (сбрасывает память) — ЭТОТ URL ВЫЗЫВАЕТ CRON-JOB"""
    logger.info("🔥 Принудительная отправка YouTube (force_youtube)")
    # Сбрасываем память
    save_last_videos({"youtube_id": None, "last_check": None, "last_video_title": None, "last_video_date": None})
    # Запускаем проверку в фоне
    threading.Thread(target=check_all).start()
    return "✅ Принудительная отправка запущена! Видео скоро появится в канале.", 200

@app.route("/debug", methods=["GET"])
def debug():
    """Отладочная информация"""
    info = {
        "memory": load_last_videos(),
        "render_url": RENDER_URL,
        "reaction_channels": REACTION_CHANNELS,
        "youtube_handle": YOUTUBE_CHANNEL_HANDLE,
        "channel_id": CHANNEL_ID,
        "admin_id": ADMIN_ID,
        "time": datetime.now(pytz.timezone("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    }
    return json.dumps(info, indent=2, ensure_ascii=False), 200, {'Content-Type': 'application/json'}

# ========== УСТАНОВКА ВЕБХУКА ==========
def setup_webhook():
    webhook_url = f"{RENDER_URL}/{BOT_TOKEN}"
    url = f"{API_URL}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Вебхук установлен: {webhook_url}")
        else:
            logger.error(f"❌ Ошибка установки вебхука: {response.text}")
    except Exception as e:
        logger.error(f"❌ Не удалось установить вебхук: {e}")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    setup_webhook()
    
    # Запускаем keep-alive в фоновом потоке
    threading.Thread(target=keep_alive, daemon=True).start()
    
    logger.info("🚀 ===== БОТ ЗАПУЩЕН =====")
    logger.info(f"🔥 Реакции на каналы: {REACTION_CHANNELS}")
    logger.info(f"📺 YouTube канал: @{YOUTUBE_CHANNEL_HANDLE}")
    logger.info(f"📢 Telegram канал для постов: {CHANNEL_ID}")
    logger.info(f"👤 Админ для уведомлений: {ADMIN_ID}")
    logger.info("📅 Ежедневная проверка: cron-job.org вызывает /force_youtube в 15:00 МСК")
    logger.info("🔗 Ручная проверка: /check")
    logger.info("🔧 Отладка: /debug")
    logger.info("🔄 Сброс памяти: /reset")
    logger.info("🔥 Принудительная отправка: /force_youtube (для cron-job)")
    logger.info("🏓 Keep-alive: /ping (каждые 10 минут self-ping)")
    
    app.run(host="0.0.0.0", port=port)
