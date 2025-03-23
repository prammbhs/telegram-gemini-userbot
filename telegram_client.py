import asyncio
import random
import time
# Defer TelegramClient import until we need it
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import Channel, User, Chat
import config

class TelegramUserbot:
    def __init__(self, super_context, target_group, duration, user_id=None):
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
        
    async def _check_chat_type(self):
        """Determine if we're in a group chat or individual conversation"""
        try:
            entity = await self.client.get_entity(self.target_group)
            
            if isinstance(entity, User):
                self.is_group_chat = False
                print(f"Connected to individual chat with {entity.first_name}")
                return False
            elif isinstance(entity, (Channel, Chat)):
                self.is_group_chat = True
                print(f"Connected to group chat: {entity.title}")
                return True
            else:
                # Default to group chat behavior if unknown
                self.is_group_chat = True
                print("Connected to unknown chat type, assuming group")
                return True
                
        except Exception as e:
            print(f"Error determining chat type: {e}")
            # Default to group chat behavior
            self.is_group_chat = True
            return True
    
    async def get_recent_messages(self, limit=config.MESSAGE_HISTORY_LIMIT):
        """Get recent messages from the group for context"""
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
            # Only include messages from the current session if we have a session start time
            if self.session_start_timestamp and message.date.timestamp() < self.session_start_timestamp:
                continue
                
            if message.message:
                try:
                    if message.from_id:
                        sender = await self.client.get_entity(message.from_id)
                        messages.append(f"{sender.first_name}: {message.message}")
                    else:
                        # Handle case where from_id is None (like channel posts)
                        messages.append(f"Unknown User: {message.message}")
                except Exception as e:
                    # Handle any other errors when getting sender info
                    print(f"Error getting message sender: {e}")
                    messages.append(f"User: {message.message}")
        return messages
    
    async def send_ai_response(self, context, event=None):
        """Generate and send AI response with error handling"""
        try:
            # Skip if message is from before the session started
            if event and self.session_start_timestamp:
                if event.message.date.timestamp() < self.session_start_timestamp:
                    print(f"Ignoring message from before session start: {event.message.text}")
                    return
            
            # Pass the message ID to reply to if we have an event
            message_id_to_reply = event.message.id if event else None
            responses = await self.generate_ai_response(context, self.is_group_chat, message_id_to_reply)
            
            if not responses:
                return
                
            # Add initial delay to seem more human-like
            initial_delay = random.uniform(40, 60)  # Between 40-60 seconds
            print(f"Waiting for {initial_delay:.1f} seconds before responding...")
            await asyncio.sleep(initial_delay)
            
            # Check if the response is the new dictionary format
            # If not, convert it to be backward compatible
            if isinstance(responses, dict):
                messages = responses.get("messages", [])
                should_reply = responses.get("should_reply", False)
            else:
                # Handle legacy format where responses was just a list
                messages = responses
                should_reply = False
            
            # Send each part of the response with a significant delay between them
            first_message = True
            for response in messages:
                # Only proceed if the bot is still running
                if not self.running:
                    break
                    
                # Decide if we should reply to the original message (only for the first message)
                reply_to = event.message.id if first_message and should_reply else None
                
                # Use try-except for sending messages
                try:
                    await self.client.send_message(
                        self.target_group, 
                        response,
                        reply_to=reply_to
                    )
                except Exception as e:
                    print(f"Error sending message: {e}")
                    # Don't stop if a single message fails, just log and continue
                    continue
                
                first_message = False
                
                # Add a delay between multiple message parts
                if len(messages) > 1 and response != messages[-1] and self.running:
                    typing_delay = random.uniform(45, 65)  # 45-65 seconds between messages
                    print(f"Waiting {typing_delay:.1f} seconds before next message part...")
                    await asyncio.sleep(typing_delay)
        except Exception as e:
            print(f"Error in send_ai_response: {e}")
    
    async def start(self):
        """Start the userbot"""
        # Import TelegramClient here to avoid premature event loop access
        from telethon import TelegramClient, events
        
        # Initialize the TelegramClient here instead of in __init__
        self.client = TelegramClient(
            self.config_instance.SESSION_FILE, 
            self.config_instance.API_ID, 
            self.config_instance.API_HASH
        )
        
        await self.client.start()
        print("Client Created")
        
        # Record the session start time
        self.session_start_timestamp = time.time()
        print(f"Session start timestamp: {self.session_start_timestamp}")
        
        # Determine if we're in a group chat
        await self._check_chat_type()
        
        self.running = True
        self.start_time = time.time()
        
        # Send initial message - with proper error handling
        initial_message = await self.generate_initial_message()
        
        # This is where the ChatWriteForbiddenError can occur
        try:
            await self.client.send_message(self.target_group, initial_message)
        except Exception as e:
            self.running = False
            # Re-raise the exception to be handled by the calling function
            raise e
        
        # Set up message handler
        @self.client.on(events.NewMessage(chats=self.target_group))
        async def message_handler(event):
            if not self.running:
                return
                
            # Check if duration has elapsed
            if time.time() - self.start_time > self.duration:
                self.running = False
                print("Session duration ended")
                return
                
            # Skip messages from before session start
            if event.message.date.timestamp() < self.session_start_timestamp:
                print(f"Skipping message from before session start")
                return
                
            # Don't respond to own messages
            if event.message.out:
                return
                
            # Get recent messages for context
            recent_messages = await self.get_recent_messages()
            
            # Pass the event to allow for direct replies
            await self.send_ai_response(recent_messages, event)
        
        # Keep the client running
        print(f"Bot running in {self.target_group} for {self.duration/60:.1f} minutes")
        while self.running:
            await asyncio.sleep(1)
        
        await self.stop()
    
    async def stop(self):
        """Stop the userbot safely with error handling"""
        self.running = False
        try:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                print("Bot disconnected")
        except Exception as e:
            print(f"Error disconnecting client: {e}")
        finally:
            print("Bot stopped")
            self.client = None  # Reset client to None