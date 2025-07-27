import os
import json
import logging
import threading
import time
from typing import Dict, List, Set, Optional

import requests
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# === Configuration ===
TOKEN = '7502824448:AAElBY0QQvG-GCE7rbhu0SWWU7J9rnELdr8'  # Replace with your Bot token
ADMIN_CHAT_ID = 7850595240  # Replace with your admin Telegram ID
bot = TeleBot(TOKEN)

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
def save_banned_users():
    """Save banned users list."""
    save_json_file(BANNED_USERS_FILE, BANNED_USERS)

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

def send_report(sessionid: str, csrftoken: str, target_id: str, report_type_id: str) -> Optional[int]:
    """Send a report to Instagram."""
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
        
        response = requests.post(
            report_url,
            headers=headers,
            data=f'source_name=&reason_id={report_type_id}&frx_context=',
            allow_redirects=False,
            timeout=10
        )
        
        logger.info(f"Report sent. Status: {response.status_code}. Response: {response.text[:200]}")
        return response.status_code
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during report: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error sending report: {e}")
        return None

def create_process_buttons(paused_state: bool) -> InlineKeyboardMarkup:
    """Create control buttons for report processes."""
    markup = InlineKeyboardMarkup()
    button_text = "Resume" if paused_state else "⏸ Pause"
    callback_data = "resume_process" if paused_state else "pause_process"
    
    markup.add(
        InlineKeyboardButton(button_text, callback_data=callback_data),
        InlineKeyboardButton("Kill", callback_data="kill_process")
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
                "⚠️ Access Required\n\n"
                "You need approval to use this bot. Your request has been sent to the admin.\n"
                "Please wait for approval."
            )
            # Notify admin about new user request
            try:
                username = message.from_user.username or "N/A"
                bot.send_message(
                    ADMIN_CHAT_ID,
                    f"New Access Request\n\n"
                    f"User ID: {user_id}\n"
                    f"Username: @{username}\n"
                    f"Name: {message.from_user.first_name or 'N/A'}\n\n"
                    f"Use /admin to manage user access."
                )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")
            return
        
        return func(message)
    return wrapper

# === Reporting Functions ===
def start_reporting_loop(chat_id: int, target_id: str, username: str, report_id: str, 
                        sessions: Dict[str, str], multi_reports: List[str] = None, delay: int = 5):
    """Start the reporting process loop."""
    done = 0
    errors = 0
    paused = threading.Event()
    stopped = threading.Event()
    report_list = multi_reports or [report_id]
    index = 0

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
        "errors": errors
    }

    def worker():
        nonlocal done, errors, index
        while not stopped.is_set():
            for name, sess_id in sessions.items():
                if stopped.is_set():
                    break
                
                # Handle pause state
                while paused.is_set():
                    time.sleep(delay)

                # Determine current report type
                if multi_reports:
                    current_name = report_list[index % len(report_list)]
                    current_report_id = next(
                        (r["id"] for r in REPORT_TYPES if r["name"] == current_name), 
                        report_id
                    )
                    index += 1
                else:
                    current_report_id = report_id

                # Send report
                status = send_report(sess_id, "1", target_id, current_report_id)
                if status == 200:
                    done += 1
                else:
                    errors += 1

                # Update process info
                report_processes[chat_id].update({
                    "done": done,
                    "errors": errors
                })

                # Update message
                try:
                    bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=msg.message_id,
                        caption=f"IG: sir.say\nDone: {done} | Errors: {errors} | Target: @{username}",
                        reply_markup=create_process_buttons(paused.is_set())
                    )
                except Exception as e:
                    logger.error(f"Failed to edit message: {e}")

                time.sleep(delay)

        # Process stopped
        bot.send_message(chat_id, "Reporting stopped.")

    # Start worker thread
    threading.Thread(target=worker, daemon=True).start()

def start_custom_reporting_loop(chat_id: int, target_id: str, username: str, 
                              session_reports: Dict[str, List[str]], 
                              all_sessions: Dict[str, str], delay: int = 5):
    """Start custom reporting with specific sessions and report types."""
    done = 0
    errors = 0
    paused = threading.Event()
    stopped = threading.Event()

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
        "errors": errors
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
                
                # Update message
                try:
                    bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=msg.message_id,
                        caption=f"IG: sir.say\nDone: {done} | Errors: {errors} | Target: @{username}",
                        reply_markup=create_process_buttons(paused.is_set())
                    )
                except Exception as e:
                    logger.error(f"Failed to edit message: {e}")
                
                time.sleep(delay)
            
            report_index += 1
        
        # Process stopped
        bot.send_message(chat_id, "Custom reporting stopped.")

    # Start worker thread
    threading.Thread(target=worker, daemon=True).start()

# === Message Handlers ===
@bot.message_handler(func=lambda message: message.from_user.id in BANNED_USERS)
def block_banned_users(message):
    """Block all messages from banned users."""
    try:
        bot.send_message(message.chat.id, "You are banned and cannot use this bot.")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.from_user.id in BANNED_USERS)
