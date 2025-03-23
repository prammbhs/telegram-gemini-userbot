import asyncio
import os
import json
from telegram_client import TelegramUserbot
from ai_handler import GeminiAI
import time

class GeminiUserbot:
    def __init__(self, super_context, target_group, duration=30, user_id=None):
        self.super_context = super_context
        self.target_group = target_group
        self.duration = duration
        self.user_id = user_id
        
        # Pass user_id to telegram client for proper session management
        self.telegram_client = TelegramUserbot(super_context, target_group, duration, user_id)
        
        # Get dynamic config for this user
        config_instance = config.DynamicConfig(user_id)
        
        # Initialize AI with user-specific API key
        self.ai = GeminiAI(super_context, api_key=config_instance.GEMINI_API_KEY)
        
        self.start_time = None
        
        # Connect the components with updated method bindings
        self.telegram_client.generate_ai_response = self.generate_ai_response
        self.telegram_client.generate_initial_message = self.generate_initial_message
    
    async def generate_ai_response(self, context, is_group_chat=True, message_id_to_reply=None):
        """Generate AI response and pass chat type information"""
        return await self.ai.generate_response(context, is_group_chat, message_id_to_reply)
    
    async def generate_initial_message(self):
        """Generate initial message with chat type awareness"""
        # Get the chat type from the Telegram client
        is_group_chat = self.telegram_client.is_group_chat
        return await self.ai.generate_initial_message(is_group_chat)
    
    async def start(self):
        """Start the userbot"""
        self.start_time = time.time()
        await self.telegram_client.start()
    
    async def stop(self):
        """Stop the userbot"""
        try:
            # Save session responses before stopping
            log_file = self.ai.save_session_log()
            print(f"Session responses saved to {log_file}")
            
            # Get and print session analytics
            analytics = self.get_session_analytics()
            print("\n===== SESSION ANALYTICS =====")
            for key, value in analytics.items():
                if key == 'response_types' or key == 'top_topics':
                    print(f"{key}: {value}")
                else:
                    print(f"{key}: {value}")
            print("============================\n")
            
            # Reset memory
            self.ai.message_fingerprints.clear()
            self.ai.question_history.clear()
            self.ai.greeting_counts.clear()
            self.ai.topic_history = [self.super_context]
        except Exception as e:
            print(f"Error during analytics processing: {e}")
        
        # Always stop the telegram client
        await self.telegram_client.stop()
    
    async def add_resource(self, resource_path, description=None):
        """Add a resource file or URL to be used for answering questions"""
        try:
            result = await self.ai.add_resource(resource_path, description)
            return True, result
        except Exception as e:
            return False, str(e)
    
    def get_resources(self):
        """Get list of all added resources"""
        return self.ai.get_resources()
    
    def get_session_analytics(self):
        """Get analytics about the current session"""
        analytics = self.ai.get_session_analytics()
        
        # Add default values for any missing keys
        default_analytics = {
            'session_duration_minutes': 0,
            'total_responses': 0,
            'average_words_per_response': 0,
            'emoji_usage_percentage': 0,
            'unique_users_engaged': 0,
            'response_types': {},
            'top_topics': [],
            'users': []
        }
        
        # Calculate session duration
        if self.start_time:
            elapsed_seconds = time.time() - self.start_time
            default_analytics['session_duration_minutes'] = round(elapsed_seconds / 60, 1)
        
        # Merge default with actual analytics, ensuring all keys exist
        for key, value in default_analytics.items():
            if key not in analytics:
                analytics[key] = value
                
        return analytics
    
    def set_learning_enabled(self, enabled=True):
        """Enable or disable learning from past responses"""
        self.ai.use_learning = enabled
    
    def learn_from_past_logs(self):
        """Process all previous logs to learn response patterns"""
        return self.ai.learn_from_past_logs()
    
    def get_learning_stats(self):
        """Get statistics about what has been learned"""
        return self.ai.get_learning_stats()