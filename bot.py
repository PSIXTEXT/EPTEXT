import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

BOT_TOKEN = os.environ.get('BOT_TOKEN')

CHANNEL_IDS = [-1002185590715, -1001317416582]
REACTION_EMOJI = "🔥"

async def react_to_post(update: Update, context):
    chat_id = update.effective_chat.id
    message_id = update.effective_message.message_id
    
    if chat_id in CHANNEL_IDS:
        try:
            await context.bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=REACTION_EMOJI
            )
            print(f"✅ Реакция {REACTION_EMOJI} на пост {message_id} в канале {chat_id}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")

def main():
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, react_to_post))
    
    print("🚀 Бот запущен и слушает каналы...")
    app.run_polling(allowed_updates=["channel_post"])

if __name__ == "__main__":
    main()
