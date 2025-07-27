import os
import json
import logging
import threading
import time
import socket
import socks
import random
from typing import Dict, List, Set, Optional
from concurrent.futures import ThreadPoolExecutor

import requests
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# === Configuration ===
TOKEN = '7502824448:AAElBY0QQvG-GCE7rbhu0SWWU7J9rnELdr8'  # Replace with your Bot token
ADMIN_CHAT_ID = 7850595240  # Replace with your admin Telegram ID
bot = TeleBot(TOKEN)

# Store original socket for restoration
original_socket = socket.socket

# === File Paths ===
ALL_USERS_FILE = 'all_users.json'
BANNED_USERS_FILE = 'banned_users.json'
SESSIONS_FILE = "sessions.json"
APPROVED_USERS_FILE = 'APPROVED_USERS.json'

# === Global Variables ===
user_state: Dict[int, dict] = {}
multi_report_selections: Dict[int, Set[str]] = {}
ALL_USERS: Dict[int, dict] = {}
BANNED_USERS: List[int] = []
report_processes: Dict[int, dict] = {}
APPROVED_USERS: List[int] = []

# Thread pool for async operations
executor = ThreadPoolExecutor(max_workers=5)

# === Logging Setup ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Report Types ===
REPORT_TYPES = [
    {"id": "1", "name": "Spam"},
    {"id": "2", "name": "Self-harm"},
    {"id": "3", "name": "Drugs"},
    {"id": "4", "name": "Nudity"},
    {"id": "5", "name": "Violence 3"},
    {"id": "6", "name": "Hate Speech"},
    {"id": "7", "name": "Harassment"},
    {"id": "8", "name": "Impersonation (Instagram)"},
    {"id": "9", "name": "Impersonation (Business)"},
    {"id": "10", "name": "Impersonation (BMW)"},
    {"id": "11", "name": "Under 13"},
    {"id": "12", "name": "Gun Selling"},
    {"id": "13", "name": "Violence 1"},
    {"id": "14", "name": "Violence 4"}
]

# === SOCKS Proxy Functions ===
def setup_socks_proxy():
    """Setup SOCKS proxy for Tor connection."""
    try:
        socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
        socket.socket = socks.socksocket
        logger.info("SOCKS proxy configured for Tor")
        return True
    except Exception as e:
        logger.error(f"Failed to setup SOCKS proxy: {e}")
        return False

def restore_original_socket():
    """Restore original socket connection."""
    try:
        socket.socket = original_socket
        logger.info("Original socket connection restored")
        return True
    except Exception as e:
        logger.error(f"Failed to restore socket: {e}")
        return False

# === Utility Functions ===
def load_json_file(filename: str, default=None):
    """Load data from a JSON file."""
    if default is None:
        default = {} if filename.endswith('.json') else []
    
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {int(k): v for k, v in data.items()} if filename == ALL_USERS_FILE else data
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json_file(filename: str, data):
    """Save data to a JSON file."""
    with open(filename, 'w') as f:
        if filename == ALL_USERS_FILE and isinstance(data, dict):
            json.dump({str(k): v for k, v in data.items()}, f)
        else:
            json.dump(data, f)

def load_initial_data():
    """Load all initial data files."""
    global ALL_USERS, BANNED_USERS, APPROVED_USERS
    ALL_USERS = load_json_file(ALL_USERS_FILE)
    BANNED_USERS = load_json_file(BANNED_USERS_FILE, [])
    APPROVED_USERS = load_json_file(APPROVED_USERS_FILE, [])

def save_all_users():
    """Save all users data."""
    save_json_file(ALL_USERS_FILE, ALL_USERS)

def save_approved_users():
    """Save approved users list."""
    save_json_file(APPROVED_USERS_FILE, APPROVED_USERS)

def save_banned_users():
    """Save banned users list."""
    save_json_file(BANNED_USERS_FILE, BANNED_USERS)

def is_user_approved(user_id: int) -> bool:
    """Check if user has access to the bot."""
    return user_id == ADMIN_CHAT_ID or user_id in APPROVED_USERS

def get_user_status(user_id: int) -> str:
    """Get user access status."""
    if user_id == ADMIN_CHAT_ID:
        return "Admin"
    elif user_id in BANNED_USERS:
        return "BANNED"
    elif user_id in APPROVED_USERS:
        return "Approved"
    else:
        return "Pending"

def get_user_sessions(chat_id: int) -> Dict[str, str]:
    """Get all sessions for a specific user."""
    data = load_json_file(SESSIONS_FILE)
    return data.get(str(chat_id), {})

def save_user_session(chat_id: int, username: str, session_value: str):
    """Save a session for a specific user."""
    data = load_json_file(SESSIONS_FILE)
    user_id = str(chat_id)
    
    if user_id not in data:
        data[user_id] = {}
    
    data[user_id][username] = session_value
    save_json_file(SESSIONS_FILE, data)

def delete_user_sessions(chat_id: int, sessions_to_delete: List[str]):
    """Delete specific sessions for a user."""
    data = load_json_file(SESSIONS_FILE)
    user_id = str(chat_id)
    
    if user_id in data:
        for session_name in sessions_to_delete:
            if session_name in data[user_id]:
                del data[user_id][session_name]
        
        save_json_file(SESSIONS_FILE, data)
        return len(sessions_to_delete)
    return 0

def get_target_user_id(username: str) -> Optional[str]:
    """Get Instagram user ID from username."""
    try:
        response = requests.post(
            'https://i.instagram.com/api/v1/users/lookup/',
            headers={
                "Connection": "close",
                "X-IG-Connection-Type": "WIFI",
                "mid": "XOSINgABAAG1IDmaral3noOozrK0rrNSbPuSbzHq",
                "X-IG-Capabilities": "3R4=",
                "Accept-Language": "en-US",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": "Instagram 99.4.0 TweakPY_vv1ck (TweakPY_vv1ck)",
                "Accept-Encoding": "gzip, deflate"
            },
            data={"signed_body": f"xxxx.{{\"q\":\"{username}\"}}"},
            timeout=10
        )
        response.raise_for_status()
        response_data = response.json()
        
        if 'user' in response_data and 'pk' in response_data['user']:
            return str(response_data['user']['pk'])
        elif 'user_id' in response_data:
            return str(response_data['user_id'])
        
        logger.warning(f"No user ID found for {username}: {response_data}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting user ID for {username}: {e}")
        return None

