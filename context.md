Telegram Userbot for Automated Group Chatting

Overview

This project implements a Telegram userbot that can chat in a group using Google Gemini AI. The bot will use your personal Telegram account (not a bot account) to send messages based on chat context and a predefined topic (Super Context). The bot operates for a limited duration and then stops automatically.

Features

Uses your Telegram account to chat in a group.

Reads recent messages from the group to understand the context.

Uses Google Gemini AI to generate meaningful, human-like responses.

Operates for a set duration before stopping.

Allows defining a Super Context, such as discussing a specific topic (e.g., "Talk about Crypto for 30 minutes").

Posts an initial message introducing the topic.

Takes references from ongoing group conversations to enhance responses.

Free to use with cloud hosting or local execution.

How It Works

The user logs in using their Telegram account via the Telethon library.

The script listens for new messages in a specified Telegram group.

The user sets a Super Context (e.g., "Discuss the latest trends in AI").

The bot posts an initial message related to the Super Context.

When a message is detected, it is sent to Google Gemini AI for processing.

The AI-generated response is posted back into the group from the user’s account.

The bot stops automatically after the specified duration.

Use Cases

Themed discussions: Initiate topic-based conversations.

Automated group participation: Helps keep conversations active.

AI-powered discussions: Uses AI to respond intelligently while staying on topic.

Hands-free engagement: The bot runs for a defined time and stops automatically.

Limitations

Requires your Telegram API credentials.

Gemini API usage is subject to free-tier limits.

Needs a stable internet connection for real-time responses.

Security Considerations

Your Telegram session is stored locally and should be protected.

Avoid sharing API credentials publicly.

Use a secondary Telegram account if privacy is a concern.