def block_banned_callbacks(call):
    """Block all callbacks from banned users."""
    try:
        bot.answer_callback_query(call.id, "You are banned.")
    except Exception:
        pass

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
        
        # Notify admin about new user (if not admin themselves)
        if user_id != ADMIN_CHAT_ID:
            try:
                bot.send_message(
                    ADMIN_CHAT_ID,
                    f"🆕 New User Joined\n\n"
                    f"User ID: {user_id}\n"
                    f"Username: @{message.from_user.username or 'N/A'}\n"
                    f"Name: {message.from_user.first_name or 'N/A'}\n\n"
                    f"Status: {get_user_status(user_id)}\n\n"
                    f"Use the Admin button to manage user access."
                )
            except Exception as e:
                logger.error(f"Failed to notify admin about new user: {e}")

    if user_id in BANNED_USERS:
        bot.send_message(user_id, "You are banned.")
        return

    # Check if user has access
    if not is_user_approved(user_id):
        bot.send_message(
            user_id,
            "⚠️ Access Required\n\n"
            "You need approval to use this bot. Your request has been sent to the admin.\n"
            "Please wait for approval."
        )
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
        "• `/report` - Start reporting\n\n"
        "Choose a command to begin!"
    )
    
    bot.send_message(
        user_id,
        welcome_text,
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(commands=['create_session'])
@require_access
def handle_create_session(message):
    """Handle session creation."""
    chat_id = message.chat.id
    user_state[chat_id] = {
        "mode": "collecting_sessions",
        "sessions": []
    }
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Done", callback_data="finish_sessions"))
    
    bot.send_message(chat_id, "Send your sessions (1 session per message):", reply_markup=markup)

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("mode") == "collecting_sessions")
def collect_sessions(message):
    """Collect sessions from user."""
    chat_id = message.chat.id
    session_id = message.text.strip()
    
    if session_id:
        user_state[chat_id]["sessions"].append(session_id)
        bot.send_message(chat_id, "Session received.")

@bot.callback_query_handler(func=lambda call: call.data == "finish_sessions")
def finish_session_collection(call):
    """Finish session collection and validate sessions."""
    chat_id = call.message.chat.id
    sessions = user_state.get(chat_id, {}).get("sessions", [])
    
    valid = 0
    invalid = 0

    for session_id in sessions:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/accounts/edit/",
            "Cookie": f"sessionid={session_id};"
        }
        try:
            response = requests.get("https://www.instagram.com/accounts/edit/", headers=headers)
            if response.status_code == 200 and '"username":"' in response.text:
                username = response.text.split('"username":"')[1].split('"')[0]
                save_user_session(chat_id, username, session_id)
                valid += 1
            else:
                invalid += 1
        except Exception:
            invalid += 1

    bot.delete_message(chat_id, call.message.message_id)
    bot.send_message(chat_id, f"Done\nFound {valid} valid sessions\nExcluded {invalid} invalid sessions")
    user_state[chat_id] = {}

@bot.message_handler(commands=['session_list'])
@require_access
def handle_session_list(message):
    """Show all saved sessions for a user."""
    sessions = get_user_sessions(message.chat.id)
    if not sessions:
        bot.send_message(message.chat.id, "No sessions saved for your user.")
    else:
        msg = "Your sessions:\n"
        for name, sess in sessions.items():
            msg += f"• {name}: `{sess}`\n"
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['remove_session'])
@require_access
def handle_remove_session(message):
    """Handle session removal."""
    chat_id = message.chat.id
    sessions = get_user_sessions(chat_id)
    
    if not sessions:
        bot.send_message(chat_id, "No sessions found to remove.")
        return

    # Initialize remove session state
    user_state[chat_id] = {
        "mode": "remove_session",
        "sessions_to_remove": set(),
        "stage": "selecting_sessions"
    }
    
    # Show all available sessions for removal
    sent = bot.send_message(
        chat_id, 
        "**Remove Sessions**\n\nLoading sessions...",
        parse_mode="Markdown"
    )
    user_state[chat_id]["last_message_id"] = sent.message_id
    
    show_remove_session_list(chat_id)

