from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_pymongo import PyMongo
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import os
import json
import asyncio
import threading
import sys
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import config
from userbot import GeminiUserbot

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# MongoDB setup with error handling
mongo_uri = os.environ.get('MONGO_URI')
if not mongo_uri:
    print("ERROR: MONGO_URI environment variable is not set!", file=sys.stderr)
    print("Please set the MONGO_URI environment variable to your MongoDB connection string.", file=sys.stderr)
    print("Example: mongodb://username:password@host:port/dbname", file=sys.stderr)

app.config['MONGO_URI'] = mongo_uri
mongo = PyMongo(app)

# Verify MongoDB connection
try:
    # Force a command to check the connection
    mongo.db.command('ping')
    print("MongoDB connection successful")
except Exception as e:
    print(f"ERROR connecting to MongoDB: {e}", file=sys.stderr)
    print("Please check your MONGO_URI and ensure your MongoDB server is running.", file=sys.stderr)

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# OAuth setup
oauth = OAuth(app)

# Configure Google login
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
)

# Configure GitHub login
github = oauth.register(
    name='github',
    client_id=os.environ.get('GITHUB_CLIENT_ID'),
    client_secret=os.environ.get('GITHUB_CLIENT_SECRET'),
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

# Active bot instances
active_bots = {}
bot_threads = {}

# User model
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.email = user_data.get('email', '')
        self.telegram_api_id = user_data.get('telegram_api_id', '')
        self.telegram_api_hash = user_data.get('telegram_api_hash', '')
        self.gemini_api_key = user_data.get('gemini_api_key', '')
        self.dark_mode = user_data.get('dark_mode', False)
        self.profile_pic = user_data.get('profile_pic', '')
        self.auth_provider = user_data.get('auth_provider', 'local')

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
        return None
    except Exception as e:
        print(f"Error loading user: {e}")
        return None

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        try:
            user = mongo.db.users.find_one({'username': username})
            
            if user and check_password_hash(user['password'], password):
                user_obj = User(user)
                login_user(user_obj, remember=remember)
                session['dark_mode'] = user.get('dark_mode', False)
                
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
        except Exception as e:
            print(f"Database error during login: {e}")
            flash('Database connection error. Please try again later.', 'danger')
    
    return render_template('login.html')

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/google/authorize')
def google_authorize():
    token = google.authorize_access_token()
    resp = google.get('userinfo')
    user_info = resp.json()
    
    # Check if user exists
    user = mongo.db.users.find_one({'email': user_info['email']})
    
    if not user:
        # Create user
        new_user = {
            'username': user_info['email'].split('@')[0],
            'email': user_info['email'],
            'password': generate_password_hash(''),  # Empty password for OAuth users
            'profile_pic': user_info.get('picture', ''),
            'auth_provider': 'google',
            'telegram_api_id': '',
            'telegram_api_hash': '',
            'gemini_api_key': '',
            'dark_mode': False,
            'date_created': datetime.utcnow()
        }
        mongo.db.users.insert_one(new_user)
        user = mongo.db.users.find_one({'email': user_info['email']})
    
    user_obj = User(user)
    login_user(user_obj)
    session['dark_mode'] = user.get('dark_mode', False)
    
    return redirect(url_for('dashboard'))

@app.route('/login/github')
def github_login():
    redirect_uri = url_for('github_authorize', _external=True)
    return github.authorize_redirect(redirect_uri)

@app.route('/login/github/authorize')
def github_authorize():
    token = github.authorize_access_token()
    resp = github.get('user')
    user_info = resp.json()
    
    # Get email (GitHub may not provide email in the user info)
    emails_resp = github.get('user/emails')
    emails = emails_resp.json()
    primary_email = next((email['email'] for email in emails if email['primary']), None)
    
    if not primary_email and user_info.get('email'):
        primary_email = user_info['email']
    
    if not primary_email:
        flash('Could not retrieve email from GitHub', 'danger')
        return redirect(url_for('login'))
    
    # Check if user exists
    user = mongo.db.users.find_one({'email': primary_email})
    
    if not user:
        # Create user
        new_user = {
            'username': user_info['login'],
            'email': primary_email,
            'password': generate_password_hash(''),  # Empty password for OAuth users
            'profile_pic': user_info.get('avatar_url', ''),
            'auth_provider': 'github',
            'telegram_api_id': '',
            'telegram_api_hash': '',
            'gemini_api_key': '',
            'dark_mode': False,
            'date_created': datetime.utcnow()
        }
        mongo.db.users.insert_one(new_user)
        user = mongo.db.users.find_one({'email': primary_email})
    
    user_obj = User(user)
    login_user(user_obj)
    session['dark_mode'] = user.get('dark_mode', False)
    
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        error = None
        if not username or not email or not password:
            error = 'All fields are required'
        elif password != confirm_password:
            error = 'Passwords do not match'
        elif mongo.db.users.find_one({'username': username}):
            error = 'Username already exists'
        elif mongo.db.users.find_one({'email': email}):
            error = 'Email already registered'
            
        if error:
            flash(error, 'danger')
        else:
            # Create user
            new_user = {
                'username': username,
                'email': email,
                'password': generate_password_hash(password),
                'auth_provider': 'local',
                'telegram_api_id': '',
                'telegram_api_hash': '',
                'gemini_api_key': '',
                'dark_mode': False,
                'date_created': datetime.utcnow()
            }
            mongo.db.users.insert_one(new_user)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    # Stop any running bots for this user
    user_id = current_user.id
    for bot_id in list(active_bots.keys()):
        if active_bots[bot_id].get('user_id') == user_id:
            stop_bot(bot_id)
    
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's bots
    bots = list(mongo.db.bots.find({'user_id': current_user.id}))
    
    # Add is_active flag to each bot
    for bot in bots:
        bot_id = str(bot['_id'])
        bot['is_active'] = bot_id in active_bots
    
    return render_template('dashboard.html', bots=bots)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Update profile info
        telegram_api_id = request.form.get('telegram_api_id')
        telegram_api_hash = request.form.get('telegram_api_hash')
        gemini_api_key = request.form.get('gemini_api_key')
        dark_mode = True if request.form.get('dark_mode') == 'on' else False
        
        # Update user in database
        mongo.db.users.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': {
                'telegram_api_id': telegram_api_id,
                'telegram_api_hash': telegram_api_hash,
                'gemini_api_key': gemini_api_key,
                'dark_mode': dark_mode
            }}
        )
        
        # Update session
        session['dark_mode'] = dark_mode
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile.html')

