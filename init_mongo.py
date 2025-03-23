import os
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from datetime import datetime

# Load environment variables
load_dotenv()

def init_database():
    # Get MongoDB URI
    mongo_uri = os.environ.get('MONGO_URI')
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client['chatbot_db']
        
        # Create collections if they don't exist
        collections = {
            'users': {'username': ASCENDING},
            'bots': {'user_id': ASCENDING, 'name': ASCENDING},
            'session_logs': {'saved_at': ASCENDING, 'bot_id': ASCENDING},
            'learned_patterns': {'type': ASCENDING}
        }
        
        for collection_name, index in collections.items():
            # Create collection if it doesn't exist
            if collection_name not in db.list_collection_names():
                print(f"Creating collection: {collection_name}")
                db.create_collection(collection_name)
            
            # Create index
            for field, direction in index.items():
                index_name = f"{field}_idx"
                db[collection_name].create_index([(field, direction)], name=index_name)
        
        # Insert initial learning patterns document if it doesn't exist
        if db.learned_patterns.count_documents({'type': 'learning_patterns'}) == 0:
            db.learned_patterns.insert_one({
                'type': 'learning_patterns',
                'patterns': {},
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
            print("Initialized learning patterns document")
            
        print("Database initialization complete")
        return True
    except Exception as e:
        print(f"Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    init_database()