def validate_single_session(session_id: str) -> tuple:
    """Validate a single session quickly."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Cookie": f"sessionid={session_id};"
    }
    
    try:
        response = requests.get(
            "https://www.instagram.com/accounts/edit/", 
            headers=headers,
            timeout=8,
            allow_redirects=False
        )
        
        if response.status_code == 200 and '"username":"' in response.text:
            try:
                username = response.text.split('"username":"')[1].split('"')[0]
                return True, username
            except (IndexError, AttributeError):
                return False, "Parse error"
        return False, "Invalid session"
        
    except Exception as e:
        return False, f"Error: {str(e)[:30]}"

def send_report(sessionid: str, csrftoken: str, target_id: str, report_type_id: str) -> Optional[int]:
    """Send a report to Instagram - ENHANCED WITH LOGGING."""
    try:
        report_url = f"https://i.instagram.com/users/{target_id}/flag/"
        
        headers = {
            "User-Agent": "Instagram 99.4.0 TweakPY_vv1ck (TweakPY_vv1ck)",
            "cookie": f"sessionid={sessionid}; csrftoken=1;",
            "X-CSRFToken": csrftoken,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive"
        }
        
        data = f'source_name=&reason_id={report_type_id}&frx_context='
        
        logger.info(f"🔗 Sending POST to: {report_url}")
        logger.info(f"📊 Headers: User-Agent, Cookie (sessionid={sessionid[:20]}...), X-CSRFToken")
        logger.info(f"📄 Data: {data}")
        
        response = requests.post(
            report_url,
            headers=headers,
            data=data,
            allow_redirects=False,
            timeout=15
        )
        
        logger.info(f"📥 Response Status: {response.status_code}")
        logger.info(f"📥 Response Headers: {dict(response.headers)}")
        logger.info(f"📥 Response Text (first 200 chars): {response.text[:200]}")
        
        return response.status_code
        
    except requests.exceptions.RequestException as e:
        logger.error(f"🌐 Network error during report: {e}")
        return None
    except Exception as e:
        logger.error(f"💥 Unexpected error sending report: {e}")
        return None

def create_process_buttons(paused_state: bool) -> InlineKeyboardMarkup:
    """Create control buttons for report processes."""
    markup = InlineKeyboardMarkup()
    button_text = "▶️ Resume" if paused_state else "⏸ Pause"
    callback_data = "resume_process" if paused_state else "pause_process"
    
    markup.add(
        InlineKeyboardButton(button_text, callback_data=callback_data),
        InlineKeyboardButton("🛑 Kill", callback_data="kill_process")
    )
    return markup

def require_access(func):
    """Decorator to check if user has access to bot features."""
    def wrapper(message):
        user_id = message.from_user.id
        
        if user_id in BANNED_USERS:
            bot.send_message(user_id, "You are banned and cannot use this bot.")
            return
        
        if not is_user_approved(user_id):
            bot.send_message(
                user_id, 
                "⚠️ Access Required\n\nYou need approval to use this bot."
            )
            return
        
        return func(message)
    return wrapper

# === Async Session Validation ===
def validate_sessions_async(chat_id: int, sessions: List[str], progress_msg_id: int):
    """Validate sessions asynchronously without blocking the main thread."""
    valid_sessions = []
    invalid_sessions = []
    
    def update_progress(current: int, total: int, valid: int, invalid: int):
        try:
            bot.edit_message_text(
                f"🔄 **Validating sessions...**\n\n"
                f"📊 Progress: {current}/{total}\n"
                f"✅ Valid: {valid} | ❌ Invalid: {invalid}",
                chat_id=chat_id,
                message_id=progress_msg_id,
                parse_mode="Markdown"
            )
        except Exception:
            pass
    
    for i, session_id in enumerate(sessions):
        if len(session_id) < 20:  # Skip obviously invalid sessions
            invalid_sessions.append((session_id, "Too short"))
            update_progress(i + 1, len(sessions), len(valid_sessions), len(invalid_sessions))
            continue
        
        is_valid, result = validate_single_session(session_id)
        
        if is_valid:
            username = result
            save_user_session(chat_id, username, session_id)
            valid_sessions.append(username)
        else:
            invalid_sessions.append((session_id[:20] + "...", result))
        
        update_progress(i + 1, len(sessions), len(valid_sessions), len(invalid_sessions))
        
        # Small delay to prevent overwhelming
        if i < len(sessions) - 1:
            time.sleep(0.5)
    
    # Send final results
    try:
        bot.delete_message(chat_id, progress_msg_id)
    except Exception:
        pass
    
    result_text = (
        f"📋 **Validation Complete**\n\n"
        f"✅ **Valid:** {len(valid_sessions)}\n"
        f"❌ **Invalid:** {len(invalid_sessions)}\n"
    )
    
    if valid_sessions:
        result_text += f"\n**Added sessions:**\n" + "\n".join([f"• {name}" for name in valid_sessions[:10]])
        if len(valid_sessions) > 10:
            result_text += f"\n... and {len(valid_sessions) - 10} more"
    
    bot.send_message(chat_id, result_text, parse_mode="Markdown")
    
    # Clear user state
    if chat_id in user_state:
        user_state[chat_id] = {}

# === Reporting Functions ===
def start_reporting_loop(chat_id: int, target_id: str, username: str, report_id: str, 
                        sessions: Dict[str, str], multi_reports: List[str] = None, delay: int = 5):
    """Fixed version - actually starts the worker thread."""
    done = 0
    errors = 0
    paused = threading.Event()
    stopped = threading.Event()
    report_list = multi_reports or [report_id]
    index = 0

    # Setup SOCKS proxy before starting reports
    proxy_setup = setup_socks_proxy()

    # Send initial animation with controls
    gif_url = "https://raw.githubusercontent.com/rev-eng1/ThemeX/refs/heads/main/video_2025-06-27_16-39-43.gif"
    caption = f"IG: sir.say\nDone: {done} | Errors: {errors} | Target: @{username}"
    msg = bot.send_animation(
        chat_id, 
        gif_url, 
        caption=caption, 
        reply_markup=create_process_buttons(False)
    )
    
    # Store process info
    report_processes[chat_id] = {
        "paused": paused,
        "stopped": stopped,
        "msg_id": msg.message_id,
        "username": username,
        "done": done,
        "errors": errors,
        "proxy_active": proxy_setup
    }

    def worker():
        nonlocal done, errors, index
        logger.info(f"🔄 Worker thread started for {username}")
        
        while not stopped.is_set():
            for name, sess_id in sessions.items():
                if stopped.is_set():
                    break
                
                logger.info(f"📊 Processing session: {name}")
                
                # Handle pause state
                while paused.is_set():
                    time.sleep(1)
                    if stopped.is_set():
                        break

                if stopped.is_set():
                    break

                # Determine current report type
                if multi_reports:
                    current_name = report_list[index % len(report_list)]
                    current_report_id = next(
                        (r["id"] for r in REPORT_TYPES if r["name"] == current_name), 
                        report_id
                    )
                    index += 1
                    logger.info(f"🎯 Using report type: {current_name} (ID: {current_report_id})")
                else:
                    current_report_id = report_id
                    logger.info(f"🎯 Using single report type ID: {current_report_id}")

                # Send report
                logger.info(f"📤 Sending report for session {name} to target {target_id}")
                status = send_report(sess_id, "1", target_id, current_report_id)
                
                logger.info(f"📥 Report response status: {status}")
                
                if status == 200:
                    done += 1
                    logger.info(f"✅ Report successful. Total done: {done}")
                else:
                    errors += 1
                    logger.info(f"❌ Report failed. Total errors: {errors}")

                # Update process info
                report_processes[chat_id].update({
                    "done": done,
                    "errors": errors
                })

                # Update message (non-blocking)
                try:
                    bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=msg.message_id,
                        caption=f"IG: sir.say\nDone: {done} | Errors: {errors} | Target: @{username}",
                        reply_markup=create_process_buttons(paused.is_set())
                    )
                except Exception as e:
                    logger.error(f"Failed to update message: {e}")

                time.sleep(delay)

        # Restore original socket when reporting stops
        if proxy_setup:
            restore_original_socket()
        
        # Process stopped
        logger.info(f"🛑 Worker thread stopped for {username}")
        bot.send_message(chat_id, "Reporting stopped.")
        if chat_id in report_processes:
            del report_processes[chat_id]

    # 🚨 THIS WAS MISSING - START THE WORKER THREAD! 🚨
    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()
    logger.info(f"🚀 Started worker thread for {username}")

def start_custom_reporting_loop(chat_id: int, target_id: str, username: str, 
                              session_reports: Dict[str, List[str]], 
                              all_sessions: Dict[str, str], delay: int = 5):
    """Start custom reporting with specific sessions and report types."""
    done = 0
    errors = 0
    paused = threading.Event()
    stopped = threading.Event()

    # Setup SOCKS proxy before starting reports
    proxy_setup = setup_socks_proxy()

    # Send initial animation with controls
    gif_url = "https://raw.githubusercontent.com/rev-eng1/ThemeX/refs/heads/main/video_2025-06-27_16-39-43.gif"
    caption = f"IG: sir.say\nDone: {done} | Errors: {errors} | Target: @{username}"
    msg = bot.send_animation(
        chat_id, 
        gif_url, 
        caption=caption, 
        reply_markup=create_process_buttons(False)
    )
    
    # Store process info
    report_processes[chat_id] = {
        "paused": paused,
        "stopped": stopped,
        "msg_id": msg.message_id,
        "username": username,
        "done": done,
        "errors": errors,
        "proxy_active": proxy_setup
    }

    def worker():
        nonlocal done, errors
        report_index = 0
        
        while not stopped.is_set():
            for session_name, report_types_list in session_reports.items():
                if stopped.is_set():
                    break
                    
                session_id = all_sessions.get(session_name)
                if not session_id:
                    continue
                
                # Get current report type
                current_report_name = report_types_list[report_index % len(report_types_list)]
                current_report_id = next(
                    (r["id"] for r in REPORT_TYPES if r["name"] == current_report_name), 
                    "1"
                )
                
                # Handle pause state
                while paused.is_set():
                    time.sleep(1)
                    if stopped.is_set():
                        break
                
                if stopped.is_set():
                    break
                
                # Send report
                status = send_report(session_id, "1", target_id, current_report_id)
                if status == 200:
                    done += 1
                else:
                    errors += 1
                
                # Update process info
                report_processes[chat_id].update({
                    "done": done,
                    "errors": errors
                })
                
                # Update message (non-blocking)
                try:
                    bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=msg.message_id,
                        caption=f"IG: sir.say\nDone: {done} | Errors: {errors} | Target: @{username}",
                        reply_markup=create_process_buttons(paused.is_set())
                    )
                except Exception:
                    pass
                
                time.sleep(delay)
            
            report_index += 1
        
        # Restore original socket when reporting stops
        if proxy_setup:
            restore_original_socket()
        
        # Process stopped
        bot.send_message(chat_id, "Custom reporting stopped.")
        if chat_id in report_processes:
            del report_processes[chat_id]

    # Start worker thread
    threading.Thread(target=worker, daemon=True).start()

# === Message Handlers ===
@bot.message_handler(func=lambda message: message.from_user.id in BANNED_USERS)
def block_banned_users(message):
    """Block all messages from banned users."""
    bot.send_message(message.chat.id, "You are banned.")

@bot.callback_query_handler(func=lambda call: call.from_user.id in BANNED_USERS)
def block_banned_callbacks(call):
    """Block all callbacks from banned users."""
    bot.answer_callback_query(call.id, "You are banned.")

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Handle the /start command."""
    user_id = message.from_user.id

    # Add new user to ALL_USERS if not exists
    if user_id not in ALL_USERS:
        ALL_USERS[user_id] = {
            "chat_id": message.chat.id,
            "username_tg": message.from_user.username or "N/A",
            "first_name": message.from_user.first_name or "N/A",
            "join_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_all_users()

    if user_id in BANNED_USERS:
        bot.send_message(user_id, "You are banned.")
        return

    # Check if user has access
    if not is_user_approved(user_id):
        bot.send_message(user_id, "⚠️ Access Required\n\nYou need approval to use this bot.")
        return

    # Create admin keyboard if admin
    markup = None
    if user_id == ADMIN_CHAT_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Admin"))

    # Send welcome message
    welcome_text = (
        "🎯 **Instagram Reporter Bot**\n\n"
        "**Available Commands:**\n"
        "• `/create_session` - Add new sessions\n"
        "• `/session_list` - View your sessions\n"
        "• `/remove_session` - Remove sessions\n"
        "• `/report` - Start reporting"
    )
    
    bot.send_message(user_id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['create_session'])
@require_access
def handle_create_session(message):
    """Handle session creation with fast validation."""
    chat_id = message.chat.id
    user_state[chat_id] = {
        "mode": "collecting_sessions",
        "sessions": []
    }
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Done", callback_data="finish_sessions"))
    
    bot.send_message(
        chat_id, 
        "📝 **Add Sessions**\n\nSend your Instagram sessions (1 per message).\nClick 'Done' when finished.",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("mode") == "collecting_sessions")
def collect_sessions(message):
    """Collect sessions from user."""
    chat_id = message.chat.id
    session_id = message.text.strip()
    
    if session_id and len(session_id) > 20:
        user_state[chat_id]["sessions"].append(session_id)
        count = len(user_state[chat_id]["sessions"])
        bot.send_message(chat_id, f"✅ Session {count} received.")
    else:
        bot.send_message(chat_id, "❌ Invalid session format.")

@bot.callback_query_handler(func=lambda call: call.data == "finish_sessions")
def finish_session_collection(call):
    """Finish session collection with async validation."""
    chat_id = call.message.chat.id
    sessions = user_state.get(chat_id, {}).get("sessions", [])
    
    if not sessions:
        bot.answer_callback_query(call.id, "No sessions to validate!")
        return
    
    # Delete original message
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass
    
    # Show progress message
    progress_msg = bot.send_message(
        chat_id, 
        f"🔄 **Validating {len(sessions)} sessions...**\n\n📊 Progress: 0/{len(sessions)}",
        parse_mode="Markdown"
    )
    
    # Start async validation
    executor.submit(validate_sessions_async, chat_id, sessions, progress_msg.message_id)

@bot.message_handler(commands=['session_list'])
@require_access
def handle_session_list(message):
    """Show all saved sessions for a user."""
    sessions = get_user_sessions(message.chat.id)
    if not sessions:
        bot.send_message(message.chat.id, "No sessions saved.")
    else:
        msg = f"**Your sessions ({len(sessions)}):**\n"
        for i, (name, sess) in enumerate(sessions.items(), 1):
            msg += f"{i}. {name}: `{sess[:20]}...`\n"
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['report'])
@require_access
def handle_report(message):
    """Show report options."""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📱 Single Session", callback_data="report_single"),
        InlineKeyboardButton("📱📱 Multi Session", callback_data="report_multi")
    )
    markup.add(
        InlineKeyboardButton("🔧 Custom Session", callback_data="report_custom")
    )
    
    bot.send_message(
        message.chat.id,
        "🎯 **Select Report Mode:**",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data in ["report_single", "report_multi", "report_custom"])