def show_remove_session_list(chat_id: int):
    """Show the session removal interface."""
    sessions = get_user_sessions(chat_id)
    sessions_to_remove = user_state[chat_id]["sessions_to_remove"]
    
    markup = InlineKeyboardMarkup()
    
    for session_name in sessions:
        # Show session with checkmark if selected for removal
        is_selected = session_name in sessions_to_remove
        button_text = f"❌ {session_name}" if is_selected else f" {session_name}"
        
        markup.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"remove_session_toggle:{session_name}"
        ))
    
    # Add control buttons
    control_buttons = []
    if sessions_to_remove:
        control_buttons.append(InlineKeyboardButton("Remove Selected", callback_data="remove_session_confirm"))
    control_buttons.append(InlineKeyboardButton("Cancel", callback_data="remove_session_cancel"))
    
    if control_buttons:
        markup.add(*control_buttons)
    
    selected_count = len(sessions_to_remove)
    total_count = len(sessions)
    
    message_text = (
        f"**Remove Sessions**\n\n"
        f"Selected for removal: {selected_count}/{total_count}\n\n"
        f"Tap sessions to select/deselect for removal:"
    )
    
    # Try to edit existing message first
    if "last_message_id" in user_state[chat_id]:
        try:
            bot.edit_message_text(
                message_text,
                chat_id=chat_id,
                message_id=user_state[chat_id]["last_message_id"],
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
    
    # Send new message if edit fails
    sent = bot.send_message(
        chat_id,
        message_text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    user_state[chat_id]["last_message_id"] = sent.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_session_toggle:"))
def handle_remove_session_toggle(call):
    """Toggle session selection for removal."""
    chat_id = call.message.chat.id
    session_name = call.data.split(":", 1)[1]
    
    # Toggle session selection
    sessions_to_remove = user_state[chat_id]["sessions_to_remove"]
    if session_name in sessions_to_remove:
        sessions_to_remove.remove(session_name)
        bot.answer_callback_query(call.id, f"Deselected: {session_name}")
    else:
        sessions_to_remove.add(session_name)
        bot.answer_callback_query(call.id, f"Selected for removal: {session_name}")
    
    # Refresh the display
    show_remove_session_list(chat_id)

@bot.callback_query_handler(func=lambda call: call.data == "remove_session_confirm")
def handle_remove_session_confirm(call):
    """Confirm session removal."""
    chat_id = call.message.chat.id
    sessions_to_remove = user_state[chat_id]["sessions_to_remove"]
    
    if not sessions_to_remove:
        bot.answer_callback_query(call.id, "No sessions selected for removal!")
        return
    
    # Show confirmation dialog
    session_list = "\n".join([f"• {name}" for name in sessions_to_remove])
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Yes, Remove", callback_data="remove_session_execute"),
        InlineKeyboardButton("Cancel", callback_data="remove_session_back")
    )
    
    bot.edit_message_text(
        f"**Confirm Removal**\n\n"
        f"Are you sure you want to remove these sessions?\n\n"
        f"{session_list}\n\n"
        f"**This action cannot be undone!**",
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "remove_session_execute")
def handle_remove_session_execute(call):
    """Execute session removal."""
    chat_id = call.message.chat.id
    sessions_to_remove = user_state[chat_id]["sessions_to_remove"]
    
    # Remove selected sessions
    removed_count = delete_user_sessions(chat_id, list(sessions_to_remove))
    
    # Clear user state
    user_state[chat_id] = {}
    
    # Show success message
    remaining_sessions = get_user_sessions(chat_id)
    bot.edit_message_text(
        f"**Removal Complete**\n\n"
        f"Successfully removed {removed_count} sessions.\n\n"
        f"Remaining sessions: {len(remaining_sessions)}",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "remove_session_back")
def handle_remove_session_back(call):
    """Go back to session selection from confirmation."""
    chat_id = call.message.chat.id
    show_remove_session_list(chat_id)

@bot.callback_query_handler(func=lambda call: call.data == "remove_session_cancel")
def handle_remove_session_cancel(call):
    """Cancel session removal."""
    chat_id = call.message.chat.id
    
    # Clear user state
    user_state[chat_id] = {}
    
    bot.edit_message_text(
        "Session removal cancelled.",
        chat_id=chat_id,
        message_id=call.message.message_id
    )

@bot.message_handler(commands=['report'])
@require_access
def handle_report(message):
    """Show report options."""
    bot.send_message(
        message.chat.id,
        "Select report settings:\n\n"
        "/Single\\_session : report from single session ID\n"
        "/multi\\_session : report using multiple sessions on one target\n"
        "/custom\\_session : Adjust reporting session and their report type/s",  
        parse_mode="MarkdownV2"
    )

@bot.message_handler(commands=['single_session', 'Single_session'])
@require_access
def handle_single_session(message):
    """Handle single session report setup."""
    sessions = get_user_sessions(message.chat.id)
    if not sessions:
        bot.send_message(message.chat.id, "No sessions found.")
        return

    markup = InlineKeyboardMarkup()
    for name in sessions:
        markup.add(InlineKeyboardButton(text=name, callback_data=f"single_select:{name}"))

    sent = bot.send_message(message.chat.id, "Select a session to use:", reply_markup=markup)
    user_state[message.chat.id] = {"last_message_id": sent.message_id}

@bot.message_handler(commands=['multi_session', 'Multi_session'])
@require_access
def handle_multi_session(message):
    """Handle multi-session report setup."""
    chat_id = message.chat.id
    user_state[chat_id] = {"mode": "multi", "stage": "waiting_for_mode"}

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("One Report", callback_data="multi_one_report"),
        InlineKeyboardButton("Change Reports", callback_data="multi_change_reports")
    )

    sent = bot.send_message(chat_id, "Choose report mode:", reply_markup=markup)
    user_state[chat_id]["last_message_id"] = sent.message_id

@bot.message_handler(commands=['custom_session'])
@require_access
def handle_custom_session(message):
    """Handle custom session report setup."""
    chat_id = message.chat.id
    sessions = get_user_sessions(chat_id)
    
    if not sessions:
        bot.send_message(chat_id, "No sessions found. Use /create_session first to add sessions.")
        return

    # Initialize custom session state
    user_state[chat_id] = {
        "mode": "custom_session_setup",
        "session_reports": {},  # Will store {session_name: [report_types]}
        "stage": "selecting_sessions"
    }
    
    # Show all available sessions
    markup = InlineKeyboardMarkup()
    for session_name in sessions:
        markup.add(InlineKeyboardButton(
            text=session_name, 
            callback_data=f"custom_session_select:{session_name}"
        ))
    
    markup.add(InlineKeyboardButton("Done", callback_data="custom_session_done"))
    
    sent = bot.send_message(
        chat_id, 
        "📝 Custom Session Report Setup\n\nSelect a session to configure its report types:",
        reply_markup=markup
    )
    user_state[chat_id]["last_message_id"] = sent.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("custom_session_select:"))
def handle_custom_session_select(call):
    """Handle custom session selection for configuration."""
    chat_id = call.message.chat.id
    session_name = call.data.split(":")[1]
    
    # Store current session being configured
    user_state[chat_id]["current_session"] = session_name
    user_state[chat_id]["stage"] = "selecting_reports"
    
    # Initialize empty report list for this session if not exists
    if session_name not in user_state[chat_id]["session_reports"]:
        user_state[chat_id]["session_reports"][session_name] = []
    
    # Show report type selection
    show_custom_session_reports(chat_id, session_name)

