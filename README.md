# Telegram Gemini Bot

A web application that allows users to create and manage AI-powered bots that run on their personal Telegram accounts. These bots use Google's Gemini AI to engage in natural conversations in Telegram groups or direct messages.

## Features

- **Telegram User Bot**: Operate a bot using your personal Telegram account (not a bot account)
- **AI-Powered Conversations**: Leverage Google Gemini AI for intelligent, context-aware responses
- **Multiple Bots**: Create and manage multiple bots with different personalities and target groups
- **Learning Capability**: Bots can learn from past conversations to improve future responses
- **Free API Credits**: Start with free Gemini API credits before adding your own API key
- **Analytics Dashboard**: Track performance with comprehensive analytics
- **Secure Authentication**: Login with email, Google, or GitHub
- **Dark Mode Support**: Toggle between light and dark themes

## Getting Started

### Prerequisites

- Python 3.8+
- MongoDB server or MongoDB Atlas account
- Telegram account
- Google Gemini API key (free tier available)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/prammbhs/telegram-gemini-userbot.git
   cd telegram-gemini-bot
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables in a `.env` file:
   ```
   # Telegram API credentials (app-level)
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   
   # Google Gemini API Key (app-level or free tier)
   GEMINI_API_KEY=your_gemini_api_key
   
   # Flask settings
   SECRET_KEY=your_secret_key
   FLASK_APP=web_app.py
   
   # MongoDB settings
   MONGO_URI=your_mongodb_uri
   
   # Optional OAuth settings
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   GITHUB_CLIENT_ID=your_github_client_id
   GITHUB_CLIENT_SECRET=your_github_client_secret
   ```

5. Run the application:
   ```bash
   python web_app.py
   ```

### Setting Up Telegram API Credentials

This application uses a centralized set of Telegram API credentials. To get your own:

1. Visit [my.telegram.org/apps](https://my.telegram.org/apps)
2. Log in with your phone number
3. Create a new application
4. Note down the `App api_id` and `App api_hash`
5. Add these to your `.env` file

### Getting a Google Gemini API Key

1. Visit [Google AI Studio](https://ai.google.dev/)
2. Sign in with your Google account
3. Navigate to the API Keys section
4. Create a new API key
5. Add it to your `.env` file or input it in the application

## Usage

### Creating a Bot

1. After logging in, go to the Dashboard
2. Click "Create New Bot"
3. Fill in the details:
   - Bot Name: A name for your bot
   - Target Group: The Telegram group or username where the bot will operate
   - Context: Define the bot's personality, knowledge, and behavior
   - Duration: How long the bot should run
   - Learning: Enable/disable learning from conversations

### Verifying Your Telegram Account

1. Go to your Profile
2. Click "Verify Telegram"
3. Enter your phone number
4. Input the verification code sent to your Telegram app
5. Your account is now ready to use with bots

### Managing API Keys

1. Go to your Profile
2. Click "Manage API Keys"
3. Add or remove API keys for different services
4. Set a default API key

## Architecture

The application uses:
- Flask for the web framework
- MongoDB for data storage
- Telethon for Telegram interaction
- Google Generative AI for the Gemini integration
- Flask-Login for authentication
- Authlib for OAuth integration

## Development

### Project Structure