def handle_report_mode(call):
    """Handle report mode selection."""
    chat_id = call.message.chat.id
    sessions = get_user_sessions(chat_id)
    
    if not sessions:
        bot.edit_message_text(
            "❌ No sessions found. Use /create_session first.",
            chat_id=chat_id,
            message_id=call.message.message_id
        )
        return
    
    if call.data == "report_single":
        # Show session selection for single mode
        markup = InlineKeyboardMarkup()
        for name in list(sessions.keys())[:10]:  # Limit to 10 for better performance
            markup.add(InlineKeyboardButton(name, callback_data=f"single_select:{name}"))
        
        bot.edit_message_text(
            "📱 **Select a session:**",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    elif call.data == "report_multi":
        # Multi session mode
        user_state[chat_id] = {"mode": "multi_setup"}
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🎯 One Report Type", callback_data="multi_one_report"),
            InlineKeyboardButton("🔄 Multiple Reports", callback_data="multi_change_reports")
        )
        
        bot.edit_message_text(
            "📱📱 **Multi-Session Mode:**",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    elif call.data == "report_custom":
        # Custom session mode
        user_state[chat_id] = {
            "mode": "custom_session_setup",
            "session_reports": {},
            "stage": "selecting_sessions"
        }
        
        markup = InlineKeyboardMarkup()
        for session_name in list(sessions.keys())[:8]:  # Limit to 8 for performance
            markup.add(InlineKeyboardButton(
                f"📱 {session_name}", 
                callback_data=f"custom_session_select:{session_name}"
            ))
        
        markup.add(InlineKeyboardButton("✅ Done", callback_data="custom_session_done"))
        
        bot.edit_message_text(
            "🔧 **Custom Session Setup**\n\nSelect sessions to configure their report types:",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("single_select:"))
def handle_single_session_select(call):
    """Handle single session selection."""
    chat_id = call.message.chat.id
    session_name = call.data.split(":", 1)[1]
    
    user_state[chat_id] = {
        "mode": "single_session",
        "session": session_name
    }
    
    markup = InlineKeyboardMarkup()
    # Show ALL report types for single session
    for report in REPORT_TYPES:
        markup.add(InlineKeyboardButton(report["name"], callback_data=f"report_type:{report['id']}"))
    
    bot.edit_message_text(
        f"📱 **Session:** {session_name}\n\n🎯 **Select report type:**",
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("report_type:"))
def handle_report_type_select(call):
    """Handle report type selection for single session."""
    chat_id = call.message.chat.id
    report_id = call.data.split(":", 1)[1]
    
    user_state[chat_id]["report_id"] = report_id
    user_state[chat_id]["stage"] = "awaiting_target"
    
    # Get report name for display
    report_name = next((r["name"] for r in REPORT_TYPES if r["id"] == report_id), "Unknown")
    
    bot.edit_message_text(
        f"✅ **Selected:** {report_name}\n\n🎯 **Target Setup**\n\nSend the Instagram username to target:",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )

# === Additional Report Handlers ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("multi_report:"))
def handle_multi_report_select(call):
    """Handle multi-session report type selection."""
    chat_id = call.message.chat.id
    report_id = call.data.split(":", 1)[1]
    
    user_state[chat_id]["report_id"] = report_id
    user_state[chat_id]["stage"] = "awaiting_target"
    
    # Get report name for display
    report_name = next((r["name"] for r in REPORT_TYPES if r["id"] == report_id), "Unknown")
    
    bot.edit_message_text(
        f"✅ **Selected:** {report_name}\n\n🎯 **Multi-Session Target**\n\nSend the Instagram username to target:",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data in ["multi_one_report", "multi_change_reports"])
def handle_multi_report_mode(call):
    """Handle multi-session report mode selection."""
    chat_id = call.message.chat.id
    
    if call.data == "multi_one_report":
        user_state[chat_id]["multi_mode"] = "one_report"
        
        markup = InlineKeyboardMarkup()
        # Show ALL report types for multi-session
        for report in REPORT_TYPES:
            markup.add(InlineKeyboardButton(report["name"], callback_data=f"multi_report:{report['id']}"))
        
        bot.edit_message_text(
            "🎯 **Select report type for all sessions:**",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        # Multi report mode - cycles through ALL report types
        user_state[chat_id]["multi_mode"] = "multi_reports"
        user_state[chat_id]["stage"] = "awaiting_target"
        
        bot.edit_message_text(
            "🔄 **Multi-Report Mode**\n\n📋 Will cycle through ALL report types\n\n🎯 Send the Instagram username to target:",
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "awaiting_target")
def handle_target_input(message):
    """Handle target username input for single and multi sessions."""
    chat_id = message.chat.id
    username = message.text.strip().replace("@", "")
    
    # Quick response
    bot.send_message(chat_id, f"🔍 Looking up @{username}...")
    
    # Get target ID in background
    def lookup_and_continue():
        target_id = get_target_user_id(username)
        if not target_id:
            bot.send_message(chat_id, "❌ User not found.")
            return
        
        # Store target info
        user_state[chat_id]["target_id"] = target_id
        user_state[chat_id]["target_username"] = username
        user_state[chat_id]["stage"] = "awaiting_delay"
        
        # Ask for delay
        bot.send_message(
            chat_id, 
            f"✅ **Found @{username}**\n\n⏱ Send delay between reports (5-100 seconds):",
            parse_mode="Markdown"
        )
    
    # Run in background
    executor.submit(lookup_and_continue)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "awaiting_delay")
def handle_delay_input(message):
    """Handle delay input for single and multi sessions."""
    chat_id = message.chat.id
    try:
        delay = int(message.text.strip())
        if not (5 <= delay <= 100):
            raise ValueError
    except ValueError:
        bot.send_message(chat_id, "❌ Invalid input. Please enter a number between 5 and 100:")
        return

    # Store delay
    user_state[chat_id]["delay"] = delay
    
    # Get stored values
    mode = user_state[chat_id].get("mode")
    target_id = user_state[chat_id]["target_id"]
    username = user_state[chat_id]["target_username"]
    sessions = get_user_sessions(chat_id)
    
    if not sessions:
        bot.send_message(chat_id, "❌ No sessions found.")
        user_state[chat_id] = {}
        return

    bot.send_message(chat_id, f"🚀 **Starting reporting...**\n\n⏱ Delay: {delay}s\n🎯 Target: @{username}", parse_mode="Markdown")

    # Debug print to see what mode we're in
    logger.info(f"Mode: {mode}, Multi-mode: {user_state[chat_id].get('multi_mode')}")

    if mode == "single_session":
        # Single session reporting
        session_name = user_state[chat_id]["session"]
        report_id = user_state[chat_id]["report_id"]
        single_session = {session_name: sessions[session_name]}
        logger.info(f"Starting single session: {session_name}, report: {report_id}")
        start_reporting_loop(chat_id, target_id, username, report_id, single_session, delay=delay)
        
    elif mode == "multi_setup":
        multi_mode = user_state[chat_id].get("multi_mode")
        
        if multi_mode == "one_report":
            # Multi session with one report type
            report_id = user_state[chat_id]["report_id"]
            logger.info(f"Starting multi session with one report: {report_id}")
            start_reporting_loop(chat_id, target_id, username, report_id, sessions, delay=delay)
            
        elif multi_mode == "multi_reports":
            # Multi session with multiple report types (cycling through all)
            all_report_names = [r["name"] for r in REPORT_TYPES]
            logger.info(f"Starting multi session with multiple reports: {len(all_report_names)} types")
            start_reporting_loop(chat_id, target_id, username, "1", sessions, multi_reports=all_report_names, delay=delay)
        else:
            bot.send_message(chat_id, "❌ Invalid multi-session mode.")
            logger.error(f"Invalid multi_mode: {multi_mode}")
    else:
        bot.send_message(chat_id, "❌ Invalid reporting mode.")
        logger.error(f"Invalid mode: {mode}")
    
    # Clear user state
    user_state[chat_id] = {}

# === Process Control (Optimized) ===
@bot.callback_query_handler(func=lambda call: call.data in ("pause_process", "resume_process", "kill_process"))
def handle_process_control(call):
    """Handle process control - optimized for speed."""
    chat_id = call.message.chat.id
    process = report_processes.get(chat_id)

    if not process:
        bot.answer_callback_query(call.id, "No active process.")
        return

    # Quick acknowledgment
    bot.answer_callback_query(call.id)

    if call.data == "pause_process":
        process["paused"].set()
        new_markup = create_process_buttons(True)
    elif call.data == "resume_process":
        process["paused"].clear()
        new_markup = create_process_buttons(False)
    elif call.data == "kill_process":
        process["stopped"].set()
        if process.get("proxy_active", False):
            restore_original_socket()
        bot.send_message(chat_id, "🛑 Reporting stopped.")
        if chat_id in report_processes:
            del report_processes[chat_id]
        return

    # Update buttons (non-blocking)
    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=process["msg_id"],
            reply_markup=new_markup
        )
    except Exception:
        pass


