import google.generativeai as genai
import config
import re
import random
import time
import hashlib
import json
import os
from datetime import datetime
from document_handler import DocumentHandler
import glob
import pickle
from collections import defaultdict, Counter
try:
    from db_handler import MongoDBHandler
    DB_HANDLER_AVAILABLE = True
except ImportError:
    DB_HANDLER_AVAILABLE = False

class GeminiAI:
    def __init__(self, super_context, api_key=None, user_id=None):
        self.super_context = super_context
        self.api_key_valid = False
        self.user_id = user_id
        
        # Use provided API key if available, otherwise fall back to config
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = config.GEMINI_API_KEY
        
        # Track if we're using the free tier API key
        self.using_free_tier = (self.api_key == config.FREE_TIER_API_KEY)
            
        # Validate API key before configuring
        if self._validate_api_key():
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.api_key_valid = True
        else:
            print(f"WARNING: Invalid Gemini API key - bot will use fallback responses")
            self.model = None
        
        # Extract name and role from super_context
        self.persona_name, self.persona_role = self._extract_persona_from_context(super_context)
        
        # Create document handler
        self.document_handler = DocumentHandler()
        
        # Create learning manager
        self.learning_manager = LearningManager()
        self.use_learning = True  # Toggle for learning feature
        
        # Response tracking for analytics
        self.response_log = []
        self.session_start_time = datetime.now()
        
        # Add missing last_responses attribute
        self.last_responses = []
        
        # Expanded emoji collection for more variety
        self.emojis = [
            # Positive/happy
            "😊", "👍", "😂", "🔥", "💯", "👏", "😁", "🤣", "😎", "🙂", "😉", "🤩",
            # Reactions/thinking
            "🤔", "👀", "😅", "🤨", "🧐", "😮", "😯", "🤷‍♂️", "🤷‍♀️", "👆", "💪",
            # Topical
            "💻", "🚀", "📱", "🤖", "💡", "⚡", "✨", "🌟", "💰", "📈", "🎯", "🔍",
            # Fun/trendy
            "💅", "🙌", "🫡", "🫠", "🤌", "✌️", "🫂", "🤝", "🙏", "🎉", "🔄",
            # Emphasis
            "❗", "❓", "⁉️", "‼️", "💭", "💬", "📢", "👇", "👈", "👉", "👋"
        ]
        
        # Enhanced conversation memory
        self.conversation_topic = super_context
        self.last_substantive_topic = super_context
        self.topic_change_threshold = 0.4
        self.last_topic_update_time = time.time()

        # Full session memory systems
        self.message_fingerprints = set()  # Track unique message fingerprints
        self.question_history = {}  # Track questions and their answers
        self.greeting_counts = {}  # Track how many times users have greeted
        self.topic_history = [super_context]  # Track topic evolution
        
        # Special keywords/patterns to recognize
        self.farewells = ["bye", "goodbye", "see ya", "cya", "gtg", "talk later", "good night", "night"]
        self.greetings = ["hi", "hello", "hey", "sup", "yo", "what's up", "morning", "afternoon", "evening"]
        self.empty_responses = ["cool", "nice", "great", "awesome", "thanks", "thank you", "ok", "okay", "good"]
        self.topic_starters = ["so,", "about", "speaking of", "regarding", "talking about", "on the topic of", "back to"]
        
        # Add signals for joke detection
        self.joke_signals = ["lol", "lmao", "haha", "😂", "🤣", "funny", "joke", "kidding", "jk"]
        self.agreement_signals = ["agree", "true", "right", "exactly", "correct", "yep", "yeah", "absolutely"]
        self.disagreement_signals = ["disagree", "nope", "nah", "not really", "incorrect", "wrong", "false"]

        self.hinglish_patterns = [
            # Greetings
            "kaise ho", "kaisa hai", "kya haal hai", "kya chal raha hai",
            "namaste", "namaskar", "kem cho", "kya scene hai", "kidhar ho",
            
            # Questions
            "kya kar rahe ho", "kahan se ho", "kya ho raha hai", "kya socha hai",
            "kitne saal", "kaunsi company", "kahan kaam", "kaise milega",
            
            # Common phrases
            "theek hai", "accha hai", "bura nahi", "haan ji", "nahi yaar",
            "bilkul", "ekdum", "zaroor", "pakka", "samajh gaya", "batao",
            
            # Tech-related
            "naukri", "job", "kaam", "paisa", "salary", "interview", "company"
        ]

    def _validate_api_key(self):
        """Validate the API key format and attempt a simple test call"""
        if not self.api_key or len(self.api_key) < 10:
            return False
            
        try:
            # Configure genai temporarily for validation
            genai.configure(api_key=self.api_key)
            
            # Try a simple generation with minimal tokens to validate the key
            test_model = genai.GenerativeModel('gemini-1.5-flash')
            response = test_model.generate_content("Hello")
            
            # If we get here, the key is valid
            return True
        except Exception as e:
            print(f"API key validation error: {e}")
            return False

    def _extract_persona_from_context(self, context):
        """Extract name and role from the super context"""
        # Default values
        name = "Assistant"
        role = "professional"
        
        if not context:
            return name, role
            
        # Try to extract name - common patterns like "You are [Name]" or "[Name] is a..."
        name_patterns = [
            r"(?:you are|i am) ([A-Z][a-z]+)",
            r"([A-Z][a-z]+)(?:,| is| as) (?:an?|the)",
            r"(?:as|by|from|with) ([A-Z][a-z]+)"
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, context, re.IGNORECASE)
            if matches and len(matches[0]) > 2:
                name = matches[0]
                break
                
        # Try to extract role - look for professional descriptions
        role_patterns = [
            r"(?:an?|the) ([a-z]+(?:\s[a-z]+){0,2}(?:specialist|professional|expert|consultant|manager|engineer|designer|developer|marketer|assistant|advisor))",
            r"(?:in|for|as) ([a-z]+(?:\s[a-z]+){0,2} (?:industry|field|sector|role|position))",
            r"(?:an?|the) ([a-z]+(?:\s[a-z]+){0,3})"
        ]
        
        for pattern in role_patterns:
            matches = re.findall(pattern, context, re.IGNORECASE)
            if matches and len(matches[0]) > 3:
                role = matches[0]
                break
                
        return name, role

    async def generate_initial_message(self, is_group_chat=True):
        """Generate an initial message based on the super context and chat type"""
        # Check if API key is valid before attempting to generate
        if not self.api_key_valid:
            print("Using fallback initial message due to invalid API key")
            if is_group_chat:
                return f"Hey! Thoughts on {self.super_context}? {random.choice(self.emojis)}"
            else:
                return f"Hey! I'm {self.persona_name}. Let's chat about {self.super_context}! {random.choice(self.emojis)}"
                
        # For direct messages, always start with a brief introduction
        if not is_group_chat:
            introduction_prompt = f"""
            I'm {self.persona_name}, {self.persona_role}.
            
            Create a brief, friendly introduction (2-3 sentences) that:
            1. Introduces myself as {self.persona_name}
            2. Mentions I'm {self.persona_role}
            3. Sounds casual and conversational
            4. Ends with a natural question to start the conversation about {self.super_context}
            
            Keep it under 25 words total and sound like a real person texting.
            """
            
            try:
                intro_response = self.model.generate_content(introduction_prompt)
                intro_message = intro_response.text.strip()
                
                # Add to history
                self.last_responses.append(intro_message.lower())
                
                # Add emoji
                if random.random() < 0.45 and not any(emoji in intro_message for emoji in self.emojis):
                    intro_message += f" {random.choice(self.emojis)}"
                    
                return intro_message
            except Exception as e:
                print(f"Error generating introduction: {e}")
                return f"Hey! I'm {self.persona_name}, {self.persona_role}. What do you think about the industry these days? {random.choice(self.emojis)}"
        
        # For group chats, use the existing logic
        prompt = f"""
        I need to start a very brief conversation in a {'Telegram group' if is_group_chat else 'one-on-one direct message'} about:
        {self.super_context}
        
        Generate an extremely short, casual opening message (MAXIMUM 7-8 words).
        Sound exactly like someone texting quickly on their phone.
        {'Don\'t use phrases like "Hey everyone" since this is a direct message with just one person.' if not is_group_chat else ''}
        Don't introduce the topic explicitly - just start naturally.
        """
        
        try:
            response = self.model.generate_content(prompt)
            message = response.text.strip()
            
            # Truncate if too long
            words = message.split()
            if len(words) > 8:
                message = " ".join(words[:8])
            
            # Remove group-oriented phrases in DMs
            if not is_group_chat and any(phrase in message.lower() for phrase in ["everyone", "guys", "all", "folks", "y'all", "people"]):
                # Replace with more personal greeting
                message = re.sub(r'(?i)hey\s+everyone|hi\s+guys|hello\s+all|hey\s+folks|hey\s+y\'all|hey\s+people', 'Hey', message)
            
            # Increase emoji chance to 45%
            if random.random() < 0.45:
                message += f" {random.choice(self.emojis)}"
                
            # Add to history
            self.last_responses.append(message.lower())
            return message
        except Exception as e:
            print(f"Error generating initial message: {e}")
            if is_group_chat:
                return f"Hey! Thoughts on {self.super_context}? {random.choice(self.emojis)}"
            else:
                return f"Hey! I'm {self.persona_name}, {self.persona_role}. What do you think about the industry these days? {random.choice(self.emojis)}"

    def _detect_message_context(self, messages):
        """Detect the context/tone of recent messages"""
        # Look at the last 3 messages
        recent = " ".join([m.lower() for m in messages[-3:]])
        
        # Core contexts
        has_farewell = any(word in recent for word in self.farewells)
        has_greeting = any(word in recent for word in self.greetings)
        
        # Additional contexts
        has_joke = any(signal in recent for signal in self.joke_signals)
        has_agreement = any(signal in recent for signal in self.agreement_signals) 
        has_disagreement = any(signal in recent for signal in self.disagreement_signals)
        
        # Question detection - more comprehensive
        has_question = '?' in recent or any(q in recent for q in [
            'what', 'how', 'why', 'when', 'where', 'who', 'which', 
            'mean', 'meaning', 'explain', 'tell me', 'definition'
        ])
        
        return {
            'farewell': has_farewell,
            'greeting': has_greeting,
            'joke': has_joke,
            'question': has_question,
            'agreement': has_agreement,
            'disagreement': has_disagreement
        }

    def _is_valid_response(self, response, recent_context, contexts):
        """Validate if a response makes sense in the current context"""
        response_lower = response.lower()
        
        # Don't reply with agreement to a farewell
        if contexts['farewell'] and any(word in response_lower for word in self.agreement_signals):
            return False
        
        # Don't say bye if no one is leaving
        if not contexts['farewell'] and any(word in response_lower for word in self.farewells):
            return False
        
        # Avoid repetitive responses
        if any(self._similarity(response_lower, r) > 0.6 for r in self.last_responses[-3:]):
            return False
            
        # Maximum 3 responses in history to check
        if len(self.last_responses) > 3:
            self.last_responses.pop(0)
            
        return True

    def _similarity(self, text1, text2):
        """Simple text similarity check"""
        # Convert both texts to sets of words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        # Calculate Jaccard similarity
        if not words1 or not words2:
            return 0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0

    async def add_resource(self, resource_path, description=None):
        """Add a resource to be used for answering questions"""
        return await self.document_handler.add_resource(resource_path, description)

    def _update_conversation_topic(self, message_history):
        """Update the conversation topic based on recent messages"""
        # Skip updating if we've updated recently (within 2 minutes)
        current_time = time.time()
        if current_time - self.last_topic_update_time < 120:
            return False
            
        # Look at the last 3 messages for topic detection
        if len(message_history) < 3:
            return False
            
        recent_messages = message_history[-3:]
        
        # Check for explicit topic change signals
        for msg in recent_messages:
            # Remove sender name if present
            if ': ' in msg:
                content = msg.split(': ', 1)[1].lower()
            else:
                content = msg.lower()
                
            # Check for topic starter phrases
            for starter in self.topic_starters:
                if (starter in content):
                    # Extract the topic after the starter phrase
                    parts = content.split(starter, 1)
                    if len(parts) > 1 and len(parts[1].strip()) > 3:
                        new_topic = parts[1].strip()
                        if len(new_topic) > 30:
                            new_topic = new_topic[:30] + "..."
                        
                        print(f"Topic changed to: {new_topic}")
                        self.conversation_topic = new_topic
                        self.last_substantive_topic = new_topic
                        self.last_topic_update_time = current_time
                        return True
            
            # Look for questions that might indicate topic change
            if '?' in content and len(content) > 15:
                # This is potentially a substantive question - set as new topic
                if len(content) > 30:
                    content = content[:30] + "..."
                
                print(f"Topic changed to question: {content}")
                self.conversation_topic = content
                self.last_substantive_topic = content
                self.last_topic_update_time = current_time
                return True
        
        return False

    def _create_message_fingerprint(self, message):
        """Create a unique fingerprint for a message to detect repeats"""
        # Extract content without sender name
        if ': ' in message:
            content = message.split(': ', 1)[1].lower()
        else:
            content = message.lower()
        
        # Normalize content
        normalized = re.sub(r'[^\w\s]', '', content).strip()
        
        # Create a hash
        return hashlib.md5(normalized.encode()).hexdigest()

    def _is_repeat_message(self, message):
        """Check if a message is substantially similar to previous ones"""
        fingerprint = self._create_message_fingerprint(message)
        
        # Check if this exact message has been seen before
        if fingerprint in self.message_fingerprints:
            return True
        
        # Add to fingerprints
        self.message_fingerprints.add(fingerprint)
        return False

    def _is_greeting_only(self, message):
        """Check if a message is just a greeting"""
        if ': ' in message:
            content = message.split(': ', 1)[1].lower()
        else:
            content = message.lower()
        
        return any(greeting in content for greeting in self.greetings) and len(content) < 20

    def _extract_user(self, message):
        """Extract username from a message"""
        if ': ' in message:
            return message.split(':', 1)[0].strip()
        return "User"

    def _track_greeting(self, message):
        """Track how many times a user has greeted"""
        if self._is_greeting_only(message):
            user = self._extract_user(message)
            if user in self.greeting_counts:
                self.greeting_counts[user] += 1
            else:
                self.greeting_counts[user] = 1
            return self.greeting_counts[user]
        return 0

    def _detect_question(self, message):
        """Detect if a message contains a question"""
        if ': ' in message:
            content = message.split(': ', 1)[1].lower()
        else:
            content = message.lower()
        
        return '?' in content or any(q in content for q in [
            'what', 'how', 'why', 'when', 'where', 'who', 'which', 
            'mean', 'meaning', 'explain', 'tell me', 'definition'
        ])

    def _track_question(self, message, response=None):
        """Track questions and their answers"""
        if not self._detect_question(message):
            return False, None
        
        question_fingerprint = self._create_message_fingerprint(message)
        
        # If this is recording a response to a question
        if response:
            self.question_history[question_fingerprint] = response
            return True, None
        
        # If this is checking if a question was already answered
        if question_fingerprint in self.question_history:
            return True, self.question_history[question_fingerprint]
        
        return True, None

    def _detect_identity_question(self, message):
        """Detect if someone is asking who the bot is"""
        if ': ' in message:
            content = message.split(': ', 1)[1].lower()
        else:
            content = message.lower()
        
        identity_patterns = [
            "who are you", "who is this", "who r u", "who u", "your name", 
            "what's your name", "whats ur name", "introduce yourself", "who am i talking to",
            "aap kaun ho", "tum kaun ho", "apka naam", "tumhara naam", "kon hai tu"
        ]
        
        return any(pattern in content for pattern in identity_patterns)

    def _detect_hinglish(self, message):
        """Detect if a message contains Hinglish"""
        if ': ' in message:
            content = message.split(': ', 1)[1].lower()
        else:
            content = message.lower()
        
        return any(pattern in content for pattern in self.hinglish_patterns)

    async def generate_response(self, message_history, is_group_chat=True, message_id_to_reply=None):
        """Generate a response based on chat history and super context"""
        # Track API usage for free tier if applicable
        if self.using_free_tier and self.user_id and self.api_key_valid:
            config.increment_api_usage(self.user_id)
        
        # Check if API key is valid before attempting to generate
        if not self.api_key_valid:
            print("Using fallback response due to invalid API key")
            # Different generic responses to avoid repetition
            generic_responses = [
                "Interesting point!",
                "Makes sense!",
                "Good to know!",
                "Tell me more?",
                "Cool!", 
                "That's neat!",
                "Thanks for sharing!",
                "Got it!",
                "Totally get it",
                "That's wild",
                "No way!",
                "For real?",
                "Keep going..."
            ]
            response = random.choice(generic_responses)
            if random.random() < 0.45:
                response += f" {random.choice(self.emojis)}"
                
            return {
                "messages": [response],
                "should_reply": message_id_to_reply is not None and random.random() < 0.3
            }
            
        # Get the last message
        last_message = message_history[-1] if message_history else ""
        
        # Check if the last message is a repeat
        is_repeat = self._is_repeat_message(last_message)
        
        # Check if the last message is just a greeting and how many times this user has greeted
        greeting_count = self._track_greeting(last_message)
        
        # Check if this is a question we've already answered
        is_question, previous_answer = self._track_question(last_message)
            
        # Update conversation topic
        self._update_conversation_topic(message_history)
        
        chat_context = "\n".join(message_history)
        
        # Add session context factors to the prompt - THIS WAS MISSING
        session_context = ""
        if is_repeat:
            session_context += "\nIMPORTANT: This message is very similar to one seen earlier in the session.\n"
        if greeting_count > 1:
            session_context += f"\nIMPORTANT: This user has greeted {greeting_count} times during this session.\n"
        if is_question and previous_answer:
            session_context += "\nIMPORTANT: This question is similar to one already answered in this session.\n"
        if len(self.topic_history) > 1:
            session_context += f"\nTopic evolution in this session: {' → '.join(self.topic_history[-3:])}\n"
        
        # Enhanced context detection
        contexts = self._detect_message_context(message_history)
        
        # Check for special message types
        is_simple_greeting = self._is_greeting_only(last_message)
        is_empty_response = False
        
        if ': ' in last_message:
            last_content = last_message.split(': ', 1)[1].lower()
            is_empty_response = any(empty in last_content for empty in self.empty_responses) and len(last_content) < 15
        
        # Determine response type for logging
        response_type = "general"
        if is_repeat or (is_question and previous_answer):
            response_type = "repeat_handling"
        elif contexts['question']:
            response_type = "question_answer"
        elif contexts['farewell']:
            response_type = "farewell"
        elif is_simple_greeting:
            response_type = "greeting"
        elif contexts['joke']:
            response_type = "humor"
        elif is_empty_response:
            response_type = "acknowledgment"
            
        # Track context data for analytics
        context_data = {
            "is_group_chat": is_group_chat,
            "is_repeat": is_repeat,
            "greeting_count": greeting_count,
            "has_previous_answer": previous_answer is not None,
            "detected_contexts": contexts
        }
        
        # Customized response guidance based on message type and session history
        is_identity_question = False
        if message_history:
            is_identity_question = self._detect_identity_question(message_history[-1])
        
        # Initialize context_instructions list here to avoid UnboundLocalError
        context_instructions = []
        
        # Build context guidance with identity handling
        if is_identity_question:
            context_instructions = [f"""
            IMPORTANT: The person is asking who you are. Respond naturally with:
            1. Your name is {self.persona_name}
            2. You're {self.persona_role}
            3. Be friendly and conversational
            4. Keep it brief (1-2 sentences)
            5. End with a question to continue the conversation
            """]
            response_type = "identity_question"
        elif is_repeat or (is_question and previous_answer):
            context_instructions = [f"IMPORTANT: This is a repeat question or message. Reference that you've already addressed this in the conversation. Be brief but friendly."]
        elif greeting_count > 1:
            context_instructions = [f"IMPORTANT: This user has greeted multiple times. Respond with a friendly greeting but add something new to the conversation."]
        elif is_simple_greeting:
            context_instructions = [f"IMPORTANT: Respond naturally to the greeting with a friendly tone. You can ask how they are or what's new."]
        elif is_empty_response:
            context_instructions = [f"IMPORTANT: Acknowledge their response, then add something interesting to keep the conversation flowing."]
        else:
            # Standard context handling with improved guidance
            if contexts['question']:
                context_instructions.append(f"IMPORTANT: Answer the question directly and conversationally.")
            elif contexts['farewell']:
                context_instructions.append("IMPORTANT: Someone said goodbye or is leaving. Respond appropriately to that.")
            elif contexts['greeting'] and not contexts['question']:
                context_instructions.append(f"IMPORTANT: Respond to the greeting in a friendly, natural way.")
            else:
                # Only mention the topic if we haven't talked about it in a while
                if random.random() < 0.3:  # 30% chance to bring the topic back
                    context_instructions.append(f"IMPORTANT: Continue the conversation naturally. If appropriate, you can gently bring the discussion back to {self.conversation_topic}.")
                else:
                    context_instructions.append("IMPORTANT: Continue the conversation in a natural way, responding to whatever the person just said.")
        
        context_guidance = "\n".join(context_instructions)
        
        # Build the prompt with improved conversational guidance
        prompt = f"""
        You're in a {'Telegram group chat' if is_group_chat else 'one-on-one Telegram conversation'} as {self.persona_name}.
        
        You are {self.persona_name}, {self.persona_role}.
        
        The conversation is about: {self.conversation_topic}
        
        Recent messages:
        {chat_context}
        
        {session_context}
        
        {context_guidance}
        """
        
        # Check for Hinglish in the last message
        has_hinglish = False
        if message_history:
            has_hinglish = self._detect_hinglish(message_history[-1])
        
        # Add Hinglish awareness to the prompt if detected
        if has_hinglish:
            prompt += """
            IMPORTANT: The person is using Hinglish (Hindi-English mixed language).
            You can occasionally mix in simple Hindi words in your reply.
            For example: "Haan, tech industry mein bahut opportunities hain!"
            Keep it mostly English with just a few Hindi words mixed in.
            """
        
        # Add learned insights if enabled
        if self.use_learning:
            learned_insights = self._get_learned_insights(self.conversation_topic, contexts, is_question, message_history)
            if learned_insights:
                prompt += f"\n{learned_insights}\n"
        
        prompt += """
        Generate 1-2 SHORT, natural responses (5-15 words each maximum).
        Each response should be on its own line, separated by a "|" character.
        
        Write exactly like a real person texting on their phone:
        - Casual and conversational
        - Use contractions (I'm, you're, doesn't)
        - Occasionally use abbreviations (tbh, lol, etc.)
        - Sound friendly but not overly enthusiastic
        - React naturally to what the other person just said
        - Don't sound like you're following a script
        - Be adaptive - if they change topics, go with it
        
        Examples of natural responses:
        "Yeah, been crazy busy with interviews lately."
        "Tech jobs are so competitive these days!"
        "I'm interested in ML. What about you?"
        "Lol, that's exactly what I thought too"
        
        Remember: Sound like a real human having a casual conversation.
        """
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.model.generate_content(prompt)
                full_text = response.text.strip()
                
                # Split the response into separate messages
                message_parts = full_text.split('|')
                
                # Clean up and validate each part
                clean_parts = []
                for i, part in enumerate(message_parts):
                    part = part.strip()
                    
                    # Skip empty parts
                    if not part:
                        continue
                    
                    # Remove any name prefixes
                    part = re.sub(r'^[A-Za-z]+:\s+', '', part)
                    
                    # Ensure part is not too long
                    words = part.split()
                    if len(words) > 11:
                        part = " ".join(words[:11])
                    
                    # Validate the response
                    if self._is_valid_response(part, message_history, contexts):
                        # Increased emoji chance to 45%
                        if random.random() < 0.45 and not any(emoji in part for emoji in self.emojis):
                            # Position: 0 = at end, 1 = at beginning, 2 = in middle
                            emoji_position = random.choices([0, 1, 2], weights=[70, 10, 20])[0]
                            emoji = random.choice(self.emojis)
                            
                            if emoji_position == 0:
                                part = f"{part} {emoji}"
                            elif emoji_position == 1:
                                part = f"{emoji} {part}"
                            else:
                                words = part.split()
                                if len(words) > 3:
                                    mid = len(words) // 2
                                    part = " ".join(words[:mid]) + f" {emoji} " + " ".join(words[mid:])
                        
                        clean_parts.append(part)
                        self.last_responses.append(part.lower())
                
                # If we have valid responses, track questions and return
                if clean_parts:
                    # If this was a question, record our answer
                    if is_question and not previous_answer:
                        self._track_question(last_message, clean_parts[0])
                    
                    # Log this response
                    self._log_response(response_type, last_message, clean_parts, context_data)
                    
                    # Determine if we should reply directly to the last message
                    # Questions and direct mentions more likely get a direct reply
                    should_reply = (is_question or 
                                    contexts['question'] or 
                                    (contexts['greeting'] and greeting_count <= 1) or
                                    random.random() < 0.3)  # 30% chance to reply to any message
                    
                    return {
                        "messages": clean_parts[:2],  # Limit to max 2 responses
                        "should_reply": should_reply and message_id_to_reply is not None
                    }
                
                # If we're here, none of the responses were valid, so try again    
                print(f"Attempt {attempt+1}: No valid responses, trying again...")
                
            except Exception as e:
                print(f"Error generating response (attempt {attempt+1}): {e}")
        
        # If all attempts failed, provide context-appropriate fallback responses
        fallback_response = []
        if contexts['farewell']:
            fallback_response = [f"Bye! {random.choice(self.emojis)}"]
        elif contexts['question']:
            fallback_response = ["Sorry, not sure about that one"]
        elif contexts['joke']:
            fallback_response = [f"LOL {random.choice(self.emojis)}", "That's hilarious!"]
        elif contexts['greeting']:
            fallback_response = [f"Hey there! {random.choice(self.emojis)}"]
        else:
            # Different generic responses to avoid repetition
            generic_responses = [
                "Interesting point!",
                "Makes sense!",
                "Good to know!",
                "Tell me more?",
                "Cool!", 
                "That's neat!",
                "Thanks for sharing!",
                "Got it!",
                "Totally get it",
                "That's wild",
                "No way!",
                "For real?",
                "Keep going..."
            ]
            fallback_response = [random.choice(generic_responses)]
        
        # Log fallback response
        self._log_response(f"fallback_{response_type}", last_message, fallback_response, context_data)
        
        # Update the fallback response to include the reply flag
        return {
            "messages": fallback_response,
            "should_reply": should_reply and message_id_to_reply is not None
        }

    def _log_response(self, response_type, user_message, bot_responses, context_data=None):
        """Log a response for later analysis"""
        timestamp = datetime.now()
        
        # Extract user from the message if possible
        user = self._extract_user(user_message) if user_message else "Unknown"
        
        # Create log entry
        log_entry = {
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "user": user,
            "user_message": user_message,
            "bot_responses": bot_responses,
            "response_type": response_type,
            "topic": self.conversation_topic,
            "context_data": context_data or {}
        }
        
        # Add to log
        self.response_log.append(log_entry)
    
    def get_session_analytics(self):
        """Generate analytics about the session responses"""
        total_responses = len(self.response_log)
        if (total_responses == 0):
            return {
                "status": "No responses logged in this session",
                "total_responses": 0
            }
            
        # Session duration
        duration = datetime.now() - self.session_start_time
        duration_minutes = duration.total_seconds() / 60
        
        # Count response types
        response_types = {}
        for entry in self.response_log:
            response_type = entry["response_type"]
            if (response_type in response_types):
                response_types[response_type] += 1
            else:
                response_types[response_type] = 1
        
        # Count unique users responded to
        unique_users = set(entry["user"] for entry in self.response_log)
        
        # Get most common topics
        topic_counts = {}
        for entry in self.response_log:
            topic = entry["topic"]
            if (topic in topic_counts):
                topic_counts[topic] += 1
            else:
                topic_counts[topic] = 1
        
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        top_topics = sorted_topics[:5] if len(sorted_topics) > 5 else sorted_topics
        
        # Analyze response length
        total_words = 0
        for entry in self.response_log:
            for response in entry["bot_responses"]:
                total_words += len(response.split())
        
        avg_words_per_response = total_words / total_responses if total_responses > 0 else 0
        
        return {
            "session_duration_minutes": round(duration_minutes, 2),
            "total_responses": total_responses,
            "response_types": response_types,
            "unique_users_engaged": len(unique_users),
            "users": list(unique_users),
            "top_topics": top_topics,
            "average_words_per_response": round(avg_words_per_response, 2),
            "emoji_usage_percentage": self._calculate_emoji_usage(),
            "full_log": self.response_log
        }
    
    def _calculate_emoji_usage(self):
        """Calculate percentage of responses that used emojis"""
        if not self.response_log:
            return 0
        
        responses_with_emoji = 0
        for entry in self.response_log:
            for response in entry["bot_responses"]:
                if any(emoji in response for emoji in self.emojis):
                    responses_with_emoji += 1
                    break
        
        return round((responses_with_emoji / len(self.response_log)) * 100, 2)
    
    def save_session_log(self, filename=None):
        """Save the session log to a JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            topic_slug = re.sub(r'[^\w]', '_', self.super_context)[:20]
            filename = f"session_{topic_slug}_{timestamp}.json"
        
        log_data = {
            "super_context": self.super_context,
            "session_start": self.session_start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "session_end": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analytics": self.get_session_analytics(),
            "responses": self.response_log
        }
        
        # If using MongoDB
        if os.environ.get('MONGODB_URI'):
            try:
                from db_handler import MongoDBHandler
                db_handler = MongoDBHandler()
                log_id = db_handler.save_session_log(log_data)
                print(f"Session responses saved to MongoDB with ID: {log_id}")
                
                # If learning is enabled, learn from this session
                if self.use_learning:
                    patterns_learned = self.learning_manager.learn_from_session(self.response_log)
                    print(f"Learned {patterns_learned} new patterns from this session")
                
                return log_id
            except Exception as e:
                print(f"Error saving to MongoDB: {e}")
                # Fall back to local storage
        
        # Local storage (for development or fallback)
        os.makedirs("logs", exist_ok=True)
        filepath = os.path.join("logs", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        # If learning is enabled, learn from this session
        if self.use_learning:
            patterns_learned = self.learning_manager.learn_from_session(self.response_log)
            print(f"Learned {patterns_learned} new patterns from this session")
        
        return filepath

    def set_learning_enabled(self, enabled=True):
        """Enable or disable learning from responses"""
        self.use_learning = enabled

    def learn_from_past_logs(self):
        """Learn from all available past logs"""
        return self.learning_manager.learn_from_all_logs()

    def get_learning_stats(self):
        """Get statistics about what has been learned"""
        return self.learning_manager.get_learning_stats()

    def _get_learned_insights(self, topic, contexts, is_question, message_history):
        """Get insights from learned patterns to guide response generation"""
        if not self.use_learning:
            return ""
        
        insights = []
        
        # Add topic-specific suggestions
        topic_suggestions = self.learning_manager.get_topic_suggestions(topic)
        if topic_suggestions:
            insights.append(f"Previous successful responses on this topic include: {'; '.join(topic_suggestions)}")
        
        # Add question-answer suggestions if this is a question
        if is_question and contexts.get('question') and message_history:
            # Get the last message as the question from the full message history
            last_message = message_history[-1] if message_history else ""
            if ': ' in last_message:
                question = last_message.split(': ', 1)[1]
            else:
                question = last_message
                
            previous_answer = self.learning_manager.get_question_answer(question)
            if previous_answer:
                insights.append(f"Similar question was previously answered with: {previous_answer}")
        
        # Enhanced context extraction from full history
        if len(message_history) > 3:
            # Identify recurring themes in conversation
            theme_words = self._extract_theme_words(message_history)
            if theme_words:
                insights.append(f"Recurring themes in this conversation: {', '.join(theme_words)}")
            
            # Track conversation flow
            if len(message_history) > 5:
                flow = self._analyze_conversation_flow(message_history)
                if flow:
                    insights.append(f"Conversation pattern: {flow}")
        
        # Add emoji suggestions based on response type
        response_type = "question_answer" if contexts.get('question') else "general"
        if contexts.get('greeting'):
            response_type = "greeting"
        elif contexts.get('farewell'):
            response_type = "farewell"
        
        preferred_emojis = self.learning_manager.get_preferred_emojis(response_type)
        if preferred_emojis:
            emoji_list = " ".join(preferred_emojis)
            insights.append(f"Consider using these emojis that worked well in similar contexts: {emoji_list}")
                
        return "\n".join(insights)

    def _extract_theme_words(self, message_history, top_n=3):
        """Extract most common theme words from conversation history"""
        # Skip if too few messages
        if len(message_history) < 3:
            return []
            
        # Common words to ignore
        stop_words = {'a', 'an', 'the', 'is', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 
                     'about', 'like', 'by', 'as', 'of', 'that', 'this', 'it', 'from', 'be', 'are', 'was',
                     'were', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'can', 'could', 'will',
                     'would', 'should', 'i', 'you', 'he', 'she', 'we', 'they', 'me', 'him', 'her', 'us',
                     'them', 'my', 'your', 'his', 'our', 'their', 'its', 'so', 'just', 'very', 'really'}
        
        # Extract all content without sender names
        all_text = ""
        for msg in message_history:
            if ': ' in msg:
                content = msg.split(': ', 1)[1].lower()
            else:
                content = msg.lower()
            all_text += " " + content
        
        # Count word frequencies
        words = all_text.split()
        word_counts = {}
        
        for word in words:
            # Clean the word
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word and len(clean_word) > 3 and clean_word not in stop_words:
                if clean_word in word_counts:
                    word_counts[clean_word] += 1
                else:
                    word_counts[clean_word] = 1
        
        # Get top theme words
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        top_words = [word for word, count in sorted_words[:top_n] if count > 1]
        
        return top_words

    def _analyze_conversation_flow(self, message_history):
        """Analyze the flow pattern of the conversation"""
        if len(message_history) < 5:
            return ""
        
        # Check for question-answer patterns
        question_count = 0
        for msg in message_history[-5:]:
            if '?' in msg:
                question_count += 1
        
        # Determine conversation patterns
        if question_count >= 3:
            return "Question-heavy discussion"
        
        # Check for alternating speakers
        speakers = []
        for msg in message_history[-6:]:
            if ': ' in msg:
                speaker = msg.split(':', 1)[0].strip()
                speakers.append(speaker)
        
        if len(speakers) >= 4:
            # Check if it's a back-and-forth or multi-person
            unique_speakers = len(set(speakers))
            if unique_speakers == 2 and speakers[0] != speakers[1] and speakers[0] == speakers[2]:
                return "Back-and-forth dialogue"
            elif unique_speakers > 2:
                return "Multi-person discussion"
        
        return "General conversation"

class LearningManager:
    """Manages learning from previous response logs to improve future responses"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        self.learned_patterns = {
            "topic_responses": defaultdict(list),  # Maps topics to successful responses
            "user_preferences": defaultdict(Counter),  # Tracks user interaction patterns
            "question_answers": {},  # Remembers good answers to common questions
            "common_transitions": defaultdict(list),  # Good transition phrases between topics
            "emoji_patterns": defaultdict(Counter)  # Which emojis work well in which contexts
        }
        
        # Create logs directory for local development
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Path to store learned patterns locally
        self.learning_file = os.path.join(log_dir, "learned_patterns.pkl")
        
        # Setup database handler if available
        self.db_handler = None
        if DB_HANDLER_AVAILABLE and os.environ.get('MONGO_URI'):
            try:
                self.db_handler = MongoDBHandler()
                # Load from MongoDB
                self._load_learned_patterns_db()
            except Exception as e:
                print(f"Error connecting to MongoDB: {e}")
                # Fallback to local storage
                self._load_learned_patterns_local()
        else:
            # No MongoDB available, use local storage
            self._load_learned_patterns_local()
    
    def _load_learned_patterns_local(self):
        """Load previously learned patterns from local file"""
        if os.path.exists(self.learning_file):
            try:
                with open(self.learning_file, 'rb') as f:
                    self.learned_patterns = pickle.load(f)
                print(f"Loaded learned patterns with {len(self.learned_patterns['topic_responses'])} topics")
            except Exception as e:
                print(f"Error loading learned patterns: {e}")
    
    def _load_learned_patterns_db(self):
        """Load previously learned patterns from MongoDB"""
        try:
            if not self.db_handler:
                return
                
            patterns = self.db_handler.load_learned_patterns()
            if patterns:
                # Convert back to defaultdict and Counter
                if 'topic_responses' in patterns:
                    self.learned_patterns['topic_responses'] = defaultdict(list, patterns['topic_responses'])
                if 'user_preferences' in patterns:
                    user_prefs = defaultdict(Counter)
                    for user, counts in patterns['user_preferences'].items():
                        user_prefs[user] = Counter(counts)
                    self.learned_patterns['user_preferences'] = user_prefs
                if 'emoji_patterns' in patterns:
                    emoji_pats = defaultdict(Counter)
                    for resp_type, counts in patterns['emoji_patterns'].items():
                        emoji_pats[resp_type] = Counter(counts)
                    self.learned_patterns['emoji_patterns'] = emoji_pats
                if 'question_answers' in patterns:
                    self.learned_patterns['question_answers'] = patterns['question_answers']
                if 'common_transitions' in patterns:  # Fixed: removed the extra single quote
                    self.learned_patterns['common_transitions'] = defaultdict(list, patterns['common_transitions'])
                    
                print(f"Loaded learned patterns from DB with {len(self.learned_patterns['topic_responses'])} topics")
        except Exception as e:
            print(f"Error loading learned patterns from DB: {e}")
    
    def save_learned_patterns(self):
        """Save learned patterns for future use"""
        # Try MongoDB first if available
        if self.db_handler:
            try:
                success = self.db_handler.save_learned_patterns(self.learned_patterns)
                if success:
                    print(f"Saved learned patterns to MongoDB with {len(self.learned_patterns['topic_responses'])} topics")
                    return True
            except Exception as e:
                print(f"Error saving to MongoDB, falling back to local storage: {e}")
                
        # Fallback to local storage
        try:
            with open(self.learning_file, 'wb') as f:
                pickle.dump(self.learned_patterns, f)
            print(f"Saved learned patterns locally with {len(self.learned_patterns['topic_responses'])} topics")
            return True
        except Exception as e:
            print(f"Error saving learned patterns locally: {e}")
            return False
    
    def learn_from_session(self, session_log):
        """Extract patterns from a completed session"""
        if not session_log:
            return 0
        
        patterns_learned = 0
        
        # Process each logged response
        for entry in session_log:
            if "bot_responses" not in entry or not entry["bot_responses"]:
                continue
                
            topic = entry.get("topic", "").lower()
            response_type = entry.get("response_type", "")
            user = entry.get("user", "")
            user_message = entry.get("user_message", "")
            bot_responses = entry.get("bot_responses", [])
            
            # Only learn from substantial topics
            if len(topic) < 3:
                continue
            
            # Store successful responses for topics
            if topic and bot_responses:
                for resp in bot_responses:
                    if len(resp) > 3:  # Only learn substantial responses
                        self.learned_patterns["topic_responses"][topic].append(resp)
                patterns_learned += 1
            
            # Track user interaction patterns
            if user and response_type:
                self.learned_patterns["user_preferences"][user][response_type] += 1
                patterns_learned += 1
            
            # Remember question/answer pairs
            if response_type == "question_answer" and user_message and bot_responses:
                if "?" in user_message:
                    question = user_message.split(":")[-1].strip() if ":" in user_message else user_message
                    question = question.lower()
                    
                    # Only store if we don't already have this question or if the new answer is better
                    if (question not in self.learned_patterns["question_answers"] or 
                            len(bot_responses[0]) < len(self.learned_patterns["question_answers"][question])):
                        self.learned_patterns["question_answers"][question] = bot_responses[0]
                        patterns_learned += 1
            
            # Learn emoji usage patterns
            for resp in bot_responses:
                # Extract emojis from the response
                emojis_used = [c for c in resp if c in "😊👍😂🔥💯👏😁🤣😎🙂😉🤩🤔👀😅🤨🧐😮😯🤷‍♂️🤷‍♀️👆💪💻🚀📱🤖💡⚡✨🌟💰📈🎯🔍💅🙌🫡🫠🤌✌️🫂🤝🙏🎉🔄❗❓⁉️‼️💭💬📢👇👈👉👋"]
                if emojis_used:
                    for emoji in emojis_used:
                        self.learned_patterns["emoji_patterns"][response_type][emoji] += 1
                    patterns_learned += 1
        
        # Save the updated learned patterns
        self.save_learned_patterns()
        
        return patterns_learned
    
    def learn_from_all_logs(self):
        """Process all available logs to learn patterns"""
        log_files = glob.glob(os.path.join(self.log_dir, "session_*.json"))
        total_patterns = 0
        
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                    if "responses" in log_data:
                        patterns = self.learn_from_session(log_data["responses"])
                        total_patterns += patterns
            except Exception as e:
                print(f"Error processing log file {log_file}: {e}")
        
        return total_patterns
    
    def get_topic_suggestions(self, topic, limit=3):
        """Get successful responses for a given topic"""
        topic_lower = topic.lower()
        suggestions = []
        
        # Check for exact match
        if topic_lower in self.learned_patterns["topic_responses"]:
            suggestions = self.learned_patterns["topic_responses"][topic_lower]
        
        # Check for partial matches
        if len(suggestions) < limit:
            for saved_topic, responses in self.learned_patterns["topic_responses"].items():
                if topic_lower in saved_topic or saved_topic in topic_lower:
                    suggestions.extend(responses)
                    if len(suggestions) >= limit*2:  # Get more than we need so we can randomize
                        break
        
        # Randomize and limit
        if suggestions:
            random.shuffle(suggestions)
            return suggestions[:limit]
        return []
    
    def get_question_answer(self, question):
        """Get a previously successful answer for a similar question"""
        if not question:
            return None
        
        question_lower = question.lower().strip()
        
        # Check for exact match
        if question_lower in self.learned_patterns["question_answers"]:
            return self.learned_patterns["question_answers"][question_lower]
        
        # Check for similar questions
        for saved_q, answer in self.learned_patterns["question_answers"].items():
            # If the question is very similar
            if (question_lower in saved_q or saved_q in question_lower or
                    self._similarity(question_lower, saved_q) > 0.7):
                return answer
        
        return None
    
    def get_preferred_emojis(self, response_type, limit=3):
        """Get most successful emojis for a response type"""
        if response_type not in self.learned_patterns["emoji_patterns"]:
            return []
            
        emoji_counter = self.learned_patterns["emoji_patterns"][response_type]
        if not emoji_counter:
            return []
            
        # Get the most common emojis for this response type
        most_common = emoji_counter.most_common(limit)
        return [emoji for emoji, count in most_common]
    
    def get_learning_stats(self):
        """Get statistics about what the bot has learned"""
        return {
            "topics_learned": len(self.learned_patterns["topic_responses"]),
            "questions_learned": len(self.learned_patterns["question_answers"]),
            "users_tracked": len(self.learned_patterns["user_preferences"]),
            "response_types_with_emojis": len(self.learned_patterns["emoji_patterns"]),
            "total_responses_remembered": sum(len(responses) for responses in self.learned_patterns["topic_responses"].values())
        }
    
    def _similarity(self, text1, text2):
        """Calculate text similarity (Jaccard)"""
        if not text1 or not text2:
            return 0
        
        set1 = set(text1.lower().split())
        set2 = set(text2.lower().split())
        
        # Fix the condition - current code incorrectly checks "if not set1 or set2:"
        if not set1 or not set2:
            return 0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0