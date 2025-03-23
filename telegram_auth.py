import os
import asyncio
import sys
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
import config

class TelegramAuthHandler:
    def __init__(self, user_id=None, api_id=None, api_hash=None, phone_number=None):
        # Get dynamic config for this user
        self.config_instance = config.DynamicConfig(user_id)
        
        # Use provided credentials or fall back to config (which uses app-level credentials)
        self.api_id = api_id or self.config_instance.API_ID
        self.api_hash = api_hash or self.config_instance.API_HASH
        self.phone_number = phone_number
        self.user_id = user_id
        
        # Session file path
        self.session_file = self.config_instance.SESSION_FILE
        
        # Ensure sessions directory exists
        os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
        
        # Verification data holders
        self.client = None
        self.phone_code_hash = None
        self.verification_code = None
        
        print(f"Using Telegram API ID: {self.api_id}")
        print(f"Session file path: {self.session_file}")
    
    async def _create_client(self):
        """Create and connect the Telegram client"""
        if self.client and self.client.is_connected():
            return self.client
            
        self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
        await self.client.connect()
        return self.client
        
    async def start_authentication(self):
        """Initiate the authentication process by sending code to phone"""
        try:
            # Create Telegram client
            self.client = await self._create_client()
            
            # Check if already authorized
            if await self.client.is_user_authorized():
                try:
                    await self.client.disconnect()
                    self.client = None
                except:
                    pass
                return {"status": "already_authorized", "message": "Already authorized with Telegram"}
            
            # Send code to the phone number
            if not self.phone_number:
                return {"status": "error", "message": "Phone number is required"}
                
            result = await self.client.send_code_request(self.phone_number)
            self.phone_code_hash = result.phone_code_hash
            
            return {
                "status": "code_sent", 
                "message": f"Verification code sent to {self.phone_number}",
                "phone_code_hash": self.phone_code_hash
            }
            
        except Exception as e:
            # Clean up
            if self.client:
                try:
                    await self.client.disconnect()
                    self.client = None
                except:
                    pass
            return {"status": "error", "message": f"Error sending verification code: {str(e)}"}
    
    async def verify_code(self, code, password=None):
        """Verify a code received via Telegram"""
        if not self.phone_code_hash:
            return {"status": "error", "message": "Authentication process not initiated properly"}
            
        try:
            # Create a new client for verification
            self.client = await self._create_client()
                
            # Verify the code
            try:
                await self.client.sign_in(
                    phone=self.phone_number, 
                    code=code, 
                    phone_code_hash=self.phone_code_hash
                )
                
            except PhoneCodeInvalidError:
                try:
                    await self.client.disconnect()
                    self.client = None
                except:
                    pass
                return {"status": "error", "message": "Invalid verification code. Please try again."}
                
            except SessionPasswordNeededError:
                # 2FA is enabled
                if not password:
                    return {
                        "status": "2fa_needed", 
                        "message": "Two-factor authentication is enabled. Please provide your password."
                    }
                    
                # Sign in with 2FA password
                await self.client.sign_in(password=password)
                
            # Successfully signed in
            # Get user info
            me = await self.client.get_me()
            
            # Disconnect (we'll reconnect when starting the bot)
            try:
                await self.client.disconnect()
                self.client = None
            except:
                pass
            
            return {
                "status": "success", 
                "message": f"Successfully authenticated as {me.first_name} {me.last_name if me.last_name else ''} (@{me.username if me.username else 'No username'})",
                "user_info": {
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone,
                    "id": me.id
                }
            }
            
        except Exception as e:
            # Clean up
            if self.client:
                try:
                    await self.client.disconnect()
                    self.client = None
                except:
                    pass
            return {"status": "error", "message": f"Error verifying code: {str(e)}"}
            
    def is_authenticated(self):
        """Check if the user is already authenticated"""
        # Ensure sessions directory exists
        os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
        
        # For web usage, we'll check if the session file exists
        session_file_path = f"{self.session_file}.session"
        is_auth = os.path.exists(session_file_path)
        
        # Log the check for debugging
        print(f"Checking session file {session_file_path}: {'Exists' if is_auth else 'Not found'}")
        
        return is_auth
            
    async def check_auth_status(self):
        """Check if already authenticated with Telegram"""
        try:
            # Create Telegram client
            client = TelegramClient(self.session_file, self.api_id, self.api_hash)
            
            # Connect to Telegram servers
            await client.connect()
            
            # Check if already authorized
            is_authorized = await client.is_user_authorized()
            
            # Get user info if authorized
            user_info = None
            if is_authorized:
                me = await client.get_me()
                user_info = {
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone,
                    "id": me.id
                }
            
            # Disconnect
            try:
                await client.disconnect()
            except:
                pass
            
            return {
                "status": "authorized" if is_authorized else "unauthorized",
                "user_info": user_info
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Error checking authentication status: {str(e)}"}

# Command-line authentication helper for testing
async def interactive_auth():
    """Interactive authentication from command line"""
    print("=== Telegram Authentication ===")
    api_id = input("Enter API ID: ")
    api_hash = input("Enter API Hash: ")
    phone = input("Enter phone number (with country code, e.g. +1234567890): ")
    
    auth = TelegramAuthHandler(api_id=api_id, api_hash=api_hash, phone_number=phone)
    
    # Start authentication
    result = await auth.start_authentication()
    print(result["message"])
    
    if result["status"] == "code_sent":
        code = input("Enter the verification code received on Telegram: ")
        result = await auth.verify_code(code)
        
        if result["status"] == "2fa_needed":
            print(result["message"])
            password = input("Enter your 2FA password: ")
            result = await auth.verify_code(code, password)
            
        print(result["message"])
    
    print("Authentication process complete.")

if __name__ == "__main__":
    # Run interactive auth when script is executed directly
    asyncio.run(interactive_auth())