# === Complete Admin Panel with Unban Feature ===

@bot.message_handler(func=lambda msg: msg.text == "Admin" and msg.from_user.id == ADMIN_CHAT_ID)
def admin_panel(message):
    """Show enhanced admin panel with all features."""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("👥 Users", callback_data="admin_users"),
        InlineKeyboardButton("✅ Approve", callback_data="admin_approve")
    )
    markup.add(
        InlineKeyboardButton("❌ Unapprove", callback_data="admin_unapprove"),
        InlineKeyboardButton("🚫 Ban", callback_data="admin_ban")
    )
    markup.add(
        InlineKeyboardButton("🔓 Unban", callback_data="admin_unban")
    )
    
    bot.send_message(
        ADMIN_CHAT_ID, 
        "🔧 Admin Panel\n\nSelect an action:", 
        reply_markup=markup
    )

# Also add the format_user_display function
def format_user_display(uid: int, max_length: int = 35) -> str:
    """Format user display with name and chat ID."""
    user_data = ALL_USERS.get(uid, {})
    username = user_data.get("username_tg", "N/A")
    first_name = user_data.get("first_name", "N/A")
    
    # Create display string
    if username != "N/A":
        display = f"{first_name} (@{username}) - {uid}"
    else:
        display = f"{first_name} - {uid}"
    
    # Truncate if too long for button
    if len(display) > max_length:
        if username != "N/A":
            display = f"@{username} - {uid}"
        else:
            display = f"{first_name[:10]}... - {uid}"
    
    return display


