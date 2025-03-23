import os
from pymongo import MongoClient
from datetime import datetime

class MongoDBHandler:
    def __init__(self):
        # Connect to MongoDB Atlas
        mongodb_uri = os.environ.get('MONGO_URI')  # Changed from 'MONGODB_URI' to 'MONGO_URI'
        self.client = MongoClient(mongodb_uri) if mongodb_uri else None
        
        if self.client:
            self.db = self.client.get_database()
            
            # Collections
            self.logs_collection = self.db['session_logs']
            self.learning_collection = self.db['learned_patterns']
    
    def save_session_log(self, log_data):
        """Save a session log to MongoDB"""
        if not self.client:
            return None
            
        # Add timestamps
        log_data['saved_at'] = datetime.now()
        
        # Insert the log
        result = self.logs_collection.insert_one(log_data)
        return str(result.inserted_id)
    
    def get_all_logs(self):
        """Get all session logs from MongoDB"""
        if not self.client:
            return []
            
        return list(self.logs_collection.find())
    
    def save_learned_patterns(self, patterns):
        """Save learned patterns to MongoDB"""
        if not self.client:
            return False
            
        # Convert defaultdict and Counter to regular dicts for MongoDB
        serializable_patterns = {}
        
        for key, value in patterns.items():
            if key == 'topic_responses' or key == 'common_transitions':
                # These are defaultdict(list)
                serializable_patterns[key] = dict(value)
            elif key == 'user_preferences' or key == 'emoji_patterns':
                # These are defaultdict(Counter)
                serializable_patterns[key] = {
                    k: dict(v) for k, v in value.items()
                }
            else:
                # Regular dicts
                serializable_patterns[key] = value
        
        # Update or insert
        self.learning_collection.replace_one(
            {'type': 'learned_patterns'},
            {'type': 'learned_patterns', 'data': serializable_patterns, 'updated_at': datetime.now()},
            upsert=True
        )
        
        return True
    
    def load_learned_patterns(self):
        """Load learned patterns from MongoDB"""
        if not self.client:
            return None
            
        result = self.learning_collection.find_one({'type': 'learned_patterns'})
        return result['data'] if result and 'data' in result else None