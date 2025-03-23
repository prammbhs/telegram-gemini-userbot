import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Default configs
API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# App configs
DEFAULT_CHAT_DURATION = 30  # minutes
MESSAGE_HISTORY_LIMIT = 15  # messages to include for context
RESPONSE_DELAY_MIN = 5  # seconds
RESPONSE_DELAY_MAX = 15  # seconds

# Session path
SESSION_FILE = "sessions/telegram_session"

# User-specific configs directory
USER_CONFIGS_DIR = os.path.join(os.path.dirname(__file__), "user_configs")
os.makedirs(USER_CONFIGS_DIR, exist_ok=True)

class DynamicConfig:
    """Provides user-specific configurations"""
    
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.config = self._load_config()
    
    def _load_config(self):
        """Load user-specific config if available, else use defaults"""
        if not self.user_id:
            return {
                "API_ID": API_ID,
                "API_HASH": API_HASH,
                "GEMINI_API_KEY": GEMINI_API_KEY,
                "SESSION_FILE": SESSION_FILE
            }
        
        # Try to load user-specific config
        config_path = os.path.join(USER_CONFIGS_DIR, f"{self.user_id}.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                
                # Use user config but fall back to defaults if missing
                return {
                    "API_ID": user_config.get("API_ID", API_ID),
                    "API_HASH": user_config.get("API_HASH", API_HASH),
                    "GEMINI_API_KEY": user_config.get("GEMINI_API_KEY", GEMINI_API_KEY),
                    "SESSION_FILE": f"sessions/telegram_session_{self.user_id}"
                }
            except Exception as e:
                print(f"Error loading user config: {e}")
        
        # Return default config with unique session file
        return {
            "API_ID": API_ID,
            "API_HASH": API_HASH,
            "GEMINI_API_KEY": GEMINI_API_KEY,
            "SESSION_FILE": f"sessions/telegram_session_{self.user_id}"
        }
    
    @property
    def API_ID(self):
        return self.config["API_ID"]
    
    @property
    def API_HASH(self):
        return self.config["API_HASH"]
    
    @property
    def GEMINI_API_KEY(self):
        return self.config["GEMINI_API_KEY"]
    
    @property
    def SESSION_FILE(self):
        return self.config["SESSION_FILE"]

def update_user_config(user_id, api_id, api_hash, gemini_api_key):
    """Update user-specific config"""
    if not user_id:
        return False
    
    config_path = os.path.join(USER_CONFIGS_DIR, f"{user_id}.json")
    
    user_config = {
        "API_ID": api_id,
        "API_HASH": api_hash,
        "GEMINI_API_KEY": gemini_api_key
    }
    
    try:
        with open(config_path, 'w') as f:
            json.dump(user_config, f)
        return True
    except Exception as e:
        print(f"Error saving user config: {e}")
        return False