def show_custom_session_reports(chat_id: int, session_name: str):
    """Show report type selection for a custom session."""
    selected_reports = user_state[chat_id]["session_reports"].get(session_name, [])
    
    markup = InlineKeyboardMarkup()
    
    # Add "All" button
    all_selected = len(selected_reports) == len(REPORT_TYPES)
    all_text = "All" if all_selected else "All"
    markup.add(InlineKeyboardButton(all_text, callback_data="custom_report_all"))
    
    # Add individual report buttons
    for report in REPORT_TYPES:
        is_selected = report["name"] in selected_reports
        button_text = f"{report['name']}" if is_selected else report["name"]
        markup.add(InlineKeyboardButton(
            button_text, 
            callback_data=f"custom_report_{report['name']}"
        ))
    
    # Add navigation buttons
    markup.add(
        InlineKeyboardButton("← Back", callback_data="custom_session_back"),
        InlineKeyboardButton("Save", callback_data="custom_session_save")
    )
    
    selected_text = f"Selected: {', '.join(selected_reports)}" if selected_reports else "No reports selected"
    
    try:
        bot.edit_message_text(
            f"Configure Reports for: {session_name}\n\n{selected_text}\n\nSelect report types:",
            chat_id=chat_id,
            message_id=user_state[chat_id]["last_message_id"],
            reply_markup=markup
        )
    except Exception:
        # If edit fails, send new message
        msg = bot.send_message(
            chat_id,
            f"Configure Reports for: {session_name}\n\n{selected_text}\n\nSelect report types:",
            reply_markup=markup
        )
        user_state[chat_id]["last_message_id"] = msg.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("custom_report_"))
def handle_custom_report_selection(call):
    """Handle custom report type selection."""
    chat_id = call.message.chat.id
    action = call.data.replace("custom_report_", "")
    session_name = user_state[chat_id]["current_session"]
    selected_reports = user_state[chat_id]["session_reports"][session_name]
    
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
    show_custom_session_reports(chat_id, session_name)

@bot.callback_query_handler(func=lambda call: call.data == "custom_session_save")
def handle_custom_session_save(call):
    """Save custom session configuration."""
    chat_id = call.message.chat.id
    session_name = user_state[chat_id]["current_session"]
    
    # Go back to session selection
    user_state[chat_id]["stage"] = "selecting_sessions"
    show_custom_session_list(chat_id)

@bot.callback_query_handler(func=lambda call: call.data == "custom_session_back")  
def handle_custom_session_back(call):
    """Go back from report selection to session selection."""
    chat_id = call.message.chat.id
    user_state[chat_id]["stage"] = "selecting_sessions"
    show_custom_session_list(chat_id)

def show_custom_session_list(chat_id: int):
    """Show the list of custom sessions."""
    sessions = get_user_sessions(chat_id)
    session_reports = user_state[chat_id]["session_reports"]
    
    markup = InlineKeyboardMarkup()
    
    for session_name in sessions:
        # Show session with report count
        report_count = len(session_reports.get(session_name, []))
        status = f"({report_count} reports)" if report_count > 0 else "(no reports)"
        button_text = f"{session_name} {status}"
        
        markup.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"custom_session_select:{session_name}"
        ))
    
    markup.add(InlineKeyboardButton("Done", callback_data="custom_session_done"))
    
    try:
        bot.edit_message_text(
            "Custom Session Report Setup\n\nSelect a session to configure its report types:",
            chat_id=chat_id,
            message_id=user_state[chat_id]["last_message_id"],
            reply_markup=markup
        )
    except Exception:
        msg = bot.send_message(
            chat_id,
            "Custom Session Report Setup\n\nSelect a session to configure its report types:",
            reply_markup=markup
        )
        user_state[chat_id]["last_message_id"] = msg.message_id

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
    summary_lines = [" Configuration Summary:\n"]
    for session_name, reports in active_sessions.items():
        summary_lines.append(f"• {session_name}: {', '.join(reports)}")
    
    summary_text = "\n".join(summary_lines)
    
    bot.edit_message_text(
        f"{summary_text}\n\n⏱ Send delay between reports (5-100 seconds):",
        chat_id=chat_id,
        message_id=call.message.message_id
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
        bot.send_message(chat_id, "Invalid input. Please enter a number between 5 and 100:")
        return
    
    user_state[chat_id]["delay"] = delay
    user_state[chat_id]["stage"] = "custom_awaiting_username"
    
    bot.send_message(chat_id, f"Delay set to {delay} seconds.\n\n Send target Instagram username:")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "custom_awaiting_username")
def handle_custom_username_input(message):
    """Handle username input for custom reporting."""
    chat_id = message.chat.id
    username = message.text.strip()
    
    bot.send_message(chat_id, f"Looking up @{username}...")
    target_id = get_target_user_id(username)
    
    if not target_id:
        bot.send_message(chat_id, "Could not retrieve Instagram user ID. Try again:")
        return
    
    # Start custom reporting process
    active_session_reports = user_state[chat_id]["active_session_reports"]
    delay = user_state[chat_id]["delay"]
    sessions = get_user_sessions(chat_id)
    
    start_custom_reporting_loop(chat_id, target_id, username, active_session_reports, sessions, delay)
    
    # Clear user state
    user_state[chat_id] = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("single_select:"))
