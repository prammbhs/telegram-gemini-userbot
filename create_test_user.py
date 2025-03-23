from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_test_user():
    # Test user credentials - REMEMBER THESE FOR LOGIN
    username = "testuser"
    password = "password123"
    email = "test@example.com"
    
    # Connect to MongoDB
    mongo_uri = os.environ.get('MONGO_URI')
    if not mongo_uri:
        print("Error: MONGO_URI environment variable not set")
        return False
    
    try:
        client = MongoClient(mongo_uri)
        # Use explicit database name instead of get_default_database()
        db = client['telegrambotdb']  # This matches the database name in web_app.py
        
        # Check if user already exists
        existing_user = db.users.find_one({'username': username})
        if existing_user:
            print(f"Test user '{username}' already exists")
            return True
        
        # Create new user
        new_user = {
            'username': username,
            'email': email,
            'password': generate_password_hash(password),
            'auth_provider': 'local',
            'telegram_api_id': '12345678',  # Sample values
            'telegram_api_hash': 'abcdef1234567890abcdef1234567890',  # Sample value
            'gemini_api_key': 'YOUR_GEMINI_API_KEY',  # Replace with your API key if needed
            'dark_mode': False,
            'date_created': datetime.utcnow()
        }
        
        db.users.insert_one(new_user)
        print(f"Test user created successfully!")
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"Email: {email}")
        return True
        
    except Exception as e:
        print(f"Error creating test user: {e}")
        return False

if __name__ == "__main__":
    create_test_user()
