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
from telegram_auth import TelegramAuthHandler

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
                
                # Check if the user needs to complete the setup wizard
                if not user.get('setup_complete', False):
                    return redirect(url_for('setup_wizard'))
                
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
            'date_created': datetime.utcnow(),
            'setup_complete': False,
            'api_keys': []  # Store multiple API keys
        }
        mongo.db.users.insert_one(new_user)
        user = mongo.db.users.find_one({'email': user_info['email']})
    
    user_obj = User(user)
    login_user(user_obj)
    session['dark_mode'] = user.get('dark_mode', False)
    
    # Redirect to setup wizard if not completed
    if not user.get('setup_complete', False):
        return redirect(url_for('setup_wizard'))
    
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
            # Create user with setup_complete set to False
            new_user = {
                'username': username,
                'email': email,
                'password': generate_password_hash(password),
                'auth_provider': 'local',
                'telegram_api_id': '',
                'telegram_api_hash': '',
                'gemini_api_key': '',
                'dark_mode': False,
                'date_created': datetime.utcnow(),
                'setup_complete': False,
                'api_keys': []  # Store multiple API keys
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

# Helper functions for dashboard
def get_user_bots(user_id):
    """Get all bots for a user with additional status information"""
    bots_cursor = mongo.db.bots.find({'user_id': user_id})
    bots = []
    
    for bot in bots_cursor:
        # Convert ObjectId to string for serialization
        bot['_id'] = str(bot['_id'])
        
        # Add active status
        bot['status'] = 'active' if bot['_id'] in active_bots else 'inactive'
        
        # Get response count from logs
        response_count = mongo.db.logs.count_documents({
            'bot_id': bot['_id'],
            'type': 'info',
            'message': {'$regex': 'response', '$options': 'i'}
        })
        
        # Add response count to bot object
        bot['responses'] = response_count
        
        # Add formatted dates
        if 'date_created' in bot:
            bot['created_at'] = bot['date_created'].strftime('%Y-%m-%d')
        
        bots.append(bot)
    
    # Sort by creation date (newest first)
    bots.sort(key=lambda x: x.get('date_created', datetime.min), reverse=True)
    
    return bots

def get_free_tier_warning(user_id):
    """Check if the user should see a free tier warning"""
    # Create a default structure with all required fields as None
    warning = {
        'show': False,
        'used': 0,
        'limit': 0,
        'remaining': 0,
        'percentage': 0,
        'percent_used': 0
    }
    
    # Check if user has set custom API key
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    
    if not user or not user.get('gemini_api_key'):
        # Check usage from config
        config_path = os.path.join(config.USER_CONFIGS_DIR, f"{user_id}.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                
                usage = user_config.get('FREE_TIER_USAGE', {})
                total_requests = usage.get('total_requests', 0)
                
                # Show warning if usage is over 80% of limit
                if total_requests > 0 and hasattr(config, 'FREE_TIER_MAX_REQUESTS'):
                    # Calculate remaining requests
                    remaining = max(0, config.FREE_TIER_MAX_REQUESTS - total_requests)
                    percentage = (total_requests / config.FREE_TIER_MAX_REQUESTS) * 100 if config.FREE_TIER_MAX_REQUESTS > 0 else 0
                    
                    warning.update({
                        'show': percentage > 80,
                        'used': total_requests,
                        'limit': config.FREE_TIER_MAX_REQUESTS,
                        'remaining': remaining,
                        'percentage': percentage,
                        'percent_used': round(percentage)
                    })
            except Exception as e:
                print(f"Error checking free tier usage: {e}")
    
    return warning

@app.route('/dashboard')
@login_required
def dashboard():
    """Render the dashboard page"""
    # Fetch bots and free tier warning
    bots = get_user_bots(current_user.id)
    free_tier_warning = get_free_tier_warning(current_user.id)

    # Calculate total_responses
    total_responses = sum(bot['responses'] for bot in bots) if bots else 0

    return render_template('dashboard.html', bots=bots, free_tier_warning=free_tier_warning, total_responses=total_responses)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Update profile info - removed Telegram API ID and Hash
        gemini_api_key = request.form.get('gemini_api_key')
        dark_mode = True if request.form.get('dark_mode') == 'on' else False
        
        # Update user in database
        mongo.db.users.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': {
                'gemini_api_key': gemini_api_key,
                'dark_mode': dark_mode,
                'setup_complete': True
            }}
        )
        
        # Update session
        session['dark_mode'] = dark_mode
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    
    # Get user's API keys
    user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    api_keys = user.get('api_keys', [])
    
    # Check if Telegram is verified
    auth_handler = TelegramAuthHandler(user_id=current_user.id)
    is_telegram_verified = auth_handler.is_authenticated()
    
    # Get free tier status
    free_tier_status = None
    if config.FREE_TIER_ENABLED:
        # Load user config to get usage info
        config_path = os.path.join(config.USER_CONFIGS_DIR, f"{current_user.id}.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                
                usage = user_config.get('FREE_TIER_USAGE', {})
                if usage:
                    # Calculate days remaining
                    start_date = usage.get('start_date')
                    if start_date:
                        start = datetime.fromisoformat(start_date)
                        days_elapsed = (datetime.now() - start).days
                        days_remaining = max(0, config.FREE_TIER_MAX_DAYS - days_elapsed)
                    else:
                        days_remaining = config.FREE_TIER_MAX_DAYS
                    
                    # Check if free tier is still active
                    is_active = (
                        usage.get('total_requests', 0) < config.FREE_TIER_MAX_REQUESTS and
                        days_remaining > 0
                    )
                    
                    free_tier_status = {
                        'total_requests': usage.get('total_requests', 0),
                        'max_requests': config.FREE_TIER_MAX_REQUESTS,
                        'days_remaining': days_remaining,
                        'max_days': config.FREE_TIER_MAX_DAYS,
                        'is_active': is_active
                    }
            except Exception as e:
                print(f"Error loading free tier status: {e}")
    
    return render_template(
        'profile.html', 
        api_keys=api_keys, 
        free_tier_status=free_tier_status,
        is_telegram_verified=is_telegram_verified
    )

@app.route('/bot/create', methods=['GET', 'POST'])
@login_required
def create_bot():
    if request.method == 'POST':
        name = request.form.get('name')
        target_group = request.form.get('target_group')
        duration = int(request.form.get('duration'))
        learning_enabled = True if request.form.get('learning_enabled') == 'on' else False
        context = request.form.get('context')
        
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

class SerializableUser:
    """A thread-safe alternative to the Flask-Login current_user object"""
    def __init__(self, user):
        self.id = str(user.id)
        self.username = user.username
        self.email = user.email
        # Remove telegram API credentials and add phone instead
        self.telegram_phone = getattr(user, 'telegram_phone', '')
        self.gemini_api_key = user.gemini_api_key

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
    
    # Check if required credentials are set - only need Gemini API key now
    if not current_user.gemini_api_key:
        flash('Please set your Gemini API key in your profile first', 'danger')
        return redirect(url_for('profile'))
    
    # Check if Telegram is verified
    auth_handler = TelegramAuthHandler(user_id=current_user.id)
    if not auth_handler.is_authenticated():
        flash('You need to verify your Telegram account before starting a bot', 'warning')
        return redirect(url_for('verify_telegram'))
    
    # Check Telegram connection before trying to start
    from telegram_connection_checker import TelegramConnectionChecker
    is_reachable, server, message = TelegramConnectionChecker.check_telegram_connection()
    
    if not is_reachable:
        flash('Cannot connect to Telegram servers. Please check your internet connection and try again.', 'danger')
        # Log the connectivity issue
        log_entry = {
            'bot_id': bot_id,
            'user_id': current_user.id,
            'type': 'error',
            'timestamp': datetime.now(),
            'message': f"Failed to connect to Telegram servers: {message}"
        }
        mongo.db.logs.insert_one(log_entry)
        return redirect(url_for('check_telegram_connection'))
    
    # Create a serializable user object that won't become invalid in threads
    serializable_user = SerializableUser(current_user)
    
    # Start the bot with the serializable user
    success, message = start_bot(bot, serializable_user)
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
def run_bot(loop, bot_config, user):
    """Run a bot in a separate thread with proper user context"""
    bot_id = str(bot_config['_id'])
    
    try:
        # Check if user object is valid to avoid NoneType errors
        if not user or not hasattr(user, 'id'):
            print(f"Error: Invalid user object for bot {bot_id}")
            return
            
        user_id = user.id  # Store user id in a local variable to prevent reference issues
        
        # Record start
        log_entry = {
            'bot_id': bot_id,
            'user_id': user_id,
            'type': 'start',
            'timestamp': datetime.now(),
            'message': f"Started bot {bot_config['name']}"
        }
        mongo.db.logs.insert_one(log_entry)
        
        # Run bot
        try:
            # Set this thread's event loop
            asyncio.set_event_loop(loop)
            
            # Get bot instance from active_bots
            bot = active_bots[bot_id]['bot']
            
            # Run the async start method with connection error handling
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    loop.run_until_complete(bot.start())
                    break  # If successful, exit the retry loop
                except ConnectionError as conn_err:
                    retry_count += 1
                    error_msg = f"Connection error (attempt {retry_count}/{max_retries}): {str(conn_err)}"
                    print(error_msg)
                    
                    # Log connection error
                    conn_log = {
                        'bot_id': bot_id,
                        'user_id': user_id,
                        'type': 'warning',
                        'timestamp': datetime.now(),
                        'message': error_msg
                    }
                    mongo.db.logs.insert_one(conn_log)
                    
                    if retry_count >= max_retries:
                        raise  # Re-raise if max retries reached
                    
                    # Wait before retrying (incremental backoff)
                    time.sleep(2 * retry_count)
            
            # Add a log message indicating successful initialization
            success_log = {
                'bot_id': bot_id,
                'user_id': user_id,
                'type': 'info',
                'timestamp': datetime.now(),
                'message': f"Bot initialized and running in group {bot_config['target_group']}"
            }
            mongo.db.logs.insert_one(success_log)
        except ConnectionError as e:
            # Handle connection errors specifically
            error_msg = f"Network connection error: {str(e)}. Please check your internet connection and Telegram service status."
            log_entry = {
                'bot_id': bot_id,
                'user_id': user_id,
                'type': 'error',
                'timestamp': datetime.now(),
                'message': error_msg
            }
            mongo.db.logs.insert_one(log_entry)
            print(f"Bot connection error: {error_msg}")
        except Exception as e:
            # Log other errors
            error_msg = str(e)
            log_entry = {
                'bot_id': bot_id,
                'user_id': user_id,
                'type': 'error',
                'timestamp': datetime.now(),
                'message': f"Error: {error_msg}"
            }
            mongo.db.logs.insert_one(log_entry)
            print(f"Bot error: {error_msg}")
    except Exception as outer_e:
        print(f"Error in run_bot thread: {outer_e}")
    finally:
        # Record stop
        try:
            # Only log stop if user object is valid
            if user and hasattr(user, 'id'):
                stop_log = {
                    'bot_id': bot_id,
                    'user_id': user.id,
                    'type': 'stop',
                    'timestamp': datetime.now(),
                    'message': f"Bot {bot_config['name']} stopped"
                }
                mongo.db.logs.insert_one(stop_log)
        except Exception as e:
            print(f"Error in run_bot cleanup: {e}")
        
        # Remove from active bots
        if bot_id in active_bots:
            del active_bots[bot_id]
        
        # Close the loop properly
        try:
            if hasattr(loop, 'shutdown_asyncgens'):
                loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception as e:
            print(f"Error closing event loop: {e}")

def start_bot(bot_config, user):
    """Start a new bot instance"""
    bot_id = str(bot_config['_id'])
    
    try:
        # Verify API key is present
        if not user.gemini_api_key or len(user.gemini_api_key) < 10:
            print(f"Invalid or missing Gemini API key for user {user.id}")
            return False, "Error: Invalid or missing Gemini API key. Please update your API key in profile settings."
        
        # Create new config.py for user-specific credentials
        if not config.update_user_config(
            user_id=user.id,
            telegram_phone=getattr(user, 'telegram_phone', ''),
            gemini_api_key=user.gemini_api_key
        ):
            print(f"Error updating user config for user {user.id}")
            return False, "Failed to update configuration"
        
        # Create bot instance
        bot = GeminiUserbot(
            bot_config['context'],
            bot_config['target_group'],
            bot_config['duration'],
            user.id
        )
        
        # Set learning mode
        if hasattr(bot, 'set_learning_enabled'):
            bot.set_learning_enabled(bot_config.get('learning_enabled', True))
        
        # Start bot in a separate thread with its own event loop
        loop = asyncio.new_event_loop()
        
        # Store bot instance and create thread
        active_bots[bot_id] = {
            'bot': bot,
            'loop': loop,
            'user_id': user.id,
            'start_time': datetime.now()
        }
        
        thread = threading.Thread(
            target=run_bot,
            args=(loop, bot_config, user)
        )
        thread.daemon = True
        thread.start()
        
        # Store thread reference
        active_bots[bot_id]['thread'] = thread
        
        return True, f"Bot {bot_config['name']} started successfully"
    except Exception as e:
        print(f"Error starting bot: {e}")
        # If there was an error, make sure we clean up any partial initialization
        if bot_id in active_bots:
            del active_bots[bot_id]
        return False, f"Error starting bot: {str(e)}"

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
    
    stop_thread = threading.Thread(target=stop_thread)
    stop_thread.daemon = True
    stop_thread.start()
    
    # Wait for thread to finish (with timeout)
    stop_thread.join(timeout=5)
    
    # Remove from active bots
    if bot_id in active_bots:
        del active_bots[bot_id]
    
    return True, "Bot stopped successfully"

@app.route("/help")
def help_center():
    """Render the help center page"""
    return render_template("help/help.html")

@app.route("/help/faq")
def help_faq():
    """Render the FAQ page"""
    return render_template("help/faq.html")

@app.route("/help/getting-started")
def help_getting_started():
    """Render the getting started guide"""
    return render_template("help/getting_started.html")

@app.route("/help/api")
def help_api():
    """Render the API documentation"""
    return render_template("help/api.html")

@app.route("/help/troubleshooting")
def help_troubleshooting():
    """Render the troubleshooting page"""
    return render_template("help/troubleshooting.html")

@app.route("/help/videos")
def help_videos():
    """Render the video tutorials page"""
    return render_template("help/videos.html")

@app.route("/help/contact")
def help_contact():
    """Render the contact support page"""
    return render_template("help/help_contact.html")

@app.route("/help/search")
def help_search():
    """Handle help center search"""
    query = request.args.get('q', '')
    # In a real app, you would search your help content here
    return render_template("help/search_results.html", query=query)

@app.route("/help/article/<article>")
def help_article(article):
    """Render a specific help article"""
    # In a real app, you might look up the article in a database
    article_template = f"help/articles/{article}.html"
    try:
        return render_template(article_template)
    except TemplateNotFound:
        # Fallback to a generic article template with the article name
        return render_template("help/article_not_found.html", article=article)

@app.route("/pricing")
def pricing():
    """Render the pricing page"""
    return render_template("pricing.html")

@app.route("/privacy")
def privacy():
    """Render the privacy policy page"""
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    """Render the terms of service page"""
    return render_template("terms.html")

@app.route("/blog")
def blog():
    """Render the blog page"""
    return render_template("blog.html")

@app.route('/test-api-key', methods=['POST'])
@login_required
def test_api_key():
    """Test if a Gemini API key is valid"""
    data = request.get_json()
    api_key = data.get('api_key', '')
    
    if not api_key:
        return jsonify({
            'valid': False,
            'message': 'API key is missing'
        })
    
    try:
        # Import here to avoid circular imports
        from ai_handler import GeminiAI
        
        # Test the API key using GeminiAI's validation method
        test_handler = GeminiAI(super_context="Test", api_key=api_key)
        
        # Return result
        return jsonify({
            'valid': test_handler.api_key_valid,
            'message': 'API key is valid' if test_handler.api_key_valid else 'Invalid API key'
        })
    
    except Exception as e:
        return jsonify({
            'valid': False,
            'message': f'Error testing API key: {str(e)}'
        })

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

# Setup wizard routes
@app.route('/setup-wizard')
@login_required
def setup_wizard():
    """Show the setup wizard for first-time users"""
    return render_template('setup_wizard.html')

@app.route('/complete-setup', methods=['POST'])
@login_required
def complete_setup():
    """Complete the setup wizard and save API keys"""
    gemini_api_key = request.form.get('gemini_api_key')
    
    # Get phone number instead of API credentials
    country_code = request.form.get('telegram_country_code', '')
    phone_number = request.form.get('telegram_phone', '')
    
    # Format the full phone number with country code
    if country_code and phone_number:
        if not country_code.startswith('+'):
            country_code = '+' + country_code
        phone_number = phone_number.replace(' ', '').replace('-', '')
        full_phone = f"{country_code}{phone_number}"
    else:
        full_phone = ""
    
    # Add the first API key to the list of API keys
    new_api_key = {
        'name': 'Default Gemini API Key',
        'api_key': gemini_api_key,
        'provider': 'gemini',
        'date_added': datetime.utcnow()
    }
    
    # Update user
    mongo.db.users.update_one(
        {'_id': ObjectId(current_user.id)},
        {
            '$set': {
                'gemini_api_key': gemini_api_key,
                'telegram_phone': full_phone,
                'setup_complete': True
            },
            '$push': {
                'api_keys': new_api_key
            }
        }
    )
    
    # Also update the configuration file
    config.update_user_config(
        user_id=current_user.id,
        telegram_phone=full_phone,
        gemini_api_key=gemini_api_key
    )
    
    flash('Setup completed successfully! Now let\'s verify your Telegram account.', 'success')
    return redirect(url_for('verify_telegram'))

# API key management routes
@app.route('/api-keys')
@login_required
def manage_api_keys():
    """Show the API key management page"""
    # Get the user with API keys
    user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    api_keys = user.get('api_keys', [])
    
    return render_template('api_keys.html', api_keys=api_keys)

@app.route('/api-keys/add', methods=['POST'])
@login_required
def add_api_key():
    """Add a new API key"""
    name = request.form.get('name')
    api_key = request.form.get('api_key')
    provider = request.form.get('provider', 'gemini')
    
    if not name or not api_key:
        flash('Name and API key are required', 'danger')
        return redirect(url_for('manage_api_keys'))
    
    # Create new API key
    new_api_key = {
        'id': str(ObjectId()),  # Generate a unique ID for this key
        'name': name,
        'api_key': api_key,
        'provider': provider,
        'date_added': datetime.utcnow()
    }
    
    # Add to user's API keys
    mongo.db.users.update_one(
        {'_id': ObjectId(current_user.id)},    
        {'$push': {'api_keys': new_api_key}}
    )
    
    flash(f'API key "{name}" added successfully', 'success')
    return redirect(url_for('manage_api_keys'))

@app.route('/api-keys/delete/<key_id>')
@login_required
def delete_api_key(key_id):
    """Delete an API key"""
    # Remove the API key with the given ID
    mongo.db.users.update_one(
        {'_id': ObjectId(current_user.id)},
        {'$pull': {'api_keys': {'id': key_id}}}
    )
    
    flash('API key removed successfully', 'success')
    return redirect(url_for('manage_api_keys'))

@app.route('/api-keys/set-default/<key_id>')
@login_required
def set_default_api_key(key_id):
    """Set an API key as the default"""
    # Get the user with API keys
    user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    api_keys = user.get('api_keys', [])
    
    # Find the key with the given ID
    for key in api_keys:
        if key.get('id') == key_id:
            # Set this key as the default in the gemini_api_key field
            mongo.db.users.update_one(
                {'_id': ObjectId(current_user.id)},
                {'$set': {'gemini_api_key': key['api_key']}}
            )
            flash(f'"{key["name"]}" set as the default API key', 'success')
            break
    
    return redirect(url_for('manage_api_keys'))

# Telegram verification route - updated to handle the authentication flow
@app.route('/verify-telegram', methods=['GET', 'POST'])
@login_required
def verify_telegram():
    """Verify Telegram account using application credentials"""
    if request.method == 'POST':
        # Get phone number from form
        country_code = request.form.get('country_code', '')
        phone_number = request.form.get('phone_number', '')
        
        # Combine country code and phone number, ensuring proper format
        if not country_code.startswith('+'):
            country_code = '+' + country_code
            
        # Strip any spaces or dashes from phone number
        phone_number = phone_number.replace(' ', '').replace('-', '')
        
        # Combine into full phone number
        full_phone = f"{country_code}{phone_number}"
        
        if not full_phone or len(full_phone) < 8:
            flash('Please enter a valid phone number with country code', 'danger')
            return render_template('verify_telegram.html')
        
        # Update user's Telegram phone number
        mongo.db.users.update_one(
            {'_id': ObjectId(current_user.id)},
            {
                '$set': {
                    'telegram_phone': full_phone,
                }
            }
        )
        
        # Also update the configuration file
        config.update_user_config(
            user_id=current_user.id,
            telegram_phone=full_phone,
            gemini_api_key=current_user.gemini_api_key
        )
        
        # Store in session for the verification step
        session['telegram_verification'] = {
            'phone': full_phone
        }
        
        # Redirect to the verification code page
        return redirect(url_for('telegram_verification_code'))
    
    # Get user's existing phone info if available
    user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    existing_phone = user.get('telegram_phone', '')
    
    # Extract country code and local number if available
    country_code = ''
    local_number = ''
    if existing_phone:
        # Try to parse the existing phone number
        import re
        match = re.match(r'(\+\d+)(\d+)', existing_phone)
        if match:
            country_code = match.group(1)
            local_number = match.group(2)
    
    # Check if already authenticated
    auth_handler = TelegramAuthHandler(
        user_id=current_user.id
    )
    is_authenticated = auth_handler.is_authenticated()
    
    return render_template('verify_telegram.html', 
                          existing={'country_code': country_code, 'local_number': local_number},
                          is_authenticated=is_authenticated)

@app.route('/telegram-verification-code', methods=['GET', 'POST'])
@login_required
def telegram_verification_code():
    """Handle Telegram verification code entry"""
    # Check if we have the required session data
    if 'telegram_verification' not in session:
        flash('Please enter your phone number first', 'danger')
        return redirect(url_for('verify_telegram'))
    
    verification_data = session['telegram_verification']
    
    if request.method == 'POST':
        verification_code = request.form.get('verification_code')
        two_factor_password = request.form.get('two_factor_password', '')
        
        if not verification_code:
            flash('Verification code is required', 'danger')
            return render_template('telegram_verification_code.html')
        
        if 'phone_code_hash' not in verification_data:
            flash('Session expired. Please try again', 'danger')
            return redirect(url_for('verify_telegram'))
        
        # Run async code to verify authentication
        async def verify_auth():
            auth_handler = TelegramAuthHandler(
                user_id=current_user.id,
                phone_number=verification_data['phone']
            )
            
            # Set the phone code hash from the session
            auth_handler.phone_code_hash = verification_data['phone_code_hash']
            
            # Verify the code
            return await auth_handler.verify_code(verification_code, two_factor_password)
        
        # Create a new event loop for the async code
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(verify_auth())
        finally:
            loop.close()
        
        if result['status'] == 'success':
            # Update user record with verified flag
            mongo.db.users.update_one(
                {'_id': ObjectId(current_user.id)},
                {'$set': {'telegram_verified': True}}
            )
            
            # Clear session data
            if 'telegram_verification' in session:
                del session['telegram_verification']
                
            flash('Telegram authentication successful! Your bot can now send messages.', 'success')
            return redirect(url_for('profile'))
        elif result['status'] == '2fa_needed':
            # Show the 2FA password field
            flash('Two-factor authentication is enabled. Please enter your password.', 'warning')
            return render_template('telegram_verification_code.html', needs_2fa=True)
        else:
            # Authentication failed
            flash(f'Authentication failed: {result["message"]}', 'danger')
            return render_template('telegram_verification_code.html')
            
    # For GET request, initiate the authentication process to send the code
    async def start_auth():
        auth_handler = TelegramAuthHandler(
            user_id=current_user.id,
            phone_number=verification_data['phone']
        )
        
        return await auth_handler.start_authentication()
    
    # Create a new event loop for the async code
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(start_auth())
    finally:
        loop.close()
    
    if result['status'] == 'error':
        flash(f'Error sending verification code: {result["message"]}', 'danger')
        return redirect(url_for('verify_telegram'))
    
    if 'phone_code_hash' in result:
        # Store the phone_code_hash in the session for later verification
        verification_data['phone_code_hash'] = result['phone_code_hash']
        session['telegram_verification'] = verification_data
        
        flash(f'Verification code sent to {verification_data["phone"]}. Please check your Telegram app.', 'info')
    
    return render_template('telegram_verification_code.html')

@app.route('/check-telegram-connection')
@login_required
def check_telegram_connection():
    """Check and diagnose Telegram connection issues"""
    from telegram_connection_checker import TelegramConnectionChecker
    
    # Run the connection check
    is_reachable, server, message = TelegramConnectionChecker.check_telegram_connection()
    
    # If not reachable, run diagnostics
    if not is_reachable:
        diagnosis = TelegramConnectionChecker.diagnose_connection_problems()
        
        return render_template(
            'connection_issues.html',
            is_reachable=is_reachable,
            server=server,
            message=message,
            diagnosis=diagnosis
        )
    
    # If reachable, just display success message
    flash(f'Telegram connection is working properly via {server}', 'success')
    return redirect(url_for('profile'))

if __name__ == '__main__':
    # Enable production mode for deployment
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
    port = int(os.environ.get('PORT', 5000))
    
    # Railway uses 0.0.0.0 for binding
    host = '0.0.0.0'
    
    app.run(host=host, port=port, debug=debug_mode)