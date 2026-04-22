import os
import requests
import json
import pytz
import time
from datetime import datetime
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
import logging

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# === ВАШИ КАНАЛЫ ===
YOUTUBE_CHANNEL_HANDLE = "psixonat"  # из ссылки @psixonat
RUTUBE_CHANNEL_URL = "https://rutube.ru/channel/41901830"

# === ТЕКСТ КОТОРЫЙ ДОБАВЛЯЕТСЯ К КАЖДОМУ ВИДЕО ===
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
        return {"youtube": None, "rutube": None}

def save_last_videos(data):
    with open(LAST_VIDEOS_FILE, "w") as f:
        json.dump(data, f)

# === ПРЕОБРАЗОВАНИЕ HANDLE В CHANNEL ID ===
def get_youtube_channel_id(handle):
    """Преобразует @username или handle в channel ID"""
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

# === ПОЛУЧЕНИЕ ПОСЛЕДНИХ ВИДЕО С YOUTUBE ===
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
                "published_at": published_at,
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "hours_ago": hours_ago
            })
        
        return videos
    except Exception as e:
        logger.error(f"YouTube ошибка: {e}")
        return []

# === ПОЛУЧЕНИЕ ПОСЛЕДНИХ ВИДЕО С RUTUBE ===
def get_rutube_videos():
    try:
        api_url = "https://rutube.ru/api/ugc/video/"
        params = {
            "channel_id": 41901830,
            "limit": 5,
            "order_by": "issue_date"
        }
        
        response = requests.get(api_url, params=params, timeout=10)
        data = response.json()
        
        videos = []
        for item in data.get("results", []):
            video_id = item["id"]
            videos.append({
                "id": str(video_id),
                "url": f"https://rutube.ru/video/{video_id}/",
                "title": item["title"],
                "thumbnail": item.get("thumbnail_url", ""),
                "published_at": item.get("issue_date", "")
            })
        
        return videos
        except Exception as e:
        logger.error(f"Rutube ошибка: {e}")
        return []

# === ОТПРАВКА В TELEGRAM С ДОБАВЛЕННЫМ ТЕКСТОМ ===
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

def send_rutube_video(video_url, title):
    url = f"{API_URL}/sendMessage"
    text = f"""🎬 <b>НОВОЕ ВИДЕО НА RUTUBE</b>

📹 {title}

<a href='{video_url}'>▶️ Смотреть на Rutube</a>

{FOOTER_TEXT}"""
    
    data = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        requests.post(url, json=data, timeout=10)
        logger.info(f"Rutube видео отправлено: {title}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки Rutube: {e}")
        return False

# === ГЛАВНАЯ ПРОВЕРКА ===
def check_all():
    logger.info("🔍 Проверка новых видео...")
    new_videos = []
    
    # === YouTube ===
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
        else:
            logger.error("Не удалось получить YouTube Channel ID")
    
    # === Rutube ===
    videos = get_rutube_videos()
    last_videos = load_last_videos()
    last_rutube_id = last_videos.get("rutube")
    
    if videos and videos[0]["id"] != last_rutube_id:
        for video in videos:
            if video["id"] == last_rutube_id:
                break
            send_rutube_video(video["url"], video["title"])
            new_videos.append(f"Rutube: {video['title']}")
            time.sleep(2)
        
        last_videos["rutube"] = videos[0]["id"]
        save_last_videos(last_videos)
    
    # Если новых видео нет
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

# === ПЛАНИРОВЩИК (ежедневно в 15:00 МСК) ===
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

# === FLASK ДЛЯ KEEP-ALIVE ===
@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route("/check", methods=["GET"])
def manual_check():
    check_all()
    return "Проверка запущена", 200

# === ЗАПУСК ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    schedule_daily_check()
    
    logger.info("🚀 Бот отслеживания видео запущен")
    logger.info(f"📺 YouTube канал: @{YOUTUBE_CHANNEL_HANDLE}")
    logger.info(f"📺 Rutube канал: {RUTUBE_CHANNEL_URL}")
    logger.info("📅 Ежедневная проверка в 15:00 по Москве")
    
    app.run(host="0.0.0.0", port=port)
