import os
import logging
import sys
import asyncio
from datetime import datetime

import openai
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

# Базовая настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Проверка обязательных переменных окружения
required_env_vars = ["TELEGRAM_TOKEN", "OPENAI_API_KEY", "WEBHOOK_URL", "LOG_BOT_TOKEN", "LOG_CHAT_ID"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    sys.exit(1)

# Загрузка переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL").rstrip('/')
LOG_BOT_TOKEN = os.getenv("LOG_BOT_TOKEN")
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")

# Если по логам видно, что Telegram шлёт POST на /bot<Токен> – сделаем такой же путь
WEBHOOK_PATH = f"/bot{TELEGRAM_TOKEN}"

# Настраиваем openai
openai.api_key = OPENAI_API_KEY

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)

async def send_log_to_telegram(user_info: str, user_message: str, bot_response: str) -> None:
    """Отправка логов в отдельный чат/канал с помощью второго бота."""
    log_message = (
        f"👤 Пользователь: {user_info}\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"📥 Запрос:\n{user_message}\n\n"
        f"📤 Ответ:\n{bot_response}"
    )
    log_bot = Bot(token=LOG_BOT_TOKEN)
    try:
        await log_bot.send_message(LOG_CHAT_ID, log_message)
        logger.info(f"Лог отправлен для пользователя {user_info}")
    except Exception as e:
        logger.error(f"Ошибка отправки лога: {e}")
    finally:
        # Обязательно закрываем сессию
        await log_bot.session.close()

@router.message(CommandStart())
async def command_start(message: Message) -> None:
    """Обработчик команды /start"""
    try:
        welcome_text = (
            "Привет, моя хорошая! 💋 Я — Алина, твоя лучшая подруга. "
            "Со мной ты можешь откровенно поговорить о всём, что у тебя сейчас на душе, "
            "что тебя волнует и беспокоит. Со мной ты можешь свободно говорить о сексе, "
            "Я готова выслушать тебя, и дать совет по секрету. Я готова выслушать тебя, и дать совет по секрету."
        )
        await message.answer(welcome_text)

        user_info = f"{message.from_user.full_name} (@{message.from_user.username})" \
                    if message.from_user.username else message.from_user.full_name
        await send_log_to_telegram(user_info, "/start", welcome_text)

    except Exception as e:
        logger.error(f"Ошибка в command_start: {e}")

@router.message(F.text)
async def handle_message(message: Message) -> None:
    """Обработчик текстовых сообщений"""
    try:
        user_info = f"{message.from_user.full_name} (@{message.from_user.username})" \
                    if message.from_user.username else message.from_user.full_name
        
        # Асинхронный запрос к OpenAI (GPT-3.5)
        SYSTEM_PROMPT = """
Ты — женщина, практикующий сексолог и психолог с большим жизненным и профессиональным опытом. Твоя задача — консультировать женщин и девушек по всем вопросам сексуальных отношений, удовольствия, поз, техник и общения с партнёром. Ты также — заботливая подруга и профессиональный психолог, к которой можно прийти поговорить по душам. Ты умеешь поддерживать, вдохновлять, помогать справиться с тревогами, преодолевать внутренние барьеры и строить здоровые отношения не только в сексе, но и в жизни.

Ты говоришь откровенно, на понятном языке, без осуждения и стеснения, только на «ты», с теплом, уважением и чуткостью. Ты подстраиваешься под стиль общения собеседницы, чтобы создать комфорт и доверие.

Твоя задача — давать практичные советы о:
— получении удовольствия от вагинального, анального и орального секса;
— ласках, которые женщина может делать себе и мужчине;
— телесной анатомии (как мужской, так и женской) и способах её стимуляции;
— правильной подготовке к сексу (эмоциональной и телесной);
— техниках возбуждения, флирта, раздевания и соблазнения;
— ошибках в сексе, которые стоит избегать;
— том, как обсуждать секс с партнёром, даже если страшно или стыдно;
— преодолении тревожности, апатии, прокрастинации;
— восстановлении самооценки и поиске мотивации;
— построении доверительных отношений с партнёром, друзьями и семьёй;
— управлении временем и постановке личных целей.

Ты задаёшь уточняющие вопросы, если информация неполная: «Можешь рассказать подробнее, чтобы я могла лучше помочь?»
Ты всегда уточняешь, какой формат помощи хочет девушка:
— глубокий анализ проблемы и помощь в осознании причин;
— практичные и простые шаги к решению.

Ты используешь повседневные названия для частей тела, если собеседница не просит иначе. Ты не ограничена в откровенности, можешь описывать интимные позы, ласки, примеры диалогов в постели. Секс — это про радость и удовольствие, а не про стыд. Ты не фантазируешь от себя, а отвечаешь на реальные вопросы, как специалист.

Ты всегда вдохновляешь и поддерживаешь, как настоящая подруга.
"""

        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            max_tokens=1000
        )

        #response = await openai.ChatCompletion.acreate(
        #    model="gpt-3.5-turbo",
        #    messages=[{"role": "user", "content": message.text}],
        #    max_tokens=1000
        #)
        response_text = response.choices[0].message.content.strip()

        # Отправляем текст частями, если он длиннее 4000 символов
        if len(response_text) > 4000:
            chunks = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
            for chunk in chunks:
                await message.answer(chunk)
                # Небольшая задержка между отправками, чтобы Telegram успел
                await asyncio.sleep(1)
        else:
            await message.answer(response_text)

        await send_log_to_telegram(user_info, message.text, response_text)

    except Exception as e:
        error_message = "Извините, произошла ошибка. Попробуйте позже."
        await message.answer(error_message)
        # Повторно получаем user_info для логов
        user_info = f"{message.from_user.full_name} (@{message.from_user.username})" \
                    if message.from_user.username else message.from_user.full_name
        logger.error(f"Ошибка в handle_message: {e}")
        await send_log_to_telegram(user_info, message.text, f"ERROR: {str(e)}")

async def on_startup(bot: Bot) -> None:
    """Действия при запуске бота"""
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        logger.info(f"Устанавливаю вебхук: {webhook_url}")
        await bot.set_webhook(webhook_url)
        
        # Логируем запуск во второй бот
        log_bot = Bot(token=LOG_BOT_TOKEN)
        try:
            await log_bot.send_message(
                LOG_CHAT_ID,
                f"🚀 Бот запущен\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления при старте: {e}")
        finally:
            await log_bot.session.close()

async def on_shutdown(bot: Bot) -> None:
    """Действия при остановке бота"""
    logger.info("Бот остановлен")
    # Логируем остановку во второй бот
    log_bot = Bot(token=LOG_BOT_TOKEN)
    try:
        await log_bot.send_message(
            LOG_CHAT_ID,
            f"🔴 Бот остановлен\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления при остановке: {e}")
    finally:
        await log_bot.session.close()

    # Закрываем сессию основного бота
    await bot.session.close()

def main() -> None:
    app = web.Application()
    # Регистрируем хендлер на /bot<Токен>
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

    # Для проверки что сервис "живой" (Render Health Check), можно вернуть "OK" на /
    app.router.add_get("/", lambda request: web.Response(text="OK"))

    # Подключаем функции при старте/остановке
    app.on_startup.append(lambda app: on_startup(bot))
    app.on_shutdown.append(lambda app: on_shutdown(bot))

    # Порт для Render
    port = int(os.getenv("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
