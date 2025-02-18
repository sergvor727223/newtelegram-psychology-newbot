import os

# Обязательные переменные
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # Добавлено для работы вебхуков

# Опциональные переменные для логов (если не нужны - можно удалить)
LOG_BOT_TOKEN = os.getenv("LOG_BOT_TOKEN", "")
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID", "")