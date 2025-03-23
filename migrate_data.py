import os
import json
import glob
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

# Load environment variables
load_dotenv()

def migrate_logs():
    # Get MongoDB URI
    mongo_uri = os.environ.get('MONGO_URI')
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client['chatbot_db']
        
        # Get all JSON log files
        log_files = glob.glob('logs/session_*.json')
        
        print(f"Found {len(log_files)} log files to migrate")
        
        migrated_count = 0
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                
                # Add migration metadata
                log_data['migrated_from'] = log_file
                log_data['migrated_at'] = datetime.now()
                
                # Insert into MongoDB
                result = db.session_logs.insert_one(log_data)
                print(f"Migrated {log_file} to MongoDB with ID: {result.inserted_id}")
                migrated_count += 1
            except Exception as e:
                print(f"Error migrating {log_file}: {e}")
        
        print(f"Migration complete: {migrated_count}/{len(log_files)} files migrated")
        return True
    except Exception as e:
        print(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    migrate_logs()