import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

def test_connection():
    # Get MongoDB URI
    mongo_uri = os.environ.get('MONGO_URI')
    
    print(f"Connecting to MongoDB...")
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        
        # Ping the database
        client.admin.command('ping')
        
        print("Connection successful!")
        
        # Check database and collections
        db = client['chatbot_db']
        collections = db.list_collection_names()
        print(f"Available collections: {collections}")
        
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()