@app.route('/bot/create', methods=['GET', 'POST'])
@login_required
def create_bot():
    if request.method == 'POST':
        name = request.form.get('name')
        target_group = request.form.get('target_group')
        context = request.form.get('context')
        duration = int(request.form.get('duration'))
        learning_enabled = True if request.form.get('learning_enabled') == 'on' else False
        
        # Validation
        if not name or not target_group or not context:
            flash('All fields are required', 'danger')
            return render_template('create_bot.html')
        
        # Create bot
        new_bot = {
            'name': name,
            'target_group': target_group,
            'context': context,
            'duration': duration,
            'learning_enabled': learning_enabled,
            'user_id': current_user.id,
            'date_created': datetime.utcnow(),
            'date_updated': datetime.utcnow()
        }
        result = mongo.db.bots.insert_one(new_bot)
        
        flash('Bot created successfully', 'success')
        return redirect(url_for('view_bot', bot_id=result.inserted_id))
    
    return render_template('create_bot.html')

@app.route('/bot/<bot_id>')
@login_required
def view_bot(bot_id):
    bot = mongo.db.bots.find_one({'_id': ObjectId(bot_id), 'user_id': current_user.id})
    
    if not bot:
        flash('Bot not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Add is_active flag
    bot['is_active'] = str(bot['_id']) in active_bots
    
    # Get logs for this bot
    logs = list(mongo.db.logs.find({'bot_id': str(bot['_id'])}).sort('timestamp', -1).limit(50))
    
    return render_template('view_bot.html', bot=bot, logs=logs)

@app.route('/bot/<bot_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bot(bot_id):
    bot = mongo.db.bots.find_one({'_id': ObjectId(bot_id), 'user_id': current_user.id})
    
    if not bot:
        flash('Bot not found', 'danger')
        return redirect(url_for('dashboard'))
    
    if str(bot['_id']) in active_bots:
        flash('Cannot edit a running bot. Please stop the bot first.', 'warning')
        return redirect(url_for('view_bot', bot_id=bot_id))
    
    if request.method == 'POST':
        name = request.form.get('name')
        target_group = request.form.get('target_group')
        context = request.form.get('context')
        duration = int(request.form.get('duration'))
        learning_enabled = True if request.form.get('learning_enabled') == 'on' else False
        
        # Validation
        if not name or not target_group or not context:
            flash('All fields are required', 'danger')
            return render_template('edit_bot.html', bot=bot)
        
        # Update bot
        mongo.db.bots.update_one(
            {'_id': ObjectId(bot_id)},
            {'$set': {
                'name': name,
                'target_group': target_group,
                'context': context,
                'duration': duration,
                'learning_enabled': learning_enabled,
                'date_updated': datetime.utcnow()
            }}
        )
        
        flash('Bot updated successfully', 'success')
        return redirect(url_for('view_bot', bot_id=bot_id))
    
    return render_template('edit_bot.html', bot=bot)

@app.route('/bot/<bot_id>/start')
@login_required
def start_bot_route(bot_id):
    bot = mongo.db.bots.find_one({'_id': ObjectId(bot_id), 'user_id': current_user.id})
    
    if not bot:
        flash('Bot not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if bot is already running
    if str(bot['_id']) in active_bots:
        flash('Bot is already running', 'warning')
        return redirect(url_for('view_bot', bot_id=bot_id))
    
    # Check if required credentials are set
    if not current_user.telegram_api_id or not current_user.telegram_api_hash or not current_user.gemini_api_key:
        flash('Please set your API credentials in your profile first', 'danger')
        return redirect(url_for('profile'))
    
    # Start the bot
    success, message = start_bot(bot, current_user)
    flash(message, 'success' if success else 'danger')
    
    return redirect(url_for('view_bot', bot_id=bot_id))

@app.route('/bot/<bot_id>/stop')
@login_required
def stop_bot_route(bot_id):
    bot = mongo.db.bots.find_one({'_id': ObjectId(bot_id), 'user_id': current_user.id})
    
    if not bot:
        flash('Bot not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if bot is running
    if str(bot['_id']) not in active_bots:
        flash('Bot is not running', 'warning')
        return redirect(url_for('view_bot', bot_id=bot_id))
    
    # Stop the bot
    success, message = stop_bot(str(bot['_id']))
    flash(message, 'success' if success else 'danger')
    
    return redirect(url_for('view_bot', bot_id=bot_id))

@app.route('/bot/<bot_id>/delete')
@login_required
def delete_bot(bot_id):
    bot = mongo.db.bots.find_one({'_id': ObjectId(bot_id), 'user_id': current_user.id})
    
    if not bot:
        flash('Bot not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if bot is running
    if str(bot['_id']) in active_bots:
        stop_bot(str(bot['_id']))
    
    # Delete bot
    mongo.db.bots.delete_one({'_id': ObjectId(bot_id)})
    
    flash('Bot deleted successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/bot/<bot_id>/analytics')
@login_required
def view_analytics(bot_id):
    bot = mongo.db.bots.find_one({'_id': ObjectId(bot_id), 'user_id': current_user.id})
    
    if not bot:
        flash('Bot not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get analytics data
    analytics = {}
    
    if str(bot['_id']) in active_bots:
        # Get analytics from running bot
        analytics = active_bots[str(bot['_id'])]['bot'].get_session_analytics()
    else:
        # Get the latest session log from database
        log = mongo.db.session_logs.find_one(
            {'bot_id': str(bot['_id'])}, 
            sort=[('timestamp', -1)]
        )
        
        if log:
            analytics = log.get('analytics', {})
    
    return render_template('analytics.html', bot=bot, analytics=analytics)

@app.route('/api/logs/<bot_id>')
@login_required
def get_logs(bot_id):
    # Check if user owns the bot
    bot = mongo.db.bots.find_one({'_id': ObjectId(bot_id), 'user_id': current_user.id})
    
    if not bot:
        return jsonify({'error': 'Bot not found'}), 404
    
    # Get logs for this bot
    logs = list(mongo.db.logs.find(
        {'bot_id': str(bot['_id'])},
        sort=[('timestamp', -1)],
        limit=50
    ))
    
    # Convert ObjectId to string for JSON serialization
    for log in logs:
        log['_id'] = str(log['_id'])
    
    return jsonify(logs)

@app.route('/toggle-theme')
@login_required
def toggle_theme():
    current_theme = session.get('dark_mode', False)
    new_theme = not current_theme
    
    # Update session
    session['dark_mode'] = new_theme
    
    # Update user in database
    mongo.db.users.update_one(
        {'_id': ObjectId(current_user.id)},
        {'$set': {'dark_mode': new_theme}}
    )
    
    return redirect(request.referrer or url_for('dashboard'))

# Helper functions for bot control
def start_bot(bot_config, user):
    """Start a new bot instance"""
    bot_id = str(bot_config['_id'])
    
    # Create new config.py for user-specific credentials
    config.update_user_config(
        user.id,
        user.telegram_api_id,
        user.telegram_api_hash,
        user.gemini_api_key
    )
    
    # Create bot instance
    bot = GeminiUserbot(
        bot_config['context'],
        bot_config['target_group'],
        bot_config['duration'],
        user.id
    )
    
    bot.set_learning_enabled(bot_config['learning_enabled'])
    
    # Start bot in a separate thread
    def run_bot():
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Record start
            log_entry = {
                'bot_id': bot_id,
                'user_id': user.id,
                'type': 'start',
                'timestamp': datetime.utcnow(),
                'message': f"Started bot {bot_config['name']}"
            }
            mongo.db.logs.insert_one(log_entry)
            
            # Run bot
            loop.run_until_complete(bot.start())
        except Exception as e:
            # Log error
            error_msg = str(e)
            log_entry = {
                'bot_id': bot_id,
                'user_id': user.id,
                'type': 'error',
                'timestamp': datetime.utcnow(),
                'message': f"Error: {error_msg}"
            }
            mongo.db.logs.insert_one(log_entry)
        finally:
            # Record stop
            log_entry = {
                'bot_id': bot_id,
                'user_id': user.id,
                'type': 'stop',
                'timestamp': datetime.utcnow(),
                'message': f"Stopped bot {bot_config['name']}"
            }
            mongo.db.logs.insert_one(log_entry)
            
            # Save analytics
            if bot_id in active_bots:
                try:
                    analytics = bot.get_session_analytics()
                    session_log = {
                        'bot_id': bot_id,
                        'user_id': user.id,
                        'timestamp': datetime.utcnow(),
                        'analytics': analytics
                    }
                    mongo.db.session_logs.insert_one(session_log)
                except Exception as e:
                    print(f"Error saving analytics: {e}")
                
                # Remove from active bots
                del active_bots[bot_id]
            
            # Close the loop properly
            if hasattr(loop, 'shutdown_asyncgens'):
                loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    
    # Store bot instance and start thread
    thread = threading.Thread(target=run_bot)
    thread.daemon = True
    thread.start()
    
    active_bots[bot_id] = {
        'bot': bot,
        'thread': thread,
        'user_id': user.id,
        'start_time': datetime.utcnow()
    }
    
    return True, f"Bot {bot_config['name']} started successfully"

def stop_bot(bot_id):
    """Stop a running bot"""
    if bot_id not in active_bots:
        return False, "Bot is not running"
    
    # Get bot instance
    bot_instance = active_bots[bot_id]['bot']
    
    # Run stop method in a new thread
    def stop_thread():
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot_instance.stop())
        except Exception as e:
            print(f"Error stopping bot: {e}")
        finally:
            # Proper cleanup of the event loop
            if hasattr(loop, 'shutdown_asyncgens'):
                loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    
    # Start stop thread
    stop_thread = threading.Thread(target=stop_thread)
    stop_thread.daemon = True
    stop_thread.start()
    
    # Wait for thread to finish (with timeout)
    stop_thread.join(timeout=5)
    
    # Remove from active bots
    if bot_id in active_bots:
        del active_bots[bot_id]
    
    return True, "Bot stopped successfully"

# Context processor for theme
@app.context_processor
def inject_theme():
    dark_mode = session.get('dark_mode', False)
    return {'dark_mode': dark_mode}

# MongoDB connection status endpoint for troubleshooting
@app.route('/mongo-status')
def mongo_status():
    try:
        # Check MongoDB connection
        mongo.db.command('ping')
        return jsonify({"status": "connected", "database": mongo.db.name})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/bot/start')
@login_required
def redirect_to_dashboard():
    """Redirect from the invalid /bot/start route to the dashboard"""
    flash('Please select a bot from the dashboard to start it', 'info')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)