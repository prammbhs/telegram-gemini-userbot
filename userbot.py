import asyncio
import os
import json
from telegram_client import TelegramUserbot
from ai_handler import GeminiAI
import time
import config
import socket
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GeminiUserbot')

class GeminiUserbot:
    def __init__(self, super_context, target_group, duration=30, user_id=None):
        self.super_context = super_context
        self.target_group = target_group
        self.duration = duration
        self.user_id = user_id
        self.learning_enabled = True
        self._is_running = False
        
        # We'll initialize these components during start()
        self.telegram_client = None
        self.ai_handler = None
        
        # But prepare the configuration
        self.config_instance = config.DynamicConfig(user_id)
        
        # Set up a logger for this instance
        self.log = logger
        
        # Track connection attempts
        self.connection_attempts = 0
        self.max_attempts = 5  # Increased from 3 to 5
    
    async def generate_ai_response(self, context, is_group_chat=True, message_id_to_reply=None):
        """Generate response using the AI handler"""
        if not self.ai_handler:
            raise Exception("AI handler not initialized. Please start the bot first.")
        
        return await self.ai_handler.generate_response(context, is_group_chat, message_id_to_reply)
    
    async def generate_initial_message(self):
        """Generate an initial message to start the conversation"""
        if not self.ai_handler:
            raise Exception("AI handler not initialized. Please start the bot first.")
        
        # Use the is_group_chat property from telegram_client for context awareness
        is_group = True
        if hasattr(self.telegram_client, 'is_group_chat'):
            is_group = self.telegram_client.is_group_chat

        return await self.ai_handler.generate_initial_message(is_group_chat=is_group)
    
    async def check_connection(self):
        """Test connection to Telegram servers before starting the bot"""
        try:
            # Try different Telegram servers and ports
            telegram_servers = [
                ("api.telegram.org", 443),
                ("149.154.167.50", 443),  # Telegram DC1
                ("149.154.167.51", 443),  # Telegram DC2
                ("149.154.175.100", 443), # Telegram DC3
            ]
            
            # Try each server until one responds
            for server, port in telegram_servers:
                try:
                    self.log.info(f"Testing connection to Telegram server {server}:{port}")
                    sock = socket.create_connection((server, port), timeout=5)
                    sock.close()
                    self.log.info(f"Successfully connected to {server}:{port}")
                    return True
                except (socket.timeout, socket.gaierror, ConnectionError) as e:
                    self.log.warning(f"Failed to connect to {server}:{port}: {str(e)}")
                    continue
                    
            return False
        except Exception as e:
            self.log.error(f"Error in connection check: {str(e)}")
            return False
    
    async def start(self):
        """Start the userbot with connection checking"""
        # Check for internet and Telegram server connection
        connection_attempts = 0
        max_attempts = self.max_attempts
        
        self.log.info("Starting Telegram Gemini Userbot...")
        
        # Check internet connectivity
        while connection_attempts < max_attempts:
            self.log.info(f"Checking Telegram connection (attempt {connection_attempts+1}/{max_attempts})...")
            if await self.check_connection():
                self.log.info("Connection to Telegram servers confirmed.")
                break
                
            connection_attempts += 1
            if connection_attempts >= max_attempts:
                error_msg = "Cannot connect to Telegram servers after multiple attempts. Please check your internet connection and try again later."
                self.log.error(error_msg)
                raise ConnectionError(error_msg)
            
            # Wait with exponential backoff before retrying
            retry_delay = min(30, 2 ** connection_attempts)  # Cap at 30 seconds
            self.log.info(f"Connection failed. Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
        
        self._is_running = True
        
        try:
            # 1. Initialize AI handler first with user_id for API key
            gemini_api_key = self.config_instance.GEMINI_API_KEY
            if not gemini_api_key:
                raise Exception("Gemini API key not configured. Please check your profile settings.")
            
            # Create AI handler with API key and verify it's valid
            self.ai_handler = GeminiAI(
                super_context=self.super_context,
                api_key=gemini_api_key,
                user_id=self.user_id  # Pass user_id for usage tracking
            )
            
            # Verify API key is valid and check free tier status
            if not self.ai_handler.api_key_valid:
                if self.ai_handler.using_free_tier:
                    print("WARNING: Using free tier but the house API key is invalid")
                else:
                    print("WARNING: Starting bot with invalid Gemini API key. Bot will use fallback responses.")
            
            # Set learning mode on AI handler
            if hasattr(self.ai_handler, 'set_learning_enabled'):
                self.ai_handler.set_learning_enabled(self.learning_enabled)
            
            # 2. Create and initialize the Telegram client
            self.telegram_client = TelegramUserbot(
                super_context=self.super_context,
                target_group=self.target_group,
                duration=self.duration,
                user_id=self.user_id,
                parent_bot=self  # Pass reference to self so client can access AI handler
            )
            
            # 3. Start Telegram client with better error handling specifically for CancelledError
            max_client_retries = 3
            for attempt in range(1, max_client_retries + 1):
                try:
                    self.log.info(f"Starting Telegram client (attempt {attempt}/{max_client_retries})...")
                    
                    # Handle CancelledError specifically - it often indicates a network timeout
                    # Wrap the start call with a timeout to prevent hanging connections
                    try:
                        # Set a timeout for the connection attempt to prevent hanging
                        await asyncio.wait_for(self.telegram_client.start(), timeout=30)
                        self.log.info("Telegram client started successfully")
                        break
                    except asyncio.TimeoutError:
                        self.log.error("Telegram connection timed out")
                        if attempt >= max_client_retries:
                            raise ConnectionError("Failed to connect to Telegram after multiple attempts - connection timed out")
                    except asyncio.CancelledError:
                        self.log.error("Telegram connection was cancelled - this usually indicates a network issue")
                        if attempt >= max_client_retries:
                            raise ConnectionError("Connection to Telegram servers was repeatedly cancelled - please check your internet connection")
                        
                    # Exponential backoff between retries
                    retry_wait = attempt * 4  # More aggressive waiting
                    self.log.info(f"Retrying in {retry_wait} seconds...")
                    await asyncio.sleep(retry_wait)
                except Exception as e:
                    self.log.error(f"Error starting Telegram client: {str(e)}")
                    if attempt >= max_client_retries:
                        raise
                    # Exponential backoff between retries
                    retry_wait = attempt * 4
                    self.log.info(f"Retrying in {retry_wait} seconds...")
                    await asyncio.sleep(retry_wait)
            
        except Exception as e:
            self._is_running = False
            self.log.error(f"Error starting GeminiUserbot: {str(e)}")
            raise
    
    async def stop(self):
        """Stop the userbot"""
        self.log.info("Stopping Telegram Gemini Userbot...")
        self._is_running = False
        
        # Stop the Telegram client
        if self.telegram_client:
            try:
                await self.telegram_client.stop()
                self.log.info("Telegram client stopped successfully")
            except Exception as e:
                self.log.error(f"Error stopping Telegram client: {str(e)}")
        
        # Save AI session logs if enabled
        if self.ai_handler and self.learning_enabled:
            try:
                self.ai_handler.save_session_log()
                self.log.info("AI session logs saved successfully")
            except Exception as e:
                self.log.error(f"Error saving AI session log: {str(e)}")
    
    async def add_resource(self, resource_path, description=None):
        """Add a resource for the AI handler to use"""
        if not self.ai_handler:
            raise Exception("AI handler not initialized. Please start the bot first.")
        return await self.ai_handler.add_resource(resource_path, description)
    
    def get_resources(self):
        """Get list of resources available to the bot"""
        if not self.ai_handler:
            return []
        return self.ai_handler.document_handler.get_resources() if hasattr(self.ai_handler, 'document_handler') else []
    
    def get_session_analytics(self):
        """Get analytics about the current session"""
        if not self.ai_handler:
            return {"status": "Bot not initialized", "total_responses": 0}
        return self.ai_handler.get_session_analytics()
    
    def set_learning_enabled(self, enabled=True):
        """Enable or disable learning"""
        self.learning_enabled = enabled
        
        # Update AI handler if already initialized
        if self.ai_handler and hasattr(self.ai_handler, 'set_learning_enabled'):
            self.ai_handler.set_learning_enabled(enabled)
    
    def learn_from_past_logs(self):
        """Learn from past conversation logs"""
        if not self.ai_handler:
            return 0
        return self.ai_handler.learn_from_past_logs()
    
    def get_learning_stats(self):
        """Get statistics about what has been learned"""
        return self.ai_handler.get_learning_stats()