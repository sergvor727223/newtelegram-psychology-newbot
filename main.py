import os
import logging
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from openai import AsyncOpenAI

# Базовая настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
LOG_BOT_TOKEN = os.getenv("LOG_BOT_TOKEN")
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")
WEBHOOK_PATH = f"/webhook/{TELEGRAM_TOKEN}"

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Инициализация OpenAI клиента
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def send_log_to_telegram(user_info: str, user_message: str, bot_response: str) -> None:
    """Отправка логов в Telegram канал"""
    try:
        async with Bot(token=LOG_BOT_TOKEN) as log_bot:
            log_message = (
                f"👤 Пользователь: {user_info}\n"
                f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"📥 Запрос:\n{user_message}\n\n"
                f"📤 Ответ:\n{bot_response}"
            )
            await log_bot.send_message(LOG_CHAT_ID, log_message)
            logger.info(f"Лог отправлен для пользователя {user_info}")
    except Exception as e:
        logger.error(f"Ошибка отправки лога: {e}")

@router.message(CommandStart())
async def command_start(message: Message) -> None:
    """Обработчик команды /start"""
    try:
        welcome_text = (
            "Привет! Я Алина, твой психологический ассистент и друг. "
            "Готова поддержать, выслушать и помочь разобраться с любым вопросом. "
            "Со мной можешь обсуждать всё что угодно, даже самые интимные вопросы и проблемы. "
            "Я слушаю тебя, говори."
        )
        await message.answer(welcome_text)
        
        # Логируем начало общения
        user_info = f"{message.from_user.full_name} (@{message.from_user.username})" if message.from_user.username else message.from_user.full_name
        await send_log_to_telegram(user_info, "/start", welcome_text)
        
    except Exception as e:
        logger.error(f"Ошибка в command_start: {e}")

@router.message(F.text)
async def handle_message(message: Message) -> None:
    """Обработчик текстовых сообщений"""
    try:
        # Получаем информацию о пользователе
        user_info = f"{message.from_user.full_name} (@{message.from_user.username})" if message.from_user.username else message.from_user.full_name
        
        # Создаем запрос к OpenAI
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": message.text}
            ],
            max_tokens=1000
        )
        
        # Получаем ответ
        response_text = response.choices[0].message.content.strip()
        
        # Отправляем ответ пользователю
        if len(response_text) > 4000:
            # Разбиваем длинные сообщения на части
            chunks = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
            for chunk in chunks:
                await message.answer(chunk)
            # Логируем полный ответ
            await send_log_to_telegram(user_info, message.text, response_text)
        else:
            await message.answer(response_text)
            # Логируем ответ
            await send_log_to_telegram(user_info, message.text, response_text)
            
    except Exception as e:
        error_message = "Извините, произошла ошибка. Попробуйте позже."
        await message.answer(error_message)
        logger.error(f"Ошибка в handle_message: {e}")
        # Логируем ошибку
        if 'user_info' in locals():
            await send_log_to_telegram(user_info, message.text, f"ERROR: {str(e)}")

async def on_startup(bot: Bot) -> None:
    """Действия при запуске бота"""
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
        logger.info(f"Setting webhook URL to: {webhook_url}")
        await bot.set_webhook(webhook_url)
        logger.info("Webhook has been set")
        
        # Отправляем уведомление о запуске бота
        try:
            async with Bot(token=LOG_BOT_TOKEN) as log_bot:
                await log_bot.send_message(
                    LOG_CHAT_ID,
                    f"🚀 Бот запущен\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о запуске: {e}")

async def on_shutdown(bot: Bot) -> None:
    """Действия при остановке бота"""
    await bot.session.close()
    logger.info("Bot shutdown complete")
    
    # Отправляем уведомление о остановке бота
    try:
        async with Bot(token=LOG_BOT_TOKEN) as log_bot:
            await log_bot.send_message(
                LOG_CHAT_ID,
                f"🔴 Бот остановлен\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о остановке: {e}")

def main() -> None:
    """Основная функция запуска бота"""
    try:
        # Создаем приложение
        app = web.Application()
        
        # Настраиваем вебхук хендлер
        SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        ).register(app, path=WEBHOOK_PATH)
        
        # Добавляем маршрут для проверки здоровья
        app.router.add_get("/", lambda request: web.Response(text="OK"))
        
        # Настраиваем хуки запуска и остановки
        app.on_startup.append(lambda app: on_startup(bot))
        app.on_shutdown.append(lambda app: on_shutdown(bot))
        
        # Получаем порт из переменных окружения
        port = int(os.getenv("PORT", 8080))
        
        # Запускаем приложение
        web.run_app(app, host="0.0.0.0", port=port)
        
    except Exception as e:
        logger.error(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
