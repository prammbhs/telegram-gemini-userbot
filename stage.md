# Telegram Userbot Development Guide

## Stage 1: Environment Setup

### Requirements
- Python 3.8+ installed
- Internet connection
- Telegram account
- Google account (for Gemini API)

### Setup Steps
1. Create a project directory
   ```bash
   mkdir telegram-gemini-userbot
   cd telegram-gemini-userbot
   ```

2. Set up a virtual environment
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install required libraries
   ```bash
   pip install telethon google-generativeai python-dotenv customtkinter pillow
   ```

## Stage 2: Obtaining API Credentials

### Telegram API Credentials
1. Visit https://my.telegram.org/auth
2. Log in with your phone number
3. Go to 'API development tools'
4. Create a new application (any name/description)
5. Note down the `api_id` and `api_hash`

### Google Gemini API
1. Visit https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Create a new API key
4. Copy the API key

## Stage 3: Basic Configuration

1. Create an environment file to store credentials
   ```python
   # .env
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   GEMINI_API_KEY=your_gemini_api_key
   ```

2. Create a config file
   ```python
   # config.py
   import os
   from dotenv import load_dotenv

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
   ```

## Stage 4: Core Functionality Development

### 1. Telegram Client Setup
Create a file for the Telegram client:

```python
# telegram_client.py
import asyncio
import random
import time
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
import config

class TelegramUserbot:
    def __init__(self, super_context, target_group, duration):
        self.client = TelegramClient('session_name', config.API_ID, config.API_HASH)
        self.super_context = super_context
        self.target_group = target_group
        self.duration = duration * 60  # Convert to seconds
        self.start_time = None
        self.running = False
    
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
            if message.message:
                sender = await self.client.get_entity(message.from_id)
                messages.append(f"{sender.first_name}: {message.message}")
        return messages
    
    async def send_ai_response(self, context):
        """Generate and send AI response"""
        response = await self.generate_ai_response(context)
        if response:
            # Add random delay to seem more human-like
            delay = random.uniform(config.RESPONSE_DELAY_MIN, config.RESPONSE_DELAY_MAX)
            await asyncio.sleep(delay)
            await self.client.send_message(self.target_group, response)
    
    async def start(self):
        """Start the userbot"""
        await self.client.start()
        print("Client Created")
        
        self.running = True
        self.start_time = time.time()
        
        # Send initial message
        initial_message = await self.generate_initial_message()
        await self.client.send_message(self.target_group, initial_message)
        
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
                
            # Don't respond to own messages
            if event.message.out:
                return
                
            # Get recent messages for context
            recent_messages = await self.get_recent_messages()
            await self.send_ai_response(recent_messages)
        
        print(f"Bot running in {self.target_group} for {self.duration/60} minutes")
        
        # Keep the bot running
        while self.running and (time.time() - self.start_time <= self.duration):
            await asyncio.sleep(1)
            
        print("Bot stopped")
        
    async def stop(self):
        """Stop the userbot"""
        self.running = False
        await self.client.disconnect()
        print("Bot disconnected")
```

### 2. AI Integration with Gemini
Create a file for AI interaction:

```python
# ai_handler.py
import google.generativeai as genai
import config

class GeminiAI:
    def __init__(self, super_context):
        self.super_context = super_context
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
    
    async def generate_initial_message(self):
        """Generate an initial message based on the super context"""
        prompt = f"""
        I need to start a conversation in a Telegram group about the following topic:
        {self.super_context}
        
        Generate a friendly, engaging opening message to introduce this topic to the group.
        Keep it conversational, interesting, and not too long (2-3 sentences maximum).
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error generating initial message: {e}")
            return f"Hey everyone! Let's talk about {self.super_context} today. What are your thoughts on this?"
    
    async def generate_response(self, message_history):
        """Generate a response based on chat history and super context"""
        chat_context = "\n".join(message_history)
        
        prompt = f"""
        You are participating in a Telegram group chat.
        
        Super Context: {self.super_context}
        
        Recent chat history:
        {chat_context}
        
        Generate a natural, conversational response as if you are a regular group member.
        Keep responses relatively short (1-3 sentences), casual, and engaging.
        Stay on the topic defined in the Super Context, but respond naturally to the flow of conversation.
        Don't introduce yourself as an AI or mention that you're generating responses.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error generating response: {e}")
            return None
```

### 3. Connecting Components
Create the main integration file:

```python
# userbot.py
import asyncio
from telegram_client import TelegramUserbot
from ai_handler import GeminiAI

class GeminiUserbot:
    def __init__(self, super_context, target_group, duration=30):
        self.super_context = super_context
        self.target_group = target_group
        self.duration = duration
        self.telegram_client = TelegramUserbot(super_context, target_group, duration)
        self.ai = GeminiAI(super_context)
        
        # Connect the components
        self.telegram_client.generate_ai_response = self.ai.generate_response
        self.telegram_client.generate_initial_message = self.ai.generate_initial_message
    
    async def start(self):
        """Start the userbot"""
        await self.telegram_client.start()
    
    async def stop(self):
        """Stop the userbot"""
        await self.telegram_client.stop()
```

