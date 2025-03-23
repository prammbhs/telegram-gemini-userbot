import os
import config
import time
import random
import asyncio
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import Channel, User, Chat
from telethon import TelegramClient, events

class TelegramUserbot:
    def __init__(self, super_context, target_group, duration, user_id=None, parent_bot=None):
        # Get dynamic config for this user
        self.config_instance = config.DynamicConfig(user_id)
        
        # Store parameters but don't create client yet - we'll do this in start()
        self.super_context = super_context
        self.target_group = target_group
        self.duration = duration * 60  # Convert to seconds
        self.user_id = user_id
        self.start_time = None
        self.running = False
        self.session_start_timestamp = None
        self.is_group_chat = None  # Will be set during connection
        self.client = None  # We'll initialize this in the start method
        
        # Store reference to parent bot to access AI handler
        self.parent_bot = parent_bot
        
        # Ensure session directory exists
        session_path = os.path.dirname(self.config_instance.SESSION_FILE)
        os.makedirs(session_path, exist_ok=True)
        
        # Check if session file exists
        self.session_file_exists = os.path.exists(f"{self.config_instance.SESSION_FILE}.session")
    
    async def _check_chat_type(self):
        """Determine if we're in a group chat or individual conversation"""
        try:
            entity = await self.client.get_entity(self.target_group)
            self.is_group_chat = isinstance(entity, (Channel, Chat))
            if not self.is_group_chat:
                print(f"Target {self.target_group} is a private conversation with {entity.first_name}")
            else:
                print(f"Target {self.target_group} is a group chat with {entity.title}")
                
            return self.is_group_chat
        except Exception as e:
            print(f"Error determining chat type: {e}")
            self.is_group_chat = True  # Default to group chat if we can't determine
            return self.is_group_chat
    
    async def get_recent_messages(self, limit=20):  # Increased from config.MESSAGE_HISTORY_LIMIT
        """Get recent messages from the group for context"""
        if not self.client:
            return []
            
        try:
            entity = await self.client.get_entity(self.target_group)
            history = await self.client(GetHistoryRequest(
                peer=entity,
                limit=limit,
                offset_date=None,
                offset_id=0,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0
            ))
            messages = []
            for message in reversed(history.messages):
                if message.message:
                    try:
                        sender = await self.client.get_entity(message.from_id) if message.from_id else None
                        sender_name = f"{sender.first_name}" if sender else "Unknown"
                        messages.append(f"{sender_name}: {message.message}")
                    except Exception as e:
                        print(f"Error getting sender: {e}")
                        messages.append(f"User: {message.message}")
            return messages
        except Exception as e:
            print(f"Error getting recent messages: {e}")
            return []
    
    async def send_ai_response(self, context, event=None):
        """Generate and send AI response with error handling"""
        try:
            # Check if parent bot exists and has AI handler
            if not self.parent_bot or not hasattr(self.parent_bot, 'ai_handler') or not self.parent_bot.ai_handler:
                print("AI handler not initialized yet. Cannot generate response.")
                return False
            
            # Generate response using the parent bot's AI handler
            message_id = event.id if event else None
            response_data = await self.parent_bot.generate_ai_response(
                context, 
                is_group_chat=self.is_group_chat,
                message_id_to_reply=message_id
            )
            
            # Send message(s)
            for message in response_data['messages']:
                # Add typing simulation
                async with self.client.action(self.target_group, 'typing'):
                    # Random delay to simulate human typing
                    delay = min(0.1 * len(message), 5.0)
                    await asyncio.sleep(delay)
                
                if response_data.get('should_reply') and event:
                    await event.reply(message)
                else:
                    await self.client.send_message(self.target_group, message)
                
                # Sleep between multiple messages
                if len(response_data['messages']) > 1:
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    
            return True
        except Exception as e:
            print(f"Error sending AI response: {e}")
            return False
    
    async def _send_initial_message(self):
        """Send an initial message to start the conversation"""
        try:
            # Make sure parent bot and AI handler are initialized
            if not self.parent_bot or not self.parent_bot.ai_handler:
                print("AI handler not initialized yet. Will skip initial message.")
                return False
            
            # Get initial message
            initial_message = await self.parent_bot.generate_initial_message()
            
            # Send initial message with typing simulation
            async with self.client.action(self.target_group, 'typing'):
                await asyncio.sleep(random.uniform(1.5, 3.0))
                await self.client.send_message(self.target_group, initial_message)
            
            print(f"Sent initial message: {initial_message}")
            return True
        except Exception as e:
            print(f"Error sending initial message: {e}")
            return False
    
    async def start(self):
        """Initialize and start the Telegram client"""
        try:
            # Create client
            api_id = self.config_instance.API_ID
            api_hash = self.config_instance.API_HASH
            
            print(f"Connecting to Telegram with API ID: {api_id}")
            
            # Create client
            self.client = TelegramClient(
                self.config_instance.SESSION_FILE,
                api_id,
                api_hash
            )
            
            # Connect to Telegram
            await self.client.connect()
            
            # Check authorization
            if not await self.client.is_user_authorized():
                raise Exception("Telegram authentication required. Please run the setup script first.")
            
            # Get target entity to validate
            entity = await self.client.get_entity(self.target_group)
            print(f"Successfully connected to {entity.title if hasattr(entity, 'title') else entity.first_name}")
            
            # Check if we're in a group or private chat
            await self._check_chat_type()
            
            # Mark as running
            self.running = True
            self.start_time = time.time()
            self.session_start_timestamp = self.start_time
            
            # Add message handler for all incoming messages
            @self.client.on(events.NewMessage(chats=self.target_group))
            async def message_handler(event):
                # Skip messages from ourselves
                me = await self.client.get_me()
                if event.sender_id == me.id:
                    return
                
                # Get recent messages for context
                recent_messages = await self.get_recent_messages()
                
                # Send to AI and respond
                await self.send_ai_response(recent_messages, event)
            
            # Wait for a short time to ensure client is fully connected before sending first message
            await asyncio.sleep(1.0)
            
            # Send initial message
            await self._send_initial_message()
            
            # Run the client until the duration expires or stopped
            end_time = self.start_time + self.duration
            while time.time() < end_time and self.running:
                # Add a small sleep to prevent tight loops
                await asyncio.sleep(1.0)
            
            # If we reached the end naturally
            if time.time() >= end_time and self.running:
                print(f"Bot duration ({self.duration/60} minutes) completed")
                self.running = False
            
        except Exception as e:
            print(f"Error in TelegramUserbot.start(): {e}")
            self.running = False
            raise
    
    async def stop(self):
        """Stop the Telegram client"""
        self.running = False
        
        # Disconnect client if it exists
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                print(f"Error disconnecting Telegram client: {e}")