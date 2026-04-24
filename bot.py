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

# === ID АДМИНА (куда отправлять уведомления, если нет видео) ===
ADMIN_ID = 483977434  # Ваш Telegram ID

# === КАНАЛЫ ДЛЯ РЕАКЦИЙ ===
REACTION_CHANNELS = [-1002185590715, -1001317416582]

# === ВАШ YouTube КАНАЛ ===
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
        return {"youtube_date": None, "last_check": None}

def save_last_videos(data):
    with open(LAST_VIDEOS_FILE, "w") as f:
        json.dump(data, f)

# ========== РЕАКЦИИ НА ПОСТЫ ==========
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        logger.info(f"📩 Вебхук получен")
        
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
        logger.error(f"❌ Ошибка webhook: {e}")
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
            "maxResults": 5,
            "order": "date",
            "type": "video",
            "key": YOUTUBE_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        videos = []
        for item in data.get("items", []):
            video_id = item["id"]["videoId"]
            published_at = item["snippet"]["publishedAt"]
            
            videos.append({
                "id": video_id,
                "url": f"https://youtube.com/watch?v={video_id}",
                "title": item["snippet"]["title"],
                "published_at": published_at,
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
            logger.info(f"✅ YouTube видео отправлено в канал: {title}")
            return True
        else:
            logger.error(f"❌ Ошибка YouTube: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки YouTube: {e}")
        return False

def send_admin_message(text):
    """Отправляет сообщение админу (только в личку)"""
    data = {
        "chat_id": ADMIN_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Сообщение отправлено админу")
            return True
        else:
            logger.error(f"❌ Ошибка отправки админу: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки админу: {e}")
        return False

# ========== ГЛАВНАЯ ПРОВЕРКА ==========
def check_all():
    logger.info("🔍 ===== НАЧАЛО ПРОВЕРКИ =====")
    new_videos = []
    tz = pytz.timezone("Europe/Moscow")
    today = datetime.now(tz).date()
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    time_str = datetime.now(tz).strftime("%H:%M:%S")
    
    last = load_last_videos()
    last["last_check"] = now_str
    save_last_videos(last)
    
    # ----- YouTube -----
    if YOUTUBE_API_KEY:
        logger.info("📺 Проверяем YouTube...")
        channel_id = get_youtube_channel_id(YOUTUBE_CHANNEL_HANDLE)
        if channel_id:
            videos = get_youtube_videos(channel_id)
            if videos:
                video = videos[0]
                pub_date = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00')).astimezone(tz).date()
                logger.info(f"YouTube последнее видео: {video['title']}")
                logger.info(f"Дата публикации: {pub_date}, Сегодня: {today}")
                
                if pub_date == today and last.get("youtube_date") != str(today):
                    logger.info("🎬 Отправляем YouTube видео в канал...")
                    if send_youtube_video(video["thumbnail"], video["url"], video["title"]):
                        new_videos.append(f"YouTube: {video['title']}")
                        last["youtube_date"] = str(today)
                        save_last_videos(last)
                else:
                    if last.get("youtube_date") == str(today):
                        logger.info("⏭ YouTube видео уже отправлено сегодня")
                    else:
                        logger.info(f"⏭ YouTube видео от {pub_date} — не сегодняшнее")
            else:
                logger.warning("⚠️ Не удалось получить видео с YouTube")
        else:
            logger.error("❌ Не удалось найти YouTube канал")
    else:
        logger.warning("⚠️ YOUTUBE_API_KEY не задан")
    
    # ===== ОТПРАВКА УВЕДОМЛЕНИЯ АДМИНУ (если нет видео) =====
    if not new_videos:
        msg = f"""📭 <b>Новых видео нет</b>

За сегодня ({today}) видео не найдено.

🕐 Время проверки: {now_str}"""
        send_admin_message(msg)
        logger.info("📭 Сообщение отправлено админу (новых видео нет)")
    else:
        logger.info(f"✅ Отправлено {len(new_videos)} видео в канал")
    
    logger.info("🔍 ===== КОНЕЦ ПРОВЕРКИ =====")

# ========== ПЛАНИРОВЩИК (ежедневно в 15:00 МСК) ==========
def schedule_daily_check():
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Moscow"))
    scheduler.add_job(
        func=check_all,
        trigger="cron",
        hour=15,
        minute=0,
        id="daily_check",
        misfire_grace_time=3600
    )
    scheduler.start()
    logger.info("⏰ Планировщик запущен. Проверка каждый день в 15:00 по МСК")

# ========== FLASK МАРШРУТЫ ==========
@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route("/check", methods=["GET"])
def manual_check():
    """Ручной запуск проверки"""
    threading.Thread(target=check_all).start()
    return "✅ Проверка видео запущена! Смотрите логи.", 200

@app.route("/reset", methods=["GET"])
def reset_memory():
    """Сброс памяти бота"""
    save_last_videos({"youtube_date": None, "last_check": None})
    return "✅ Память бота сброшена!", 200

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

@app.route("/force_youtube", methods=["GET"])
def force_youtube():
    """Принудительная отправка последнего видео с YouTube"""
    logger.info("🔥 Принудительная отправка YouTube (админ)")
    
    # Сначала сбрасываем память
    save_last_videos({"youtube_date": None, "last_check": None})
    
    channel_id = get_youtube_channel_id(YOUTUBE_CHANNEL_HANDLE)
    if channel_id:
        videos = get_youtube_videos(channel_id)
        if videos:
            video = videos[0]
            if send_youtube_video(video["thumbnail"], video["url"], video["title"]):
                last = load_last_videos()
                last["youtube_date"] = datetime.now(pytz.timezone("Europe/Moscow")).date().strftime("%Y-%m-%d")
                save_last_videos(last)
                send_admin_message(f"✅ Принудительно отправлено YouTube видео: {video['title']}")
                return f"✅ Принудительно отправлено: {video['title']}", 200
    return "❌ Не удалось получить видео с YouTube", 500

@app.route("/ping", methods=["GET"])
def ping():
    """Для keep-alive от UptimeRobot"""
    return "pong", 200

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
    schedule_daily_check()
    
    logger.info("🚀 ===== БОТ ЗАПУЩЕН =====")
    logger.info(f"🔥 Реакции на каналы: {REACTION_CHANNELS}")
    logger.info(f"📺 YouTube канал: @{YOUTUBE_CHANNEL_HANDLE}")
    logger.info(f"📢 Telegram канал для постов: {CHANNEL_ID}")
    logger.info(f"👤 Админ для уведомлений: {ADMIN_ID}")
    logger.info("⏰ Ежедневная проверка в 15:00 МСК")
    logger.info("🔗 Ручная проверка: /check")
    logger.info("🔧 Отладка: /debug")
    logger.info("🔄 Сброс памяти: /reset")
    logger.info("🏓 Keep-alive: /ping")
    
    app.run(host="0.0.0.0", port=port)