## Stage 5: Building the UI

Create a simple GUI using CustomTkinter:

```python
# app.py
import customtkinter as ctk
import asyncio
import threading
from userbot import GeminiUserbot

# Configure appearance
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class UserbotApp:
    def __init__(self):
        self.app = ctk.CTk()
        self.app.title("Telegram Gemini Userbot")
        self.app.geometry("500x600")
        self.app.resizable(True, True)
        
        self.userbot = None
        self.userbot_thread = None
        
        self.setup_ui()
    
    def setup_ui(self):
        # Create frames
        self.header_frame = ctk.CTkFrame(self.app)
        self.header_frame.pack(fill="x", padx=10, pady=10)
        
        self.main_frame = ctk.CTkFrame(self.app)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.footer_frame = ctk.CTkFrame(self.app)
        self.footer_frame.pack(fill="x", padx=10, pady=10)
        
        # Header with title
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="Telegram Gemini AI Userbot", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(pady=10)
        
        # Main content
        # Group ID input
        self.group_frame = ctk.CTkFrame(self.main_frame)
        self.group_frame.pack(fill="x", pady=10)
        
        self.group_label = ctk.CTkLabel(self.group_frame, text="Target Group Username/ID:")
        self.group_label.pack(anchor="w", padx=10, pady=5)
        
        self.group_entry = ctk.CTkEntry(self.group_frame, width=400)
        self.group_entry.pack(padx=10, pady=5, fill="x")
        self.group_entry.insert(0, "@group_username")
        
        # Super Context input
        self.context_frame = ctk.CTkFrame(self.main_frame)
        self.context_frame.pack(fill="x", pady=10)
        
        self.context_label = ctk.CTkLabel(self.context_frame, text="Super Context (Topic):")
        self.context_label.pack(anchor="w", padx=10, pady=5)
        
        self.context_text = ctk.CTkTextbox(self.context_frame, height=100)
        self.context_text.pack(padx=10, pady=5, fill="x")
        self.context_text.insert("1.0", "Discuss the latest trends in AI technology")
        
        # Duration input
        self.duration_frame = ctk.CTkFrame(self.main_frame)
        self.duration_frame.pack(fill="x", pady=10)
        
        self.duration_label = ctk.CTkLabel(self.duration_frame, text="Duration (minutes):")
        self.duration_label.pack(anchor="w", padx=10, pady=5)
        
        self.duration_slider = ctk.CTkSlider(
            self.duration_frame, 
            from_=5, 
            to=60,
            number_of_steps=11,
            command=self.update_duration_label
        )
        self.duration_slider.pack(padx=10, pady=5, fill="x")
        self.duration_slider.set(30)
        
        self.duration_value_label = ctk.CTkLabel(self.duration_frame, text="30 minutes")
        self.duration_value_label.pack(padx=10, pady=5)
        
        # Status display
        self.status_frame = ctk.CTkFrame(self.main_frame)
        self.status_frame.pack(fill="x", pady=10)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame, 
            text="Status: Not running",
            font=ctk.CTkFont(weight="bold")
        )
        self.status_label.pack(padx=10, pady=10)
        
        # Log display
        self.log_frame = ctk.CTkFrame(self.main_frame)
        self.log_frame.pack(fill="both", expand=True, pady=10)
        
        self.log_label = ctk.CTkLabel(self.log_frame, text="Activity Log:")
        self.log_label.pack(anchor="w", padx=10, pady=5)
        
        self.log_text = ctk.CTkTextbox(self.log_frame, state="disabled", height=150)
        self.log_text.pack(padx=10, pady=5, fill="both", expand=True)
        
        # Control buttons
        self.start_button = ctk.CTkButton(
            self.footer_frame, 
            text="Start Bot", 
            command=self.start_bot,
            fg_color="green"
        )
        self.start_button.pack(side="left", padx=10, pady=10)
        
        self.stop_button = ctk.CTkButton(
            self.footer_frame, 
            text="Stop Bot", 
            command=self.stop_bot,
            fg_color="red",
            state="disabled"
        )
        self.stop_button.pack(side="right", padx=10, pady=10)
    
    def update_duration_label(self, value):
        """Update the duration label when slider moves"""
        minutes = int(value)
        self.duration_value_label.configure(text=f"{minutes} minutes")
    
    def log_message(self, message):
        """Add a message to the log display"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    
    def start_bot(self):
        """Start the userbot"""
        group = self.group_entry.get().strip()
        context = self.context_text.get("1.0", "end").strip()
        duration = int(self.duration_slider.get())
        
        if not group or not context:
            self.log_message("Error: Please fill in all fields")
            return
        
        self.log_message(f"Starting bot in group: {group}")
        self.log_message(f"Super Context: {context}")
        self.log_message(f"Duration: {duration} minutes")
        
        # Update UI
        self.status_label.configure(text="Status: Running")