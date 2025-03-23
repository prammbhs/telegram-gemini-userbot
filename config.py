import os
import json
from dotenv import load_dotenv
from datetime import datetime

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

# Free tier settings
FREE_TIER_ENABLED = True
FREE_TIER_API_KEY = os.environ.get("HOUSE_GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
FREE_TIER_MAX_REQUESTS = 50  # Maximum number of free requests per user
FREE_TIER_MAX_DAYS = 7  # Maximum number of days for free tier access

# Create sessions directory
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Session path
SESSION_FILE = os.path.join(SESSIONS_DIR, "telegram_session")

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
                
                # Get user's API key or use free tier key if available and within limits
                gemini_api_key = self._get_appropriate_api_key(user_config)
                
                # Always use application-level Telegram API credentials
                # but use user-specific Gemini key and session file
                return {
                    "API_ID": API_ID,  # Use app-level API ID
                    "API_HASH": API_HASH,  # Use app-level API Hash
                    "GEMINI_API_KEY": gemini_api_key,
                    "SESSION_FILE": os.path.join(SESSIONS_DIR, f"telegram_session_{self.user_id}")
                }
            except Exception as e:
                print(f"Error loading user config: {e}")
        
        # Return default config with unique session file but app-level credentials
        return {
            "API_ID": API_ID,
            "API_HASH": API_HASH,
            "GEMINI_API_KEY": self._get_appropriate_api_key({}),
            "SESSION_FILE": os.path.join(SESSIONS_DIR, f"telegram_session_{self.user_id}")
        }
    
    def _get_appropriate_api_key(self, user_config):
        """Determine which API key to use based on user's free tier status"""
        # If user has their own API key, use it
        if user_config.get("GEMINI_API_KEY") and user_config.get("GEMINI_API_KEY") != FREE_TIER_API_KEY:
            return user_config.get("GEMINI_API_KEY")
            
        # If free tier is disabled, return user's key or default
        if not FREE_TIER_ENABLED:
            return user_config.get("GEMINI_API_KEY", GEMINI_API_KEY)
            
        # Check if user is within free tier limits
        usage = user_config.get("FREE_TIER_USAGE", {})
        total_requests = usage.get("total_requests", 0)
        start_date = usage.get("start_date")
        
        # If user has no usage data yet, they're eligible
        if not start_date:
            return FREE_TIER_API_KEY
            
        # Check request limit
        if total_requests >= FREE_TIER_MAX_REQUESTS:
            return user_config.get("GEMINI_API_KEY", GEMINI_API_KEY)
            
        # Check time limit
        if start_date:
            start = datetime.fromisoformat(start_date)
            days_elapsed = (datetime.now() - start).days
            if days_elapsed > FREE_TIER_MAX_DAYS:
                return user_config.get("GEMINI_API_KEY", GEMINI_API_KEY)
        
        # User is within free tier limits
        return FREE_TIER_API_KEY
    
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

def update_user_config(user_id, telegram_phone=None, gemini_api_key=None):
    """Update user-specific config - now without Telegram API credentials"""
    if not user_id:
        return False
    
    config_path = os.path.join(USER_CONFIGS_DIR, f"{user_id}.json")
    
    # Load existing config or create new one
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
        except Exception:
            user_config = {}
    else:
        user_config = {}
    
    # Update config values
    if telegram_phone is not None:
        user_config["TELEGRAM_PHONE"] = telegram_phone
    
    if gemini_api_key is not None:
        user_config["GEMINI_API_KEY"] = gemini_api_key
    
    # Initialize free tier usage tracking if not present
    if "FREE_TIER_USAGE" not in user_config and FREE_TIER_ENABLED:
        user_config["FREE_TIER_USAGE"] = {
            "total_requests": 0,
            "start_date": datetime.now().isoformat(),
            "last_request": None
        }
    
    try:
        with open(config_path, 'w') as f:
            json.dump(user_config, f)
        return True
    except Exception as e:
        print(f"Error saving user config: {e}")
        return False

def increment_api_usage(user_id):
    """Increment the user's API usage count"""
    if not user_id or not FREE_TIER_ENABLED:
        return
    
    config_path = os.path.join(USER_CONFIGS_DIR, f"{user_id}.json")
    
    # Load existing config
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
        except Exception:
            user_config = {}
    else:
        user_config = {}
    
    # Update usage tracking
    if "FREE_TIER_USAGE" not in user_config:
        user_config["FREE_TIER_USAGE"] = {
            "total_requests": 1,
            "start_date": datetime.now().isoformat(),
            "last_request": datetime.now().isoformat()
        }
    else:
        user_config["FREE_TIER_USAGE"]["total_requests"] += 1
        user_config["FREE_TIER_USAGE"]["last_request"] = datetime.now().isoformat()
    
    # Save updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(user_config, f)
    except Exception as e:
        print(f"Error updating API usage: {e}")