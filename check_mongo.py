from pymongo import MongoClient
import os
from dotenv import load_dotenv
import sys
from urllib.parse import urlparse, parse_qs

# Load environment variables
load_dotenv()

def check_mongodb_connection():
    """Check MongoDB connection and print diagnostic information"""
    mongo_uri = os.environ.get('MONGO_URI')
    
    if not mongo_uri:
        print("ERROR: MONGO_URI environment variable is not set!", file=sys.stderr)
        print("Set it in your .env file as:")
        print("MONGO_URI=mongodb://username:password@host:port/dbname")
        return False
    
    print(f"MongoDB URI is set: {'yes' if mongo_uri else 'no'}")
    
    # Extract database name from URI or use default
    DEFAULT_DB_NAME = 'telegrambotdb'
    db_name = extract_db_name(mongo_uri) or DEFAULT_DB_NAME
    
    # Display sanitized connection information
    try:
        # Parse URI for display (without showing password)
        parsed_uri = urlparse(mongo_uri)
        username = parsed_uri.username or ""
        host = parsed_uri.netloc
        if '@' in host:
            host = host.split('@')[1]  # Get only the host part after @
            
        print(f"URI format: {parsed_uri.scheme}://{'*****' if username else ''}@{host}")
        print(f"Will connect to database: '{db_name}' (using default if not specified in URI)")
    except Exception as e:
        print(f"Could not parse URI: {e}")
    
    # Try to connect
    try:
        print("\nTrying to connect to MongoDB...")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        
        # Force a command to check the connection
        client.admin.command('ping')
        
        # Get server info
        server_info = client.server_info()
        print("✅ Connection successful!")
        print(f"MongoDB version: {server_info.get('version')}")
        
        # Try to access the database with the extracted or default name
        db = client[db_name]
        
        # Try a simple operation to verify database access
        try:
            collections = db.list_collection_names()
            print(f"✅ Connected to database '{db_name}' successfully!")
            print(f"Database has {len(collections)} collections:")
            for coll in collections:
                count = db[coll].count_documents({})
                print(f"  - {coll}: {count} documents")
        except Exception as db_e:
            print(f"⚠️ Connected to MongoDB server but had an issue with database '{db_name}': {db_e}")
            # Try to list all available databases
            try:
                all_dbs = client.list_database_names()
                print(f"Available databases: {', '.join(all_dbs)}")
                print(f"Please set one of these as your database or create '{db_name}'")
            except:
                print("Could not list available databases")
        
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}", file=sys.stderr)
        print("\nPossible issues:")
        print("1. MongoDB server is not running")
        print("2. Network connectivity issues")
        print("3. Authentication failed (incorrect username/password)")
        print("4. IP address not whitelisted in MongoDB Atlas")
        print("\nMake sure your MongoDB URI is correct and the database is accessible from your location.")
        return False

def extract_db_name(mongo_uri):
    """Extract database name from MongoDB URI"""
    try:
        # Parse the URI
        parsed_uri = urlparse(mongo_uri)
        
        # The path component contains the database name
        path = parsed_uri.path
        
        # Remove leading slash and get the database name
        if path and path.startswith('/'):
            db_name = path[1:]
            
            # If there are additional path components, take only the first part
            if '/' in db_name:
                db_name = db_name.split('/')[0]
                
            return db_name if db_name else None
            
        return None
    except Exception:
        return None

if __name__ == "__main__":
    check_mongodb_connection()
