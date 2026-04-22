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
RENDER_URL = os.environ.get("RENDER_URL", "https://eptext.onrender.com")

# === КАНАЛЫ ДЛЯ РЕАКЦИЙ ===
REACTION_CHANNELS = [-1002185590715, -1001317416582]

# === ВАШИ КАНАЛЫ ДЛЯ ВИДЕО ===
YOUTUBE_CHANNEL_HANDLE = "psixonat"
RUTUBE_RSS_URL = "https://rutube.ru/rss/channel/41901830/"

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
        return {"youtube_date": None, "rutube_id": None, "last_check": None}

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
                response = requests.post(url, json=data, timeout=5)
                if response.status_code == 200:
                    logger.info(f"🔥 Реакция на пост {message_id} в канале {channel_id}")
                else:
                    logger.error(f"❌ Ошибка реакции: {response.text}")
        
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
            logger.info(f"✅ YouTube видео отправлено: {title}")
            return True
        else:
            logger.error(f"❌ Ошибка YouTube: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки YouTube: {e}")
        return False

# ========== RUTUBE (RSS) ==========
def get_rutube_videos_from_rss():
    try:
        logger.info(f"📡 Запрос RSS: {RUTUBE_RSS_URL}")
        response = requests.get(RUTUBE_RSS_URL, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        # Проверяем, что это XML
        if not response.text.strip().startswith('<?xml'):
            logger.error(f"RSS вернул не XML: {response.text[:200]}")
            return []
        
        root = ET.fromstring(response.content)
        videos = []
        
        # Пробуем разные пространства имён
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            '': 'http://www.w3.org/2005/Atom'
        }
        
        for entry in root.findall('.//atom:entry', namespaces):
            try:
                # Получаем ID видео
                id_elem = entry.find('atom:id', namespaces)
                if id_elem is None or not id_elem.text:
                    continue
                video_id = id_elem.text.split('/')[-1]
                
                # Получаем название
                title_elem = entry.find('atom:title', namespaces)
                title = title_elem.text if title_elem is not None else "Без названия"
                
                # Получаем ссылку
                link_elem = entry.find('atom:link', namespaces)
                link = link_elem.attrib.get('href', '') if link_elem is not None else ''
                
                if video_id and link:
                    videos.append({
                        "id": video_id,
                        "url": link,
                        "title": title,
                        "thumbnail": f"https://rutube.ru/api/video/{video_id}/thumbnail/?size=500"
                    })
                    logger.info(f"📹 Найдено видео на Rutube: {title}")
            except Exception as e:
                logger.error(f"Ошибка парсинга entry: {e}")
                continue
        
        logger.info(f"📊 Rutube: найдено {len(videos)} видео")
        return videos[:5]
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Rutube RSS запрос ошибка: {e}")
        return []
    except ET.ParseError as e:
        logger.error(f"❌ Rutube XML ошибка: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Rutube общая ошибка: {e}")
        return []

def send_rutube_video(video_url, title, thumbnail):
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
        response = requests.post(f"{API_URL}/sendPhoto", json=data, timeout=15)
        if response.status_code == 200:
            logger.info(f"✅ Rutube видео отправлено: {title}")
            return True
        else:
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
    save_last_videos({"youtube_date": None, "rutube_id": None, "last_check": None})
    return "✅ Память бота сброшена! При следующей проверке бот отправит последние видео.", 200

@app.route("/debug", methods=["GET"])
def debug():
    """Отладочная информация"""
    info = {
        "memory": load_last_videos(),
        "render_url": RENDER_URL,
        "reaction_channels": REACTION_CHANNELS,
        "youtube_handle": YOUTUBE_CHANNEL_HANDLE,
        "rutube_rss": RUTUBE_RSS_URL,
        "channel_id": CHANNEL_ID,
        "time": datetime.now(pytz.timezone("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
    }
    return json.dumps(info, indent=2), 200, {'Content-Type': 'application/json'}

@app.route("/force_rutube", methods=["GET"])
def force_rutube():
    """Принудительная отправка последнего видео с Rutube"""
    logger.info("🔥 Принудительная отправка Rutube")
    videos = get_rutube_videos_from_rss()
    if videos:
        video = videos[0]
        if send_rutube_video(video["url"], video["title"], video["thumbnail"]):
            last = load_last_videos()
            last["rutube_id"] = video["id"]
            save_last_videos(last)
            return f"✅ Принудительно отправлено: {video['title']}", 200
        else:
            return "❌ Ошибка при отправке", 500
    else:
        return "❌ Не удалось получить видео с Rutube", 500

@app.route("/force_youtube", methods=["GET"])
def force_youtube():
    """Принудительная отправка последнего видео с YouTube"""
    logger.info("🔥 Принудительная отправка YouTube")
    channel_id = get_youtube_channel_id(YOUTUBE_CHANNEL_HANDLE)
    if channel_id:
        videos = get_youtube_videos(channel_id)
        if videos:
            video = videos[0]
            if send_youtube_video(video["thumbnail"], video["url"], video["title"]):
                last = load_last_videos()
                last["youtube_date"] = datetime.now(pytz.timezone("Europe/Moscow")).date().strftime("%Y-%m-%d")
                save_last_videos(last)
                return f"✅ Принудительно отправлено: {video['title']}", 200
    return "❌ Не удалось получить видео с YouTube", 500

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
    logger.info(f"📺 Rutube RSS: {RUTUBE_RSS_URL}")
    logger.info(f"📢 Telegram канал для постов: {CHANNEL_ID}")
    logger.info("⏰ Ежедневная проверка в 15:00 МСК")
    logger.info("🔗 Ручная проверка: /check")
    logger.info("🔧 Отладка: /debug")
    logger.info("🔄 Сброс памяти: /reset")
    logger.info("📺 Принудительно YouTube: /force_youtube")
    logger.info("📺 Принудительно Rutube: /force_rutube")
    
    app.run(host="0.0.0.0", port=port)
