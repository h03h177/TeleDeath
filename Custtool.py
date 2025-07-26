import telebot
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sys
import time
import threading


TOKEN = "7826463998:AAHoTkqPjax4BeDIii8f9kXvn9HM0Swarvc"
if not TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN environment variable is not set!")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

user_sessions = {}
auto_report_threads = {}

report_types = [
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


GIF_URL = "https://raw.githubusercontent.com/rev-eng1/ThemeX/refs/heads/main/video_2025-06-27_16-39-43.gif"

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    
    if user_id in auto_report_threads:
        auto_report_threads[user_id]["stop"] = True
        time.sleep(0.5) 
    
    
    
    if user_id in user_sessions:
        if user_sessions[user_id].get("control_panel_gif_message_id"):
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=user_sessions[user_id]["control_panel_gif_message_id"])
            except Exception as e:
                print(f"Error deleting old GIF message on start: {e}")
        if user_sessions[user_id].get("control_panel_status_message_id"):
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=user_sessions[user_id]["control_panel_status_message_id"])
            except Exception as e:
                print(f"Error deleting old status message on start: {e}")
        if user_sessions[user_id].get("type_selection_message_id"):
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=user_sessions[user_id]["type_selection_message_id"])
            except Exception as e:
                print(f"Error deleting old type selection message on start: {e}")

    user_sessions[user_id] = {
        "attack_count": 0,
        "error_count": 0,
        "is_running": False,
        "is_paused": False,
        "selected_report_id": None, 
        "control_panel_gif_message_id": None, 
        "control_panel_status_message_id": None,
        "type_selection_message_id": None,
        "chat_id": message.chat.id 
    }
    
    bot.send_message(user_id, "ادخل Session ID الخاص بك :")

@bot.message_handler(func=lambda message: user_sessions.get(message.from_user.id, {}).get("step") is None)
def get_session_id(message):
    user_id = message.from_user.id
    if user_id not in user_sessions: 
        user_sessions[user_id] = {"attack_count": 0, "error_count": 0, "is_running": False, "is_paused": False, "selected_report_id": None, "control_panel_gif_message_id": None, "control_panel_status_message_id": None, "type_selection_message_id": None, "chat_id": message.chat.id}
    
    user_sessions[user_id]["sessionid"] = message.text.strip()
    user_sessions[user_id]["step"] = "csrftoken"    
    bot.send_message(message.chat.id, "ادخل CRSF Token الخاص بك")

@bot.message_handler(func=lambda message: user_sessions.get(message.from_user.id, {}).get("step") == "csrftoken")
def get_csrftoken(message):
    user_sessions[message.from_user.id]["csrftoken"] = message.text.strip()
    user_sessions[message.from_user.id]["step"] = "username"
    
    bot.send_message(message.chat.id, "ادخل اسم المستخدم المستهدف (Target username):")

@bot.message_handler(func=lambda message: user_sessions.get(message.from_user.id, {}).get("step") == "username")
def get_username(message):
    user_sessions[message.from_user.id]["username"] = message.text.strip()
    user_sessions[message.from_user.id]["step"] = "delay"
    bot.send_message(message.chat.id, "Enter delay between reports (in seconds, recommended: 5-10):")

@bot.message_handler(func=lambda message: user_sessions.get(message.from_user.id, {}).get("step") == "delay")
def get_delay(message):
    try:
        delay = int(message.text.strip())
        if delay < 1:
            delay = 5
        user_sessions[message.from_user.id]["delay"] = delay
        user_sessions[message.from_user.id]["step"] = "report_type_selection" 
        
        get_user_id_and_show_type_selection(message.chat.id, message.from_user.id)
    except ValueError:
        bot.send_message(message.chat.id, "Please enter a valid number (seconds):")

def get_user_id_and_show_type_selection(chat_id, user_id):
    user_data = user_sessions[user_id]
    username = user_data['username']

    try:
        r2 = requests.post(
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
            data={
                "signed_body": f"xxxx.{{\"q\":\"{username}\"}}"
            }
        )
        if 'No users found' in r2.text:
            bot.send_message(chat_id, "No users found.")
            user_sessions[user_id]["error_count"] += 1
            user_sessions.pop(user_id, None)
            return

        target_id = str(r2.json()['user_id'])
        user_sessions[user_id]["target_id"] = target_id
        
        show_report_type_selection_menu(chat_id, user_id)
        
    except Exception as e:
        bot.send_message(chat_id, f"Error getting user ID: {str(e)}")
        user_sessions[user_id]["error_count"] += 1
        user_sessions.pop(user_id, None)
        return

