import os
import logging
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from openai import AsyncOpenAI  # Используем асинхронный клиент OpenAI

sys.stdout.reconfigure(encoding='utf-8')

# Импорт конфигураций
from config import TELEGRAM_TOKEN, OPENAI_API_KEY, LOG_BOT_TOKEN, LOG_CHAT_ID, WEBHOOK_URL
from system_prompt import SYSTEM_PROMPT

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Инициализация асинхронных объектов
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)  # Асинхронный клиент OpenAI

async def send_log_to_telegram(user: str, user_message: str, bot_response: str):
    """Асинхронная отправка логов"""
    try:
        log_bot = Bot(token=LOG_BOT_TOKEN)
        log_message = (
            f"Пользователь: {user}\n"
            f"Время: {datetime.now()}\n\n"
            f"Запрос:\n{user_message}\n\n"
            f"Ответ:\n{bot_response}"
        )
        await log_bot.send_message(LOG_CHAT_ID, log_message)
        logger.info(f"Лог для {user} отправлен")
    except Exception as e:
        logger.error(f"Ошибка лога: {e}", exc_info=True)

@dp.message(Commands=("start"))
async def send_welcome(message: types.Message):
    """Обработчик /start"""
    try:
        welcome_text = (
            "Привет! Я Алина, твой психологический ассистент и друг. "
            "Готова поддержать, выслушать и помочь разобраться с любым вопросом. "
            "Со мной можешь обсуждать всё что угодно, даже самые имтимные вопросы и проблемы. "
            "Я слушаю тебя,говори."
        )
        await message.reply(welcome_text)
        logger.info(f"Пользователь {message.from_user.username} запустил бота")
    except Exception as e:
        logger.error(f"Ошибка /start: {e}")

@dp.message()
async def handle_message(message: types.Message):
    """Основной обработчик"""
    try:
        # Асинхронный запрос к OpenAI
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        bot_response = response.choices[0].message.content.strip()
        
        # Отправка лога
        await send_log_to_telegram(
            message.from_user.username, 
            message.text, 
            bot_response
        )
        
        # Отправка частями
        if len(bot_response) > 4000:
            for chunk in [bot_response[i:i+4000] for i in range(0, len(bot_response), 4000)]:
                await message.reply(chunk)
        else:
            await message.reply(bot_response)
            
        logger.info(f"Обработано сообщение от {message.from_user.username}")

    except Exception as e:
        error_message = "Извините, возникли проблемы с обработкой вашего запроса. Пожалуйста, попробуйте позже."
        await message.reply(error_message)
        logger.error(f"Ошибка OpenAI: {e}")

async def on_startup(app: web.Application):
    """Настройка вебхука при запуске"""
    await bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook",
        drop_pending_updates=True
    )
    logger.info("Бот запущен через вебхук")

async def on_shutdown(app: web.Application):
    """Очистка при завершении"""
    await bot.delete_webhook()
    logger.info("Вебхук удален")

def main():
    # Создание aiohttp приложения
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Регистрация обработчика Telegram
    SimpleRequestHandler(dp, bot=bot).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    
    # Запуск сервера
    web.run_app(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))  # Важно для Render
    )

if __name__ == "__main__":
    main()