def handle_single_selected(call):
    """Handle selection of a single session for reporting."""
    session_name = call.data.split(":")[1]
    chat_id = call.message.chat.id

    # Delete old message if exists
    old_msg_id = user_state.get(chat_id, {}).get("last_message_id")
    if old_msg_id:
        bot.delete_message(chat_id, old_msg_id)

    # Set user state
    user_state[chat_id] = {"mode": "single", "session": session_name}

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("One Report", callback_data="one_report"))
    markup.add(InlineKeyboardButton("Change Report", callback_data="change_report"))

    sent = bot.send_message(
        chat_id,
        f"Session `{session_name}` selected. Choose an action:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    user_state[chat_id]["last_message_id"] = sent.message_id

@bot.callback_query_handler(func=lambda call: call.data == "change_report")
def handle_change_report(call):
    """Handle change report type request."""
    chat_id = call.message.chat.id

    last_msg_id = user_state.get(chat_id, {}).get("last_message_id")
    if last_msg_id:
        bot.delete_message(chat_id, last_msg_id)

    user_state[chat_id]["mode"] = "single_change"
    user_state[chat_id]["stage"] = "selecting_reports"
    multi_report_selections[chat_id] = set()
    show_report_list(chat_id, single_select=False)

@bot.callback_query_handler(func=lambda call: call.data.startswith("multi_"))
def handle_multi_mode_selection(call):
    """Handle multi-session mode selection."""
    chat_id = call.message.chat.id
    mode = call.data

    # Delete old message if exists
    last_msg_id = user_state.get(chat_id, {}).get("last_message_id")
    if last_msg_id:
        bot.delete_message(chat_id, last_msg_id)

    if mode == "multi_one_report":
        user_state[chat_id]["mode"] = "multi_one"
        user_state[chat_id]["stage"] = "waiting_for_report_choice"
        show_report_list(chat_id, single_select=True)

    elif mode == "multi_change_reports":
        user_state[chat_id]["mode"] = "multi_change"
        user_state[chat_id]["stage"] = "selecting_reports"
        multi_report_selections[chat_id] = set()
        show_report_list(chat_id, single_select=False)

def show_report_list(chat_id: int, single_select: bool = True):
    """Show the report type selection list."""
    markup = InlineKeyboardMarkup()
    reports = [r["name"] for r in REPORT_TYPES]

    if not single_select:
        markup.add(InlineKeyboardButton("All", callback_data="report_all"))

    for report in reports:
        markup.add(InlineKeyboardButton(report, callback_data=f"report_{report}"))

    if not single_select:
        markup.add(InlineKeyboardButton("Done", callback_data="report_done"))

    sent = bot.send_message(chat_id, "Select report type(s):", reply_markup=markup)
    user_state[chat_id]["last_message_id"] = sent.message_id

@bot.callback_query_handler(func=lambda call: call.data == "one_report")
def handle_one_report(call):
    """Handle one report type selection."""
    chat_id = call.message.chat.id

    # Delete old message if exists
    last_msg_id = user_state.get(chat_id, {}).get("last_message_id")
    if last_msg_id:
        bot.delete_message(chat_id, last_msg_id)

    current_mode = user_state.get(chat_id, {}).get("mode")
    if current_mode == "multi":
        user_state[chat_id]["mode"] = "multi_one"
    else:
        user_state[chat_id]["mode"] = "single_one"

    user_state[chat_id]["stage"] = "waiting_for_report_choice"
    show_report_list(chat_id, single_select=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("report_"))
def handle_any_report_action(call):
    """Handle all report type selection actions."""
    chat_id = call.message.chat.id
    data = call.data
    mode = user_state.get(chat_id, {}).get("mode")
    report_type = data[len("report_"):]

    if report_type == "done":
        if mode in ("multi_change", "single_change"):
            selected = multi_report_selections.get(chat_id, set())
            if not selected:
                bot.answer_callback_query(call.id, "Select at least one report.")
                return

            selected_list = list(selected)
            user_state[chat_id]["selected_reports"] = selected_list
            user_state[chat_id]["use_all"] = False
            user_state[chat_id]["stage"] = "awaiting_username"
            bot.delete_message(chat_id, call.message.message_id)

            formatted = " , ".join(selected_list)
            bot.send_message(chat_id, f"Selected types: {formatted}")
            bot.send_message(chat_id, " Send target Instagram username:")
            return

    elif report_type == "all":
        all_reports = [r["name"] for r in REPORT_TYPES]
        multi_report_selections[chat_id] = set(all_reports)
        user_state[chat_id]["use_all"] = True
        user_state[chat_id]["selected_reports"] = all_reports
        user_state[chat_id]["stage"] = "awaiting_username"

        bot.edit_message_text(
            "All report types selected.\n Send target Instagram username:",
            chat_id=chat_id,
            message_id=call.message.message_id
        )
        return

    elif report_type in [r["name"] for r in REPORT_TYPES]:
        if mode in ("multi_change", "single_change"):
            selected = multi_report_selections.setdefault(chat_id, set())
            if report_type in selected:
                selected.remove(report_type)
                bot.answer_callback_query(call.id, f"Unselected: {report_type}")
            else:
                selected.add(report_type)
                bot.answer_callback_query(call.id, f"Selected: {report_type}")
            return

        elif mode in ("multi_one", "single_one"):
            user_state[chat_id]["selected_report"] = report_type
            user_state[chat_id]["stage"] = "awaiting_username"
            bot.delete_message(chat_id, call.message.message_id)
            bot.send_message(chat_id, f"Selected type: {report_type}")
            bot.send_message(chat_id, " Send target Instagram username:")
            return

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "awaiting_username")
def handle_username_input(message):
    """Handle target username input."""
    chat_id = message.chat.id
    username = message.text.strip()

    bot.send_message(chat_id, f"🔍 Looking up `@{username}`...", parse_mode="Markdown")
    target_id = get_target_user_id(username)

    if not target_id:
        bot.send_message(chat_id, "Could not retrieve Instagram user ID.")
        return

    user_state[chat_id]["target_id"] = target_id
    user_state[chat_id]["target_username"] = username
    user_state[chat_id]["stage"] = "awaiting_delay"

    bot.send_message(chat_id, "Found user.\n\n Choose delay between reports (5–100 seconds):")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "awaiting_delay")