@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_CHAT_ID and call.data.startswith("admin_"))
def handle_admin_callback(call):
    """Handle admin callbacks - fixed version without syntax errors."""
    action = call.data
    chat_id = call.message.chat.id
    
    # Quick acknowledgment
    bot.answer_callback_query(call.id)

    if action == "admin_users":
        users_count = len([u for u in ALL_USERS if isinstance(u, int)])
        approved_count = len(APPROVED_USERS)
        banned_count = len(BANNED_USERS)
        pending_count = users_count - approved_count - banned_count - 1  # -1 for admin
        
        # Show detailed user breakdown
        user_breakdown = []
        user_breakdown.append(f"📊 Total Users: {users_count}")
        user_breakdown.append(f"✅ Approved: {approved_count}")
        user_breakdown.append(f"⏳ Pending: {pending_count}")
        user_breakdown.append(f"🚫 Banned: {banned_count}")
        
        # Show some recent users
        recent_users = list(ALL_USERS.items())[-5:]  # Last 5 users
        if recent_users:
            user_breakdown.append(f"\nRecent Users:")
            for uid, data in recent_users:
                if isinstance(uid, int):
                    status = get_user_status(uid)
                    username = data.get("username_tg", "N/A")
                    first_name = data.get("first_name", "N/A")
                    
                    status_emoji = {"Admin": "👑", "Approved": "✅", "Pending": "⏳", "BANNED": "🚫"}
                    emoji = status_emoji.get(status, "❓")
                    
                    user_breakdown.append(f"{emoji} {first_name} (@{username}) - {uid}")
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
        
        bot.edit_message_text(
            "\n".join(user_breakdown),
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    elif action == "admin_approve":
        pending_users = [uid for uid in ALL_USERS if isinstance(uid, int) and get_user_status(uid) == "Pending"]
        
        if not pending_users:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
            bot.edit_message_text(
                "✅ No pending users to approve.",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
            return

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Approve All", callback_data="admin_approve_all"))
        
        for uid in pending_users[:5]:  # Show max 5 for performance
            display = format_user_display(uid)
            markup.add(InlineKeyboardButton(
                f"✅ {display}", 
                callback_data=f"admin_approve_{uid}"
            ))
        
        if len(pending_users) > 5:
            markup.add(InlineKeyboardButton(f"... and {len(pending_users) - 5} more", callback_data="admin_approve_more"))
        
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
        
        bot.edit_message_text(
            f"✅ Approve Users ({len(pending_users)} pending):",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    elif action == "admin_unapprove":
        approved_users = [uid for uid in APPROVED_USERS if isinstance(uid, int) and uid != ADMIN_CHAT_ID]
        
        if not approved_users:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
            bot.edit_message_text(
                "❌ No approved users to unapprove.",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
            return

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Unapprove All", callback_data="admin_unapprove_all"))
        
        for uid in approved_users[:5]:  # Show max 5 for performance
            display = format_user_display(uid)
            markup.add(InlineKeyboardButton(
                f"❌ {display}", 
                callback_data=f"admin_unapprove_{uid}"
            ))
        
        if len(approved_users) > 5:
            markup.add(InlineKeyboardButton(f"... and {len(approved_users) - 5} more", callback_data="admin_unapprove_more"))
        
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
        
        bot.edit_message_text(
            f"❌ Unapprove Users ({len(approved_users)} approved):",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    elif action == "admin_ban":
        active_users = [uid for uid in ALL_USERS if isinstance(uid, int) and uid != ADMIN_CHAT_ID and uid not in BANNED_USERS]
        
        if not active_users:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
            bot.edit_message_text(
                "🚫 No users to ban.",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
            return

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚫 Ban All", callback_data="admin_ban_all"))
        
        for uid in active_users[:5]:  # Show max 5 for performance
            display = format_user_display(uid)
            markup.add(InlineKeyboardButton(
                f"🚫 {display}", 
                callback_data=f"admin_ban_{uid}"
            ))
        
        if len(active_users) > 5:
            markup.add(InlineKeyboardButton(f"... and {len(active_users) - 5} more", callback_data="admin_ban_more"))
        
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
        
        bot.edit_message_text(
            f"🚫 Ban Users ({len(active_users)} active):",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    elif action == "admin_unban":
        banned_users = [uid for uid in BANNED_USERS if isinstance(uid, int)]
        
        if not banned_users:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
            bot.edit_message_text(
                "🔓 No banned users to unban.",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
            return

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔓 Unban All", callback_data="admin_unban_all"))
        
        for uid in banned_users[:5]:  # Show max 5 for performance
            display = format_user_display(uid)
            markup.add(InlineKeyboardButton(
                f"🔓 {display}", 
                callback_data=f"admin_unban_{uid}"
            ))
        
        if len(banned_users) > 5:
            markup.add(InlineKeyboardButton(f"... and {len(banned_users) - 5} more", callback_data="admin_unban_more"))
        
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
        
        bot.edit_message_text(
            f"🔓 Unban Users ({len(banned_users)} banned):",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    # Handle Approve Actions
    elif action.startswith("admin_approve_"):
        if action == "admin_approve_all":
            pending_users = [uid for uid in ALL_USERS if isinstance(uid, int) and get_user_status(uid) == "Pending"]
            success_count = 0
            for uid in pending_users:
                if uid not in APPROVED_USERS:
                    APPROVED_USERS.append(uid)
                    success_count += 1
                    try:
                        bot.send_message(uid, "✅ You have been approved! Use /start to begin.")
                    except Exception:
                        pass
            save_approved_users()
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
            bot.edit_message_text(
                f"✅ Approved {success_count} users successfully.",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        else:
            uid = int(action.split("_")[-1])
            if uid not in APPROVED_USERS:
                APPROVED_USERS.append(uid)
                save_approved_users()
                display = format_user_display(uid)
                try:
                    bot.send_message(uid, "✅ You have been approved! Use /start to begin.")
                except Exception:
                    pass
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_approve"))
            bot.edit_message_text(
                f"✅ User approved successfully:\n{display}",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )

    # Handle Unapprove Actions
    elif action.startswith("admin_unapprove_"):
        if action == "admin_unapprove_all":
            users_to_unapprove = list(APPROVED_USERS)  # Copy the list
            success_count = 0
            for uid in users_to_unapprove:
                if uid != ADMIN_CHAT_ID and uid in APPROVED_USERS:
                    APPROVED_USERS.remove(uid)
                    success_count += 1
                    try:
                        bot.send_message(uid, "❌ Your approval has been revoked. Contact admin for re-approval.")
                    except Exception:
                        pass
            save_approved_users()
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
            bot.edit_message_text(
                f"❌ Unapproved {success_count} users successfully.",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        else:
            uid = int(action.split("_")[-1])
            if uid in APPROVED_USERS and uid != ADMIN_CHAT_ID:
                APPROVED_USERS.remove(uid)
                save_approved_users()
                display = format_user_display(uid)
                try:
                    bot.send_message(uid, "❌ Your approval has been revoked. Contact admin for re-approval.")
                except Exception:
                    pass
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_unapprove"))
            bot.edit_message_text(
                f"❌ User unapproved successfully:\n{display}",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )

    # Handle Ban Actions
    elif action.startswith("admin_ban_"):
        if action == "admin_ban_all":
            users_to_ban = [uid for uid in ALL_USERS if uid != ADMIN_CHAT_ID and uid not in BANNED_USERS]
            success_count = 0
            for uid in users_to_ban:
                if uid not in BANNED_USERS:
                    BANNED_USERS.append(uid)
                    success_count += 1
                if uid in APPROVED_USERS:
                    APPROVED_USERS.remove(uid)
                try:
                    bot.send_message(uid, "🚫 You have been banned.")
                except Exception:
                    pass
            save_banned_users()
            save_approved_users()
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
            bot.edit_message_text(
                f"🚫 Banned {success_count} users successfully.",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        else:
            uid = int(action.split("_")[-1])
            display = format_user_display(uid)
            if uid not in BANNED_USERS:
                BANNED_USERS.append(uid)
                save_banned_users()
            if uid in APPROVED_USERS:
                APPROVED_USERS.remove(uid)
                save_approved_users()
            try:
                bot.send_message(uid, "🚫 You have been banned.")
            except Exception:
                pass
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_ban"))
            bot.edit_message_text(
                f"🚫 User banned successfully:\n{display}",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )

    # Handle Unban Actions
    elif action.startswith("admin_unban_"):
        if action == "admin_unban_all":
            users_to_unban = list(BANNED_USERS)  # Copy the list
            success_count = 0
            for uid in users_to_unban:
                if uid in BANNED_USERS:
                    BANNED_USERS.remove(uid)
                    success_count += 1
                # Optionally add back to approved users
                if uid not in APPROVED_USERS and uid != ADMIN_CHAT_ID:
                    APPROVED_USERS.append(uid)
                try:
                    bot.send_message(uid, "🔓 You have been unbanned! Use /start to begin.")
                except Exception:
                    pass
            save_banned_users()
            save_approved_users()
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back"))
            bot.edit_message_text(
                f"🔓 Unbanned {success_count} users successfully.",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        else:
            uid = int(action.split("_")[-1])
            display = format_user_display(uid)
            if uid in BANNED_USERS:
                BANNED_USERS.remove(uid)
                save_banned_users()
            # Optionally add back to approved users
            if uid not in APPROVED_USERS and uid != ADMIN_CHAT_ID:
                APPROVED_USERS.append(uid)
                save_approved_users()
            try:
                bot.send_message(uid, "🔓 You have been unbanned! Use /start to begin.")
            except Exception:
                pass
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_unban"))
            bot.edit_message_text(
                f"🔓 User unbanned successfully:\n{display}",
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )

    elif action == "admin_back":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("👥 Users", callback_data="admin_users"),
            InlineKeyboardButton("✅ Approve", callback_data="admin_approve")
        )
        markup.add(
            InlineKeyboardButton("❌ Unapprove", callback_data="admin_unapprove"),
            InlineKeyboardButton("🚫 Ban", callback_data="admin_ban")
        )
        markup.add(
            InlineKeyboardButton("🔓 Unban", callback_data="admin_unban")
        )
        
        bot.edit_message_text(
            "🔧 Admin Panel\n\nSelect an action:",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

# Optional: Add command to view all users with details
@bot.message_handler(commands=['users'])
def handle_users_command(message):
    """Show detailed user list (admin only)."""
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    
    user_list = []
    user_list.append("👥 All Users:\n")
    
    for uid, data in ALL_USERS.items():
        if isinstance(uid, int):
            status = get_user_status(uid)
            username = data.get("username_tg", "N/A")
            first_name = data.get("first_name", "N/A")
            join_date = data.get("join_date", "N/A")
            
            status_emoji = {"Admin": "👑", "Approved": "✅", "Pending": "⏳", "BANNED": "🚫"}
            emoji = status_emoji.get(status, "❓")
            
            user_list.append(f"{emoji} {first_name} (@{username})")
            user_list.append(f"   ID: {uid} | Joined: {join_date}")
            user_list.append("")
    
    # Split into chunks if too long
    text = "\n".join(user_list)
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            bot.send_message(message.chat.id, chunk)
    else:
        bot.send_message(message.chat.id, text)

# === Custom Session Handlers ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("custom_session_select:"))
def handle_custom_session_select(call):
    """Handle custom session selection for configuration."""
    chat_id = call.message.chat.id
    session_name = call.data.split(":", 1)[1]
    
    # Store current session being configured
    user_state[chat_id]["current_session"] = session_name
    user_state[chat_id]["stage"] = "selecting_reports"
    
    # Initialize empty report list for this session if not exists
    if session_name not in user_state[chat_id]["session_reports"]:
        user_state[chat_id]["session_reports"][session_name] = []
    
    # Show report type selection
    show_custom_session_reports(chat_id, session_name, call.message.message_id)

def show_custom_session_reports(chat_id: int, session_name: str, message_id: int):
    """Show report type selection for a custom session."""
    selected_reports = user_state[chat_id]["session_reports"].get(session_name, [])
    
    markup = InlineKeyboardMarkup()
    
    # Add "All" button
    all_selected = len(selected_reports) == len(REPORT_TYPES)
    all_text = "✅ All Selected" if all_selected else "📋 Select All"
    markup.add(InlineKeyboardButton(all_text, callback_data="custom_report_all"))
    
    # Add ALL individual report buttons
    for report in REPORT_TYPES:  # Show ALL report types, not limited
        is_selected = report["name"] in selected_reports
        button_text = f"✅ {report['name']}" if is_selected else f"📋 {report['name']}"
        markup.add(InlineKeyboardButton(
            button_text, 
            callback_data=f"custom_report_{report['name']}"
        ))
    
    # Add navigation buttons
    markup.add(
        InlineKeyboardButton("← Back", callback_data="custom_session_back"),
        InlineKeyboardButton("💾 Save", callback_data="custom_session_save")
    )
    
    selected_text = f"Selected: {len(selected_reports)}/{len(REPORT_TYPES)}" if selected_reports else f"Selected: 0/{len(REPORT_TYPES)}"
    
    try:
        bot.edit_message_text(
            f"🔧 **Configure: {session_name}**\n\n{selected_text}\n\nSelect report types:",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("custom_report_"))
def handle_custom_report_selection(call):
    """Handle custom report type selection."""
    chat_id = call.message.chat.id
    action = call.data.replace("custom_report_", "")
    session_name = user_state[chat_id]["current_session"]
    selected_reports = user_state[chat_id]["session_reports"][session_name]
    
    # Quick acknowledgment
    bot.answer_callback_query(call.id)
    
    if action == "all":
        # Toggle all reports
        if len(selected_reports) == len(REPORT_TYPES):
            # If all selected, clear all
            user_state[chat_id]["session_reports"][session_name] = []
        else:
            # If not all selected, select all
            user_state[chat_id]["session_reports"][session_name] = [r["name"] for r in REPORT_TYPES]
    else:
        # Toggle individual report
        if action in selected_reports:
            selected_reports.remove(action)
        else:
            selected_reports.append(action)
    
    # Refresh the display
    show_custom_session_reports(chat_id, session_name, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "custom_session_save")
def handle_custom_session_save(call):
    """Save custom session configuration."""
    chat_id = call.message.chat.id
    
    # Go back to session selection
    user_state[chat_id]["stage"] = "selecting_sessions"
    show_custom_session_list(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "custom_session_back")  
def handle_custom_session_back(call):
    """Go back from report selection to session selection."""
    chat_id = call.message.chat.id
    user_state[chat_id]["stage"] = "selecting_sessions"
    show_custom_session_list(chat_id, call.message.message_id)

def show_custom_session_list(chat_id: int, message_id: int):
    """Show the list of custom sessions."""
    sessions = get_user_sessions(chat_id)
    session_reports = user_state[chat_id]["session_reports"]
    
    markup = InlineKeyboardMarkup()
    
    for session_name in list(sessions.keys())[:8]:  # Limit to 8 for performance
        # Show session with report count
        report_count = len(session_reports.get(session_name, []))
        status = f"({report_count})" if report_count > 0 else "(0)"
        button_text = f"📱 {session_name} {status}"
        
        markup.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"custom_session_select:{session_name}"
        ))
    
    markup.add(InlineKeyboardButton("✅ Done", callback_data="custom_session_done"))
    
    try:
        bot.edit_message_text(
            "🔧 **Custom Session Setup**\n\nSelect sessions to configure:",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "custom_session_done")
def handle_custom_session_done(call):
    """Finish custom session configuration."""
    chat_id = call.message.chat.id
    session_reports = user_state[chat_id]["session_reports"]
    
    # Filter out sessions with no reports selected
    active_sessions = {k: v for k, v in session_reports.items() if v}
    
    if not active_sessions:
        bot.answer_callback_query(call.id, "No sessions with reports selected!")
        return
    
    # Store the active configuration and move to delay input
    user_state[chat_id]["active_session_reports"] = active_sessions
    user_state[chat_id]["stage"] = "custom_awaiting_delay"
    
    # Show summary and ask for delay
    summary_lines = ["🔧 **Configuration Summary:**\n"]
    for session_name, reports in active_sessions.items():
        summary_lines.append(f"📱 {session_name}: {len(reports)} reports")
    
    summary_text = "\n".join(summary_lines)
    
    bot.edit_message_text(
        f"{summary_text}\n\n⏱ Send delay between reports (5-100 seconds):",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "custom_awaiting_delay")
def handle_custom_delay_input(message):
    """Handle delay input for custom reporting."""
    chat_id = message.chat.id
    try:
        delay = int(message.text.strip())
        if not (5 <= delay <= 100):
            raise ValueError
    except ValueError:
        bot.send_message(chat_id, "❌ Invalid input. Please enter a number between 5 and 100:")
        return
    
    user_state[chat_id]["delay"] = delay
    user_state[chat_id]["stage"] = "custom_awaiting_username"
    
    bot.send_message(chat_id, f"⏱ **Delay set to {delay} seconds.**\n\n🎯 Send target Instagram username:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "custom_awaiting_username")
def handle_custom_username_input(message):
    """Handle username input for custom reporting."""
    chat_id = message.chat.id
    username = message.text.strip().replace("@", "")
    
    # Quick response
    bot.send_message(chat_id, f"🔍 Looking up @{username}...")
    
    # Get target ID in background
    def lookup_and_start_custom():
        target_id = get_target_user_id(username)
        if not target_id:
            bot.send_message(chat_id, "❌ User not found.")
            return
        
        # Start custom reporting process
        active_session_reports = user_state[chat_id]["active_session_reports"]
        delay = user_state[chat_id]["delay"]
        sessions = get_user_sessions(chat_id)
        
        start_custom_reporting_loop(chat_id, target_id, username, active_session_reports, sessions, delay)
        
        # Clear user state
        user_state[chat_id] = {}
    
    # Run in background
    executor.submit(lookup_and_start_custom)
@bot.callback_query_handler(func=lambda call: call.data in ["multi_one_report", "multi_change_reports"])
def handle_multi_report_mode(call):
    """Handle multi-session report mode selection."""
    chat_id = call.message.chat.id
    
    if call.data == "multi_one_report":
        user_state[chat_id]["multi_mode"] = "one_report"
        
        markup = InlineKeyboardMarkup()
        # Show ALL report types for multi-session
        for report in REPORT_TYPES:
            markup.add(InlineKeyboardButton(report["name"], callback_data=f"multi_report:{report['id']}"))
        
        bot.edit_message_text(
            "🎯 **Select report type for all sessions:**",
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        # Multi report mode - simplified
        user_state[chat_id]["multi_mode"] = "multi_reports"
        user_state[chat_id]["stage"] = "awaiting_target"
        
        bot.edit_message_text(
            "🔄 **Multi-Report Mode**\n\nSend the Instagram username to target:",
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("multi_report:"))
def handle_multi_report_select(call):
    """Handle multi-session report type selection."""
    chat_id = call.message.chat.id
    report_id = call.data.split(":", 1)[1]
    
    user_state[chat_id]["report_id"] = report_id
    user_state[chat_id]["stage"] = "awaiting_target"
    
    bot.edit_message_text(
        "🎯 **Multi-Session Target**\n\nSend the Instagram username to target:",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )

# === Debug Command (Remove after testing) ===
@bot.message_handler(commands=['debug'])
@require_access
def handle_debug(message):
    """Debug command to check user state."""
    chat_id = message.chat.id
    state = user_state.get(chat_id, {})
    sessions = get_user_sessions(chat_id)
    
    debug_text = (
        f"🐛 **Debug Info:**\n\n"
        f"**User State:** {state}\n\n"
        f"**Sessions:** {len(sessions)} found\n"
        f"**Session Names:** {list(sessions.keys())}\n\n"
        f"**Current Stage:** {state.get('stage', 'None')}\n"
        f"**Mode:** {state.get('mode', 'None')}\n"
        f"**Multi-Mode:** {state.get('multi_mode', 'None')}"
    )
    
    bot.send_message(chat_id, debug_text, parse_mode="Markdown")

# === Error Handler ===
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    """Handle unknown messages."""
    if message.from_user.id in BANNED_USERS:
        return
    
    if not is_user_approved(message.from_user.id):
        bot.send_message(message.chat.id, "⚠️ You need approval to use this bot.")
        return
    
    # Check if user is in a state that expects input
    chat_id = message.chat.id
    if chat_id in user_state:
        state = user_state[chat_id]
        stage = state.get("stage")
        
        if stage == "awaiting_target":
            handle_target_input(message)
            return
        elif stage == "awaiting_delay":
            handle_delay_input(message)
            return
        elif stage == "custom_awaiting_delay":
            handle_custom_delay_input(message)
            return
        elif stage == "custom_awaiting_username":
            handle_custom_username_input(message)
            return
    
    bot.send_message(
        message.chat.id, 
        "❓ Unknown command. Use /start to see available commands.\n\n🐛 Use /debug to check your current state."
    )

# === Main ===
if __name__ == "__main__":
    # Load initial data
    load_initial_data()
    
    # Start bot
    logger.info("Starting optimized bot...")
    print("🚀 Instagram Reporter Bot - OPTIMIZED VERSION")
    print("⚡ Features:")
    print("   • Fast async session validation")
    print("   • Non-blocking admin controls") 
    print("   • Optimized callback handlers")
    print("   • Background processing")
    print("   • SOCKS proxy support")
    print("\n📊 Stats:")
    print(f"   • Users: {len(ALL_USERS)}")
    print(f"   • Approved: {len(APPROVED_USERS)}")
    print(f"   • Banned: {len(BANNED_USERS)}")
    print("\n🔧 Requirements:")
    print("   • pip install PySocks requests pyTelegramBotAPI")
    print("   • Tor running on 127.0.0.1:9050 (optional)")
    print("\n✅ Bot is ready and optimized!")
    
    bot.infinity_polling(none_stop=True)
