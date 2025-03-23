import asyncio
import os
import json
from telegram_client import TelegramUserbot
from ai_handler import GeminiAI
import time
import config

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
    
    async def start(self):
        """Start the userbot"""
        # Flag that we're running
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
            
            # 3. Start Telegram client
            await self.telegram_client.start()
            
        except Exception as e:
            self._is_running = False
            print(f"Error starting GeminiUserbot: {e}")
            raise
    
    async def stop(self):
        """Stop the userbot"""
        self._is_running = False
        
        # Stop the Telegram client
        if self.telegram_client:
            await self.telegram_client.stop()
        
        # Save AI session logs if enabled
        if self.ai_handler and self.learning_enabled:
            try:
                self.ai_handler.save_session_log()
            except Exception as e:
                print(f"Error saving AI session log: {e}")
    
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