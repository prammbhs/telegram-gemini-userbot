import os
from pymongo import MongoClient
from datetime import datetime
import json

class MongoDBHandler:
    def __init__(self):
        # Connect to MongoDB Atlas
        mongodb_uri = os.environ.get('MONGODB_URI')
        self.client = MongoClient(mongodb_uri)
        self.db = self.client['chatbot_db']
        
        # Collections
        self.logs_collection = self.db['session_logs']
        self.learning_collection = self.db['learned_patterns']
    
    def save_session_log(self, log_data):
        """Save a session log to MongoDB"""
        # Add timestamps
        log_data['saved_at'] = datetime.now()
        
        # Insert the log
        result = self.logs_collection.insert_one(log_data)
        return str(result.inserted_id)
    
    def get_all_logs(self):
        """Get all session logs from MongoDB"""
        return list(self.logs_collection.find({}, {'_id': 0}))
    
    def save_learned_patterns(self, patterns):
        """Save learned patterns to MongoDB"""
        # Convert defaultdict to regular dict for MongoDB storage
        serializable_patterns = {}
        for key, value in patterns.items():
            if hasattr(value, 'items'):  # If it's a dict-like object
                serializable_patterns[key] = dict(value)
            else:
                serializable_patterns[key] = value
        
        # Update the single document that stores patterns
        self.learning_collection.update_one(
            {'type': 'learning_patterns'},
            {'$set': {'patterns': serializable_patterns, 'updated_at': datetime.now()}},
            upsert=True
        )
        return True
    
    def load_learned_patterns(self):
        """Load learned patterns from MongoDB"""
        result = self.learning_collection.find_one({'type': 'learning_patterns'})
        if result and 'patterns' in result:
            return result['patterns']
        return {}