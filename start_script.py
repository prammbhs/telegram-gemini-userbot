"""
Simple script to start the web app with proper error handling.
"""
import traceback
import sys
import os

def start_app():
    try:
        # Make sure we import from the correct directory
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # Import web_app and run it
        from web_app import app
        app.run(debug=True)
    except Exception as e:
        print("=" * 80)
        print(f"ERROR STARTING APPLICATION: {str(e)}")
        print("-" * 80)
        traceback.print_exc()
        print("=" * 80)
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    start_app()