def handle_delay_input(message):
    """Handle delay between reports input."""
    chat_id = message.chat.id
    try:
        delay = int(message.text.strip())
        if not (5 <= delay <= 100):
            raise ValueError
    except ValueError:
        bot.send_message(chat_id, "Invalid input. Please enter a number between 5 and 100:")
        return

    user_state[chat_id]["delay"] = delay
    user_state[chat_id]["stage"] = None

    mode = user_state[chat_id].get("mode")
    sessions = get_user_sessions(chat_id)
    target_id = user_state[chat_id]["target_id"]
    username = user_state[chat_id]["target_username"]

    if not sessions:
        bot.send_message(chat_id, "No sessions found.")
        return

    if mode == "single_one":
        report_name = user_state[chat_id].get("selected_report")
        session_name = user_state[chat_id].get("session")
        session_id = sessions.get(session_name)
        report_id = next((r["id"] for r in REPORT_TYPES if r["name"] == report_name), None)

        if session_id and report_id:
            start_reporting_loop(chat_id, target_id, username, report_id, {session_name: session_id}, delay=delay)

    elif mode == "multi_one":
        report_name = user_state[chat_id].get("selected_report")
        report_id = next((r["id"] for r in REPORT_TYPES if r["name"] == report_name), None)

        if report_id:
            start_reporting_loop(chat_id, target_id, username, report_id, sessions, delay=delay)

    elif mode == "multi_change":
        selected_reports = user_state[chat_id].get("selected_reports", [])
        if selected_reports:
            start_reporting_loop(chat_id, target_id, username, "1", sessions, multi_reports=selected_reports, delay=delay)

    elif mode == "single_change":
        selected_reports = user_state[chat_id].get("selected_reports", [])
        session_name = user_state[chat_id].get("session")
        session_id = sessions.get(session_name)

        if session_id and selected_reports:
            first_report_id = next((r["id"] for r in REPORT_TYPES if r["name"] == selected_reports[0]), "1")
            start_reporting_loop(
                chat_id,
                target_id,
                username,
                report_id=first_report_id,
                sessions={session_name: session_id},
                multi_reports=selected_reports,
                delay=delay
            )

@bot.callback_query_handler(func=lambda call: call.data in ("pause_process", "resume_process", "kill_process"))
def handle_process_control(call):
    """Handle report process control commands (pause/resume/kill)."""
    chat_id = call.message.chat.id
    process = report_processes.get(chat_id)

    if not process:
        bot.answer_callback_query(call.id, "No active process.")
        return

    paused = process["paused"]
    stopped = process["stopped"]
    msg_id = process["msg_id"]
    username = process["username"]
    done = process["done"]
    errors = process["errors"]

    if call.data == "pause_process":
        paused.set()
        button_text = "Resume"
        callback_data = "resume_process"
        bot.answer_callback_query(call.id, "Paused")

    elif call.data == "resume_process":
        paused.clear()
        button_text = "⏸ Pause"
        callback_data = "pause_process"
        bot.answer_callback_query(call.id, "Resumed")

    elif call.data == "kill_process":
        stopped.set()
        bot.answer_callback_query(call.id, "Killed")

        try:
            bot.edit_message_caption(
                chat_id=chat_id,
                message_id=msg_id,
                caption=f"Reporting stopped.\nIG: sir.say\nDone: {done} | Errors: {errors} | Target: @{username}"
            )
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
        bot.send_message(chat_id, "Reporting stopped.")
        del report_processes[chat_id]
        return

    # Update message with new buttons
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(button_text, callback_data=callback_data),
        InlineKeyboardButton("Kill", callback_data="kill_process")
    )

    try:
        bot.edit_message_caption(
            chat_id=chat_id,
            message_id=msg_id,
            caption=f"IG: sir.say\nDone: {done} | Errors: {errors} | Target: @{username}",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")

# === Admin Functions ===

@bot.message_handler(func=lambda msg: msg.text == "Admin" and msg.from_user.id == ADMIN_CHAT_ID)
def admin_panel(message):
    """Show admin panel."""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("View Users", callback_data="admin_show_users"),
        InlineKeyboardButton("Manage Access", callback_data="admin_manage_access")
    )
    markup.add(
        InlineKeyboardButton("View Banned", callback_data="admin_show_banned_users"),
        InlineKeyboardButton("Stop/Ban", callback_data="admin_stop_menu")
    )
    sent = bot.send_message(ADMIN_CHAT_ID, "🔧 Admin Panel:", reply_markup=markup)
    # Store message ID for editing
    if ADMIN_CHAT_ID not in user_state:
        user_state[ADMIN_CHAT_ID] = {}
    user_state[ADMIN_CHAT_ID]["admin_msg_id"] = sent.message_id

