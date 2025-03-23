import os
import config
import time
import random
import asyncio
import logging
import platform
import socket
from telethon import TelegramClient, events, connection
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import Channel, User, Chat
from telethon.sessions import StringSession, SQLiteSession

# Configure logging
logger = logging.getLogger('TelegramUserbot')

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
        self.session_path = self.config_instance.SESSION_FILE
        session_dir = os.path.dirname(self.session_path)
        os.makedirs(session_dir, exist_ok=True)
        
        # Check if session file exists
        self.session_file_exists = os.path.exists(f"{self.config_instance.SESSION_FILE}.session")
        
        # Get API credentials
        self.api_id = int(self.config_instance.TELEGRAM_API_ID)
        self.api_hash = self.config_instance.TELEGRAM_API_HASH
        
        # Set up better connection parameters for Windows systems
        self.connection_retries = 8  # Increased from 5
        self.retry_delay = 2        # Increased from 1
        self.force_tcp = False      # Will be set based on OS detection
        
        # Track the connection status
        self.connection_errors = 0
        self.max_connection_errors = 15
        self.last_connection_time = time.time()
        
        # Simplify platform detection
        self.is_windows = 'Windows' in platform.system()
        
        # For cloud deployment, always use the most reliable connection type
        if not self.is_windows:
            # On Linux (cloud), just use the standard connection type
            self.connection_types = [connection.ConnectionTcpFull]
            self.current_connection_type = 0
        else:
            # Set low-level socket options to help prevent WinError 64
            if self.is_windows:
                # We'll try multiple connection types
                self.connection_types = [
                    connection.ConnectionTcpMTProxyRandomizedIntermediate,
                    connection.ConnectionTcpFull,
                    connection.ConnectionTcpObfuscated,
                    connection.ConnectionTcpIntermediate
                ]
                self.current_connection_type = 0
            else:
                # Use the default for other platforms
                self.connection_types = [connection.ConnectionTcpFull]
                self.current_connection_type = 0
    
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
    
    async def get_recent_messages(self, limit=20):
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
    
    async def _post_initial_message(self):
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
    
    async def check_and_clean_sessions(self):
        """Check for existing sessions and clean them if necessary"""
        import os
        import glob
        
        try:
            # Get the session file path without the .session extension
            session_dir = os.path.dirname(self.session_path)
            session_name = os.path.basename(self.session_path)
            
            # Look for any session files that might be corrupted
            session_files = glob.glob(f"{session_dir}/{session_name}.*")
            
            if session_files:
                logger.info(f"Found {len(session_files)} existing session files. Cleaning up...")
                for file in session_files:
                    try:
                        # Only remove files that might be causing issues (.tmp files, etc.)
                        if not file.endswith('.session') and ('.tmp' in file or '.old' in file):
                            logger.info(f"Removing potentially corrupted session file: {file}")
                            os.remove(file)
                    except Exception as e:
                        logger.warning(f"Failed to remove session file {file}: {e}")
                        
            # Check for .session-journal files which can cause issues
            journal_files = glob.glob(f"{session_dir}/{session_name}.session-journal")
            if journal_files:
                for file in journal_files:
                    try:
                        logger.info(f"Removing journal file: {file}")
                        os.remove(file)
                    except Exception as e:
                        logger.warning(f"Failed to remove journal file {file}: {e}")
                        
            return True
        except Exception as e:
            logger.error(f"Error cleaning sessions: {e}")
            return False

    def configure_sockets_for_windows(self):
        """Configure socket parameters to improve stability on Windows"""
        if self.is_windows:
            try:
                # Attempt to increase socket stability
                socket.setdefaulttimeout(30)  # 30 second timeout
                
                # Check if Windows firewall may be blocking connections
                if self.is_windows_firewall_blocking_telegram():
                    logger.warning("Windows Firewall may be blocking Telegram connections!")
                    logger.warning("Consider adding telethon/python to your firewall exceptions.")
                
                return True
            except Exception as e:
                logger.error(f"Failed to configure Windows socket parameters: {e}")
                return False
        return True
    
    def is_windows_firewall_blocking_telegram(self):
        """Check if Windows Firewall might be blocking Telegram connections"""
        if not self.is_windows:
            return False
            
        try:
            # Try to connect directly to Telegram API
            telegram_servers = [
                ("149.154.167.50", 443),  # Telegram DC1
                ("149.154.167.91", 443)   # Telegram DC5
            ]
            
            for server, port in telegram_servers:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(3)
                    s.connect((server, port))
                    s.close()
                    return False  # If successful, firewall is not blocking
                except (socket.timeout, socket.error):
                    continue
                    
            return True  # If all connections failed, firewall might be blocking
        except Exception:
            return True  # Assume blocked on error

    async def create_client_with_connection_type(self, idx):
        """Create a client with a specific connection type"""
        conn_type = self.connection_types[idx]
        logger.info(f"Trying connection type: {conn_type.__name__}")
        
        try:
            # Use string session for better stability
            string_session = StringSession()
            
            # Create client with the specified connection type
            client = TelegramClient(
                string_session,
                self.api_id,
                self.api_hash,
                connection=conn_type,
                connection_retries=self.connection_retries,
                retry_delay=self.retry_delay,
                auto_reconnect=True,
                flood_sleep_threshold=60
            )
            
            # Set timeout for better handling of WinError 64 issues
            client.flood_sleep_threshold = 60
            
            return client
        except Exception as e:
            logger.error(f"Error creating client with {conn_type.__name__}: {e}")
            return None

    async def start(self):
        """Start the userbot with improved error handling for WinError 64 issues"""
        # Clean up any corrupted session files
        await self.check_and_clean_sessions()
        
        # Configure socket parameters for Windows
        self.configure_sockets_for_windows()
        
        # Try starting with different connection types if on Windows
        connection_attempts = 0
        max_connection_attempts = len(self.connection_types) if self.is_windows else 1
        
        while connection_attempts < max_connection_attempts:
            try:
                # Create client with current connection type
                if self.is_windows:
                    self.client = await self.create_client_with_connection_type(
                        self.current_connection_type % len(self.connection_types)
                    )
                else:
                    # Standard client creation for non-Windows
                    self.client = TelegramClient(
                        self.session_path,
                        self.api_id,
                        self.api_hash,
                        connection_retries=self.connection_retries,
                        retry_delay=self.retry_delay,
                        auto_reconnect=True
                    )
                
                if not self.client:
                    raise ConnectionError(f"Failed to create client with connection type {self.current_connection_type}")
                
                # Add handlers
                self.client.add_event_handler(
                    self.message_handler,
                    events.NewMessage(chats=self.target_group)
                )
                
                # Connect with a timeout
                try:
                    # Use the recommended approach for Windows to connect
                    if self.is_windows:
                        logger.info("Using special Windows connection approach...")
                        # Set a timeout for connection
                        await asyncio.wait_for(self.client.connect(), timeout=45)
                    else:
                        await self.client.connect()
                    
                    # If we got here, connection succeeded
                    if await self.client.is_user_authorized():
                        logger.info("Successfully connected and authorized!")
                        self.running = True
                        self.session_start_timestamp = datetime.now()
                        
                        # Check chat type
                        await self._check_chat_type()
                        
                        # Send initial message
                        await self._post_initial_message()
                        
                        # Schedule stop
                        asyncio.create_task(self._schedule_stop())
                        
                        # Reset connection errors counter
                        self.connection_errors = 0
                        
                        # Keep client running
                        return
                    else:
                        raise ConnectionError("User is not authorized. Please verify Telegram credentials.")
                except asyncio.TimeoutError:
                    logger.error(f"Connection attempt {connection_attempts+1} timed out")
                except asyncio.CancelledError:
                    logger.error(f"Connection was cancelled during attempt {connection_attempts+1}")
                    # Try a different connection type for Windows
                    if self.is_windows:
                        self.current_connection_type += 1
                except Exception as e:
                    logger.error(f"Error during connection: {str(e)}")
                
                # If we reach here, connection failed, increment attempts and try again
                connection_attempts += 1
                
                # If we've exceeded max error count, raise an exception
                if self.connection_errors >= self.max_connection_errors:
                    raise ConnectionError(
                        f"Too many connection errors ({self.connection_errors}). "
                        f"Telegram servers might be blocked by your network or firewall."
                    )
                
                # Wait before retrying (with increasing delay)
                retry_wait = 5 + connection_attempts * 3
                logger.info(f"Connection failed. Waiting {retry_wait}s before retrying...")
                await asyncio.sleep(retry_wait)
                
            except Exception as e:
                logger.error(f"Error starting Telegram client: {str(e)}")
                connection_attempts += 1
                
                if connection_attempts >= max_connection_attempts:
                    # We've tried all connection types, raise the error
                    if self.is_windows:
                        # Provide Windows-specific guidance
                        error_msg = (
                            f"Failed to connect to Telegram after trying {max_connection_attempts} different connection types. "
                            f"This could be due to Windows Firewall, antivirus, or network issues. "
                            f"Please check your firewall settings and ensure python.exe is allowed to connect to the internet."
                        )
                    else:
                        error_msg = f"Failed to connect to Telegram after {max_connection_attempts} attempts: {str(e)}"
                    
                    raise ConnectionError(error_msg)
                
                # Try the next connection type
                if self.is_windows:
                    self.current_connection_type += 1
                    
                # Wait before trying again
                await asyncio.sleep(connection_attempts * 3)
        
        # If we get here without returning, it means we couldn't connect
        raise ConnectionError("Failed to establish a connection to Telegram servers after all attempts")
    
    async def message_handler(self, event):
        """Handle incoming messages"""
        try:
            # Skip messages from ourselves
            if event.from_id == 'me':
                return
                
            # Skip messages older than our start time
            if self.session_start_timestamp and event.date < self.session_start_timestamp:
                return
            
            # Get message text
            message_text = event.message.text
            if not message_text:
                return  # Skip empty or non-text messages
            
            # Get recent messages for context
            recent_messages = await self.get_recent_messages()
            
            # Prepare context for AI
            context = {
                'message': message_text,
                'recent_messages': recent_messages,
                'is_group_chat': self.is_group_chat
            }
            
            # Generate and send response
            await self.send_ai_response(context, event)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _schedule_stop(self):
        """Schedule the bot to stop after the specified duration"""
        self.start_time = time.time()
        
        # Keep running until duration expires
        while self.running and (time.time() - self.start_time < self.duration):
            await asyncio.sleep(5)  # Check every 5 seconds
            
            # Check if connection is still valid
            if self.client and not self.client.is_connected():
                logger.warning("Connection lost, attempting to reconnect...")
                try:
                    await self.client.connect()
                except Exception as e:
                    logger.error(f"Reconnection failed: {e}")
                    
        # Stop the bot after duration
        if self.running:
            logger.info(f"Bot session duration ({self.duration/60:.1f} minutes) completed")
            self.running = False
            await self.stop()
    
    async def stop(self):
        """Stop the Telegram client with improved cleanup"""
        self.running = False
        
        # Disconnect client if it exists
        if self.client:
            try:
                # Proper disconnection sequence
                if self.client.is_connected():
                    logger.info("Properly disconnecting client...")
                    await self.client.disconnect()
                else:
                    logger.info("Client already disconnected")
                    
                # Cleanup
                self.client = None
            except Exception as e:
                logger.error(f"Error disconnecting Telegram client: {e}")