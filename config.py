import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram configs
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

# Gemini configs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# App configs
DEFAULT_CHAT_DURATION = 30  # minutes
MESSAGE_HISTORY_LIMIT = 15  # messages to include for context
RESPONSE_DELAY_MIN = 5  # seconds
RESPONSE_DELAY_MAX = 15  # seconds

# Session path
SESSION_FILE = "sessions/telegram_session"