@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_CHAT_ID and call.data.startswith("admin_"))
def handle_admin_callback(call):
    """Handle admin callback actions."""
    action = call.data
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    def edit_admin_message(text, markup=None):
        """Edit the current admin message."""
        try:
            bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to edit admin message: {e}")

    if action == "admin_show_users":
        visible_users = [uid for uid in ALL_USERS if isinstance(uid, int)]
        if not visible_users:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back_to_panel"))
            edit_admin_message("👥 **All Users:**\n\nNo users found.", markup)
            return

        msg_lines = ["👥 **All Users:**\n"]
        approved_count = banned_count = pending_count = 0
        
        for uid in visible_users:
            info = ALL_USERS.get(uid, {})
            status = get_user_status(uid)
            username = info.get("username_tg", "N/A")
            join_date = info.get("join_date", "Unknown")
            
            if status == "Admin":
                continue
            elif status == "Approved":
                approved_count += 1
            elif status == "BANNED":
                banned_count += 1
            else:
                pending_count += 1
                
            msg_lines.append(f"• `{uid}` | @{username} | {status} | {join_date}")

        msg_lines.insert(1, f"📊 **Summary:** {approved_count} Approved, {pending_count} Pending, {banned_count} Banned\n")
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back_to_panel"))
        
        edit_admin_message("\n".join(msg_lines), markup)

    elif action == "admin_manage_access":
        pending_users = [uid for uid in ALL_USERS if isinstance(uid, int) and get_user_status(uid) == "Pending"]
        approved_users = [uid for uid in ALL_USERS if isinstance(uid, int) and get_user_status(uid) == "Approved"]
        
        markup = InlineKeyboardMarkup()
        
        if pending_users:
            markup.add(InlineKeyboardButton(
                f"⏳ Pending Requests ({len(pending_users)})", 
                callback_data="admin_show_pending_users"
            ))
        
        if approved_users:
            markup.add(InlineKeyboardButton(
                f"✅ Approved Users ({len(approved_users)})", 
                callback_data="admin_show_approved_users"
            ))
        
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back_to_panel"))
        
        status_text = (
            f"📋 **Access Management**\n\n"
            f"⏳ Pending: {len(pending_users)}\n"
            f"✅ Approved: {len(approved_users)}"
        )
        
        edit_admin_message(status_text, markup)

    elif action == "admin_show_pending_users":
        pending_users = [uid for uid in ALL_USERS if isinstance(uid, int) and get_user_status(uid) == "Pending"]
        
        if not pending_users:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_manage_access"))
            edit_admin_message("⏳ **Pending Access Requests**\n\nNo pending users.", markup)
            return

        markup = InlineKeyboardMarkup()
        msg_lines = [f"⏳ **Pending Access Requests ({len(pending_users)}):**\n"]
        
        for uid in pending_users:
            info = ALL_USERS.get(uid, {})
            username = info.get("username_tg", "N/A")
            first_name = info.get("first_name", "N/A")
            join_date = info.get("join_date", "Unknown")
            
            msg_lines.append(f"• `{uid}` | @{username} | {first_name} | {join_date}")
            markup.add(InlineKeyboardButton(
                f"✅ Approve {uid} (@{username})", 
                callback_data=f"admin_approve_{uid}"
            ))
            
        if len(pending_users) > 1:
            markup.add(InlineKeyboardButton("✅ Approve All Pending", callback_data="admin_approve_all_pending"))
            
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_manage_access"))

        edit_admin_message("\n".join(msg_lines), markup)

    elif action == "admin_show_approved_users":
        approved_users = [uid for uid in ALL_USERS if isinstance(uid, int) and get_user_status(uid) == "Approved"]
        
        if not approved_users:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_manage_access"))
            edit_admin_message("✅ **Approved Users**\n\nNo approved users.", markup)
            return

        markup = InlineKeyboardMarkup()
        msg_lines = [f"✅ **Approved Users ({len(approved_users)}):**\n"]
        
        for uid in approved_users:
            info = ALL_USERS.get(uid, {})
            username = info.get("username_tg", "N/A")
            join_date = info.get("join_date", "Unknown")
            
            msg_lines.append(f"• `{uid}` | @{username} | {join_date}")
            markup.add(InlineKeyboardButton(
                f"❌ Revoke {uid} (@{username})", 
                callback_data=f"admin_revoke_{uid}"
            ))
            
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_manage_access"))

        edit_admin_message("\n".join(msg_lines), markup)

    elif action == "admin_show_banned_users":
        if not BANNED_USERS:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_back_to_panel"))
            edit_admin_message("🚫 **Banned Users**\n\nNo banned users.", markup)
            return

        markup = InlineKeyboardMarkup()
        msg_lines = [f"🚫 **Banned Users ({len(BANNED_USERS)}):**\n"]
        
        for uid in BANNED_USERS:
            username = ALL_USERS.get(uid, {}).get("username_tg", "N/A")
            join_date = ALL_USERS.get(uid, {}).get("join_date", "Unknown")
            
            msg_lines.append(f"• `{uid}` | @{username} | {join_date}")
            markup.add(InlineKeyboardButton(f"🔓 Unban {uid} (@{username})", callback_data=f"admin_unban_{uid}"))

        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back_to_panel"))
        edit_admin_message("\n".join(msg_lines), markup)

    elif action == "admin_stop_menu":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🚫 Ban All Users", callback_data="admin_stop_all_users"),
            InlineKeyboardButton("🚫 Ban Single User", callback_data="admin_stop_single_user")
        )
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back_to_panel"))
        edit_admin_message("🚫 **Ban Options:**\n\nChoose ban action:", markup)

    elif action == "admin_stop_all_users":
        users_to_ban = [uid for uid in ALL_USERS if uid != ADMIN_CHAT_ID and uid not in BANNED_USERS]

        if not users_to_ban:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_stop_menu"))
            edit_admin_message("🚫 **Ban All Users**\n\nNo users to ban.", markup)
            return

        for uid in users_to_ban:
            if uid not in BANNED_USERS:
                BANNED_USERS.append(uid)
            if uid in APPROVED_USERS:
                APPROVED_USERS.remove(uid)
            try:
                bot.send_message(uid, "🚫 You have been banned by admin.")
            except Exception:
                pass

        save_banned_users()
        save_approved_users()
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("← Back", callback_data="admin_back_to_panel"))
        edit_admin_message(f"✅ **Banned {len(users_to_ban)} users successfully.**", markup)

    elif action == "admin_stop_single_user":
        bannable_users = [uid for uid in ALL_USERS if uid != ADMIN_CHAT_ID and uid not in BANNED_USERS]
        
        if not bannable_users:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_stop_menu"))
            edit_admin_message("🚫 **Ban Single User**\n\nNo available users to ban.", markup)
            return
            
        markup = InlineKeyboardMarkup()
        msg_lines = [f"🚫 **Select User to Ban ({len(bannable_users)} available):**\n"]
        
        for uid in bannable_users:
            info = ALL_USERS.get(uid, {})
            username = info.get("username_tg", "N/A")
            status = get_user_status(uid)
            
            msg_lines.append(f"• `{uid}` | @{username} | {status}")
            markup.add(InlineKeyboardButton(
                f"🚫 Ban {uid} (@{username}) - {status}", 
                callback_data=f"admin_ban_{uid}"
            ))

        markup.add(InlineKeyboardButton("← Back", callback_data="admin_stop_menu"))
        edit_admin_message("\n".join(msg_lines), markup)

    elif action.startswith("admin_approve_"):
        if action == "admin_approve_all_pending":
            pending_users = [uid for uid in ALL_USERS if isinstance(uid, int) and get_user_status(uid) == "Pending"]
            
            approved_count = 0
            for uid in pending_users:
                if uid not in APPROVED_USERS:
                    APPROVED_USERS.append(uid)
                    approved_count += 1
                    try:
                        bot.send_message(uid, "✅ Great! You have been approved to use the bot. Use /start to begin.")
                    except Exception:
                        pass
            
            save_approved_users()
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_manage_access"))
            edit_admin_message(f"✅ **Approved {approved_count} pending users successfully.**", markup)
        else:
            uid = int(action.split("_")[-1])
            
            if uid not in APPROVED_USERS:
                APPROVED_USERS.append(uid)
                save_approved_users()
                
                username = ALL_USERS.get(uid, {}).get("username_tg", "N/A")
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("← Back", callback_data="admin_show_pending_users"))
                edit_admin_message(f"✅ **Approved user `{uid}` (@{username}) successfully.**", markup)
                
                try:
                    bot.send_message(uid, "✅ Great! You have been approved to use the bot. Use /start to begin.")
                except Exception:
                    pass
            else:
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("← Back", callback_data="admin_show_pending_users"))
                edit_admin_message(f"⚠️ **User `{uid}` is already approved.**", markup)

    elif action.startswith("admin_revoke_"):
        uid = int(action.split("_")[-1])
        
        if uid in APPROVED_USERS:
            APPROVED_USERS.remove(uid)
            save_approved_users()
            
            username = ALL_USERS.get(uid, {}).get("username_tg", "N/A")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_show_approved_users"))
            edit_admin_message(f"❌ **Revoked access for user `{uid}` (@{username}) successfully.**", markup)
            
            try:
                bot.send_message(uid, "❌ Your access has been revoked by admin.")
            except Exception:
                pass
        else:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_show_approved_users"))
            edit_admin_message(f"⚠️ **User `{uid}` is not in approved list.**", markup)

    elif action.startswith("admin_ban_"):
        uid = int(action.split("_")[-1])
        
        if uid not in BANNED_USERS:
            BANNED_USERS.append(uid)
            if uid in APPROVED_USERS:
                APPROVED_USERS.remove(uid)
                save_approved_users()
            save_banned_users()
            
            username = ALL_USERS.get(uid, {}).get("username_tg", "N/A")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_stop_single_user"))
            edit_admin_message(f"✅ **Banned user `{uid}` (@{username}) successfully.**", markup)
            
            try:
                bot.send_message(uid, "🚫 You have been banned by admin.")
            except Exception:
                pass
        else:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_stop_single_user"))
            edit_admin_message(f"⚠️ **User `{uid}` is already banned.**", markup)

    elif action.startswith("admin_unban_"):
        uid = int(action.split("_")[-1])
        
        if uid in BANNED_USERS:
            BANNED_USERS.remove(uid)
            save_banned_users()
            
            username = ALL_USERS.get(uid, {}).get("username_tg", "N/A")
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_show_banned_users"))
            edit_admin_message(f"✅ **Unbanned user `{uid}` (@{username}) successfully.**", markup)
            
            try:
                bot.send_message(uid, "✅ You have been unbanned. Use /start to access the bot.")
            except Exception:
                pass
        else:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("← Back", callback_data="admin_show_banned_users"))
            edit_admin_message(f"⚠️ **User `{uid}` is not banned.**", markup)

    elif action == "admin_back_to_panel":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("View Users", callback_data="admin_show_users"),
            InlineKeyboardButton("Manage Access", callback_data="admin_manage_access")
        )
        markup.add(
            InlineKeyboardButton("View Banned", callback_data="admin_show_banned_users"),
            InlineKeyboardButton("Stop/Ban", callback_data="admin_stop_menu")
        )
        edit_admin_message("🔧 **Admin Panel:**", markup)

# === Main ===
if __name__ == "__main__":
    # Load initial data
    load_initial_data()
    
    # Start bot
    logger.info("Bot is running...")
    bot.infinity_polling()
