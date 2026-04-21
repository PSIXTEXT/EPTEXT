import os
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters

# Токен бота (единственное, что нужно)
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# ID каналов
CHANNEL_IDS = [-1002185590715, -1001317416582]

# Какие реакции ставить
REACTION_EMOJI = "🔥"  # можно сменить на 👍, ❤️ и т.д.

async def react_to_post(update: Update, context):
    """Ставит реакцию на каждый новый пост в отслеживаемых каналах"""
    chat_id = update.effective_chat.id
    message_id = update.effective_message.message_id
    
    # Проверяем, что это один из наших каналов
    if chat_id in CHANNEL_IDS:
        try:
            await context.bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=REACTION_EMOJI
            )
            print(f"✅ Поставил реакцию {REACTION_EMOJI} на пост {message_id} в канале {chat_id}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")

def main():
    # Создаём приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчик на все новые сообщения
    app.add_handler(MessageHandler(filters.ALL, react_to_post))
    
    print("🚀 Бот запущен и слушает каналы...")
    app.run_polling(allowed_updates=["channel_post"])

if __name__ == "__main__":
    main()