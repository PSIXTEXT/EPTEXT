import os
import requests
import json
import pytz
import time
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import logging

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# === КАНАЛЫ ДЛЯ РЕАКЦИЙ ===
REACTION_CHANNELS = [-1002185590715, -1001317416582]

# === ВАШИ КАНАЛЫ ДЛЯ ВИДЕО ===
YOUTUBE_CHANNEL_HANDLE = "psixonat"
RUTUBE_RSS_URL = "https://rutube.ru/rss/channel/41901830/"

# === ТЕКСТ К ВИДЕО ===
FOOTER_TEXT = """
Всем приятного просмотра.
Не забываем подписываться, ставить лайки и обязательно комментировать!"""

# === НАСТРОЙКА ===
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
LAST_VIDEOS_FILE = "last_videos.json"

# === РАБОТА С ФАЙЛОМ ПОСЛЕДНИХ ВИДЕО ===
def load_last_videos():
    try:
        with open(LAST_VIDEOS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"youtube": None, "rutube": None}

def save_last_videos(data):
    with open(LAST_VIDEOS_FILE, "w") as f:
        json.dump(data, f)

# ============================================
# ===== 1. РЕАКЦИИ НА ПОСТЫ В КАНАЛАХ =====
# ============================================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        
        # Обработка постов в каналах (ставим реакции)
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

# ============================================
# ===== 2. ОТСЛЕЖИВАНИЕ YOUTUBE =====
# ============================================
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
        return None
    except Exception as e:
        logger.error(f"Ошибка получения channel ID: {e}")
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
            pub_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            now = datetime.now(pub_time.tzinfo)
            hours_ago = (now - pub_time).total_seconds() / 3600
            
            videos.append({
                "id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}",
                "title": item["snippet"]["title"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "hours_ago": hours_ago
            })
        return videos
    except Exception as e:
        logger.error(f"YouTube ошибка: {e}")
        return []

def send_youtube_video(thumbnail, video_url, title):
    url = f"{API_URL}/sendPhoto"
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
        requests.post(url, json=data, timeout=10)
        logger.info(f"YouTube видео отправлено: {title}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки YouTube: {e}")
        return False

# ============================================
# ===== 3. ОТСЛЕЖИВАНИЕ RUTUBE (через RSS) =====
# ============================================
def get_rutube_videos_from_rss():
    try:
        response = requests.get(RUTUBE_RSS_URL, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        videos = []
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('.//atom:entry', ns):
            video_id = entry.find('atom:id', ns).text.split('/')[-1]
            title = entry.find('atom:title', ns).text
            link = entry.find('atom:link', ns).attrib['href']
            
            videos.append({
                "id": video_id,
                "url": link,
                "title": title,
                "thumbnail": f"https://rutube.ru/api/video/{video_id}/thumbnail/?size=500"
            })
        return videos[:5]
    except Exception as e:
        logger.error(f"Rutube RSS ошибка: {e}")
        return []

def send_rutube_video(video_url, title, thumbnail):
    url = f"{API_URL}/sendPhoto"
    caption = f"""🎬 <b>НОВОЕ ВИДЕО НА RUTUBE</b>

📹 {title}

<a href='{video_url}'>▶️ Смотреть на Rutube</a>
{FOOTER_TEXT}"""
    
    data = {
        "chat_id": CHANNEL_ID,
        "photo": thumbnail,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=data, timeout=10)
        logger.info(f"Rutube видео отправлено: {title}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки Rutube: {e}")
        return False

# ============================================
# ===== 4. ГЛАВНАЯ ПРОВЕРКА ВИДЕО =====
# ============================================
def check_all():
    logger.info("🔍 Проверка новых видео...")
    new_videos = []
    
    # YouTube
    if YOUTUBE_API_KEY:
        channel_id = get_youtube_channel_id(YOUTUBE_CHANNEL_HANDLE)
        if channel_id:
            videos = get_youtube_videos(channel_id)
            last_videos = load_last_videos()
            last_youtube_id = last_videos.get("youtube")
            
            if videos and videos[0]["id"] != last_youtube_id:
                for video in videos:
                    if video["id"] == last_youtube_id:
                        break
                    if video["hours_ago"] <= 24:
                        send_youtube_video(video["thumbnail"], video["url"], video["title"])
                        new_videos.append(f"YouTube: {video['title']}")
                        time.sleep(2)
                last_videos["youtube"] = videos[0]["id"]
                save_last_videos(last_videos)
    
    # Rutube
    videos = get_rutube_videos_from_rss()
    last_videos = load_last_videos()
    last_rutube_id = last_videos.get("rutube")
    
    if videos and videos[0]["id"] != last_rutube_id:
        for video in videos:
            if video["id"] == last_rutube_id:
                break
            send_rutube_video(video["url"], video["title"], video["thumbnail"])
            new_videos.append(f"Rutube: {video['title']}")
            time.sleep(2)
        last_videos["rutube"] = videos[0]["id"]
        save_last_videos(last_videos)
    
    if not new_videos:
        url = f"{API_URL}/sendMessage"
        data = {
            "chat_id": CHANNEL_ID,
            "text": f"📭 За сегодня новых видео не найдено.\n\nПроверка выполнена в {datetime.now().strftime('%H:%M:%S')}",
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, json=data, timeout=10)
            logger.info("Новых видео нет")
        except Exception as e:
            logger.error(f"Ошибка: {e}")
    else:
        logger.info(f"Отправлено {len(new_videos)} видео")

# ============================================
# ===== 5. ПЛАНИРОВЩИК (ежедневно в 15:00 МСК) =====
# ============================================
def schedule_daily_check():
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Moscow"))
    scheduler.add_job(
        func=check_all,
        trigger="cron",
        hour=15,
        minute=0,
        id="daily_youtube_rutube_check"
    )
    scheduler.start()
    logger.info("⏰ Планировщик запущен. Проверка каждый день в 15:00 по МСК")

# ============================================
# ===== 6. FLASK МАРШРУТЫ =====
# ============================================
@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route("/check", methods=["GET"])
def manual_check():
    """Ручной запуск проверки видео через браузер"""
    threading.Thread(target=check_all).start()
    return "✅ Проверка видео запущена!", 200

# ============================================
# ===== 7. ЗАПУСК =====
# ============================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    schedule_daily_check()
    
    logger.info("🚀 БОТ ЗАПУЩЕН")
    logger.info("🔥 Функция 1: Реакции на посты в каналах")
    logger.info(f"   Каналы: {REACTION_CHANNELS}")
    logger.info("📺 Функция 2: Отслеживание видео")
    logger.info(f"   YouTube: @{YOUTUBE_CHANNEL_HANDLE}")
    logger.info(f"   Rutube: {RUTUBE_RSS_URL}")
    logger.info("📅 Ежедневная проверка видео в 15:00 по Москве")
    logger.info("🔗 Ручная проверка: /check")
    
    app.run(host="0.0.0.0", port=port)