def show_report_type_selection_menu(chat_id, user_id):
    """Displays only report types and an exit button."""
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    
    for report in report_types:
        button_text = f"{report['name']}" 
        callback_data = f"start_auto_report_{report['id']}" 
        buttons.append(InlineKeyboardButton(button_text, callback_data=callback_data))
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
            
    markup.add(InlineKeyboardButton("ايقاف البلاغ التلقائي ", callback_data="stop_process")) 
    
    sent_msg = bot.send_message(chat_id, "اختر نوع البلاغ:", reply_markup=markup, parse_mode='Markdown')
    user_sessions[user_id]["type_selection_message_id"] = sent_msg.message_id


def display_and_update_control_panel(chat_id, user_id):
    """
    Manages sending/editing both the GIF message and the separate status message.
    """
    user_data = user_sessions[user_id]
    username = user_data['username']
    attack_count = user_data.get('attack_count', 0)
    error_count = user_data.get('error_count', 0)
    is_paused = user_data.get('is_paused', False) 
    
    gif_caption = "IG : sir.say"

    if user_data.get("control_panel_gif_message_id"):
        try:
            bot.edit_message_caption(
                chat_id=chat_id,
                message_id=user_data["control_panel_gif_message_id"],
                caption=gif_caption,
                parse_mode='Markdown'
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                pass 
            else:
                print(f"Error editing GIF caption (ID: {user_data['control_panel_gif_message_id']}): {e}")
                
                try:
                    sent_gif_msg = bot.send_animation(chat_id, GIF_URL, caption=gif_caption, parse_mode='Markdown')
                    user_sessions[user_id]["control_panel_gif_message_id"] = sent_gif_msg.message_id
                except Exception as send_e:
                    print(f"Error sending new GIF after edit failure: {send_e}")
                    
                    sent_gif_msg = bot.send_message(chat_id, f"**GIF failed to load.**\n{gif_caption}", parse_mode='Markdown')
                    user_sessions[user_id]["control_panel_gif_message_id"] = sent_gif_msg.message_id
    else:
        try:
            sent_gif_msg = bot.send_animation(chat_id, GIF_URL, caption=gif_caption, parse_mode='Markdown')
            user_sessions[user_id]["control_panel_gif_message_id"] = sent_gif_msg.message_id
        except Exception as e:
            print(f"Error sending initial GIF: {e}")
            sent_gif_msg = bot.send_message(chat_id, f"**GIF failed to load.**\n{gif_caption}", parse_mode='Markdown')
            user_sessions[user_id]["control_panel_gif_message_id"] = sent_gif_msg.message_id


    
    status_text = f"**Done:** {attack_count}  |  **Error:** {error_count}  |  **Target:** @{username}"
    
    markup_status = InlineKeyboardMarkup(row_width=2)
    
    
    if is_paused:
        pause_resume_button = InlineKeyboardButton("Resume", callback_data="resume_auto")
    else:
        pause_resume_button = InlineKeyboardButton("Pause", callback_data="pause_auto")
    
    kill_button = InlineKeyboardButton("Kill", callback_data="kill_auto")
    
    
    markup_status.add(pause_resume_button, kill_button)

    if user_data.get("control_panel_status_message_id"):
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data["control_panel_status_message_id"],
                text=status_text,
                reply_markup=markup_status,
                parse_mode='Markdown'
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                pass
            else:
                print(f"Error editing status message (ID: {user_data['control_panel_status_message_id']}): {e}")
                
                try:
                    sent_status_msg = bot.send_message(chat_id, status_text, reply_markup=markup_status, parse_mode='Markdown')
                    user_sessions[user_id]["control_panel_status_message_id"] = sent_status_msg.message_id
                except Exception as send_e:
                    print(f"Error sending new status message after edit failure: {send_e}")
    else:
        try:
            sent_status_msg = bot.send_message(chat_id, status_text, reply_markup=markup_status, parse_mode='Markdown')
            user_sessions[user_id]["control_panel_status_message_id"] = sent_status_msg.message_id
        except Exception as e:
            print(f"Error sending initial status message: {e}")


def auto_report_worker(user_id, report_type_id):
    """Worker function that runs in a separate thread for a specific report type"""
    user_data = user_sessions.get(user_id)
    if not user_data:
        return
    
    chat_id = user_data.get('chat_id') 
    
    target_id = user_data['target_id']
    sessionid = user_data['sessionid']
    csrftoken = user_data['csrftoken']
    delay = user_data['delay']
    
    
    user_sessions[user_id]["is_running"] = True
    user_sessions[user_id]["is_paused"] = False
    
    while user_id in auto_report_threads and not auto_report_threads[user_id].get("stop", False):
        if user_sessions[user_id].get('is_paused', False):
            time.sleep(1)
            continue
        
        try:
            r3 = requests.post(
                f"https://i.instagram.com/users/{target_id}/flag/",
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "cookie": f"sessionid={sessionid}",
                    "X-CSRFToken": csrftoken,
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data=f'source_name=&reason_id={report_type_id}&frx_context=',
                allow_redirects=False
            )

            if r3.status_code in [200, 302]:
                user_sessions[user_id]["attack_count"] += 1
            elif r3.status_code == 429:
                user_sessions[user_id]["error_count"] += 1
                if chat_id:
                    try:
                        bot.send_message(chat_id, "Rate limited. Increasing delay...")
                    except:
                        pass
                time.sleep(delay * 2) 
                
            else:
                user_sessions[user_id]["error_count"] += 1
        except Exception as e:
            user_sessions[user_id]["error_count"] += 1
        
        
        if chat_id and user_data.get("is_running") and not user_data.get("is_paused"):
            try:
                time.sleep(0.5)
                display_and_update_control_panel(chat_id, user_id)
            except Exception as e:
                print(f"Error updating control panel during auto-report: {e}")

        remaining_delay = delay - 0.5 
        for _ in range(int(remaining_delay)): 
            if user_id in auto_report_threads and auto_report_threads[user_id].get("stop", False):
                break
            time.sleep(1)
        if remaining_delay > 0 and remaining_delay % 1 != 0: 
             time.sleep(remaining_delay % 1)
            

    if user_id in auto_report_threads:
        del auto_report_threads[user_id]
    
    if user_id in user_sessions and chat_id:
        
        bot.send_message(chat_id, "تم ايقاف البلاغ التلقائي ")
        user_sessions.pop(user_id, None) 


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    
    if user_id not in user_sessions:
        bot.answer_callback_query(call.id, "Session expired. Please start again with /start")
        return
    
    user_data = user_sessions[user_id]
    
    if not user_data.get('chat_id'):
        user_data['chat_id'] = call.message.chat.id

    
    if call.data.startswith('start_auto_report_'):
        if user_data.get("type_selection_message_id"):
            try:
                bot.delete_message(chat_id=call.message.chat.id, message_id=user_data["type_selection_message_id"])
                user_data["type_selection_message_id"] = None
            except Exception as e:
                print(f"Error deleting type selection message: {e}")

        report_id = call.data.split('_')[-1] 
        user_sessions[user_id]["selected_report_id"] = report_id

        if user_id in auto_report_threads:
            auto_report_threads[user_id]["stop"] = True
            time.sleep(1) 
        
        user_sessions[user_id]["attack_count"] = 0 
        user_sessions[user_id]["error_count"] = 0

        auto_report_threads[user_id] = {"stop": False}
        
        thread = threading.Thread(target=auto_report_worker, args=(user_id, report_id))
        thread.daemon = True
        thread.start()
        
        bot.answer_callback_query(call.id, f"Auto reporting started for type {report_id}!")
        display_and_update_control_panel(call.message.chat.id, user_id) 

    elif call.data == "pause_auto":
        user_sessions[user_id]["is_paused"] = True
        bot.answer_callback_query(call.id, "Auto reporting paused")
        display_and_update_control_panel(call.message.chat.id, user_id)
        
    elif call.data == "resume_auto":
        user_sessions[user_id]["is_paused"] = False
        bot.answer_callback_query(call.id, "Auto reporting resumed")
        display_and_update_control_panel(call.message.chat.id, user_id)
        
    elif call.data == "kill_auto": 
        stop_auto_reporting(call, user_id)
        bot.answer_callback_query(call.id, "Auto reporting kill command sent.")
        
    elif call.data == "stop_process":
        bot.answer_callback_query(call.id, "Stopping process.")
        if user_data.get("type_selection_message_id"):
            try:
                bot.delete_message(chat_id=call.message.chat.id, message_id=user_data["type_selection_message_id"])
                user_data["type_selection_message_id"] = None
            except Exception as e:
                print(f"Error deleting type selection message on Exit: {e}")
        
        if user_id in user_sessions:
            user_sessions.pop(user_id, None)
        bot.send_message(call.message.chat.id, "تم إنهاء العملية.") 


def stop_auto_reporting(call, user_id):
    if user_id in auto_report_threads:
        auto_report_threads[user_id]["stop"] = True
    
    user_sessions[user_id]["is_running"] = False
    user_sessions[user_id]["is_paused"] = False


@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id
    if user_id in user_sessions:
        step = user_sessions[user_id].get("step")
        if step and step not in ["report_type_selection"]: 
            return 
        
        if user_sessions[user_id].get("is_running") or user_sessions[user_id].get("is_paused"):
            display_and_update_control_panel(message.chat.id, user_id)
        elif user_sessions[user_id].get("type_selection_message_id"): 
            show_report_type_selection_menu(message.chat.id, user_id)
        else:
            bot.send_message(message.chat.id, "Please use the provided buttons or type /start to begin/restart.")
    else:
        bot.send_message(message.chat.id, "Please type /start to begin.")

if __name__ == "__main__":
    print("Auto Multi-Report Bot is starting...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Bot polling error: {e}")
