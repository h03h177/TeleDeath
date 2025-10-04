import telebot
import requests
from io import BytesIO
import time
from collections import defaultdict
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = '8350843648:AAGTNJhvvGoJcoixp8FC-4VL-0cOLreQa-s'
GROUP_LINK = 'https://t.me/Red_Dead_online7'
ADMIN_IDS = [7865602280, 0, 0]

bot = telebot.TeleBot(BOT_TOKEN)

last_request_time = defaultdict(float)
chat_warned = defaultdict(bool)
api_url = "https://madam-nazar-location-api.herokuapp.com/location/current"
DATA_FILE = 'bot_data.json'
mute_notifications = False

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            global mute_notifications
            global ADMIN_IDS
            mute_notifications = data.get('mute_notifications', False)
            admins = data.get('admins', ADMIN_IDS)
            ADMIN_IDS = [admin for admin in admins if admin != 0]
            return data.get('allowed', []), data.get('known', {}), admins
    except FileNotFoundError:
        return [], {}, ADMIN_IDS

def save_data(allowed, known, admins):
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'allowed': allowed,
            'known': known,
            'mute_notifications': mute_notifications,
            'admins': admins
        }, f)

allowed_groups, known_groups, ADMIN_IDS = load_data()

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    if message.chat.type in ['group', 'supergroup'] and chat_id not in allowed_groups:
        return
    
    bot.reply_to(message, "مرحبًا بكم في بوت مدام نزار!")
    if not mute_notifications:
        user = message.from_user
        for admin_id in [aid for aid in ADMIN_IDS if aid != 0]:
            bot.send_message(admin_id, f"المستخدم @{user.username} (ID: {user.id}) بدأ البوت في الدردشة {chat_id}.")

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if message.from_user.id not in [aid for aid in ADMIN_IDS if aid != 0]:
        bot.reply_to(message, "غير مخول لك الوصول إلى لوحة التحكم.")
        return
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("قائمة المجموعات المسموح بها", callback_data="list_allowed"))
    markup.add(InlineKeyboardButton("قائمة المجموعات المعلقة", callback_data="list_pending"))
    mute_text = "إلغاء كتم الإشعارات" if mute_notifications else "كتم الإشعارات"
    markup.add(InlineKeyboardButton(mute_text, callback_data="toggle_mute"))
    markup.add(InlineKeyboardButton("إدارة المشرفين", callback_data="manage_admins"))
    bot.reply_to(message, "لوحة التحكم:", reply_markup=markup)

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_members(message):
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            chat_id = message.chat.id
            title = message.chat.title or "مجموعة بدون عنوان"
            
            if chat_id not in known_groups:
                known_groups[chat_id] = {'title': title, 'status': 'pending'}
                save_data(allowed_groups, known_groups, ADMIN_IDS)
            
            if chat_id not in allowed_groups:
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("الموافقة", callback_data=f"approve_{chat_id}"))
                markup.add(InlineKeyboardButton("المغادرة", callback_data=f"leave_{chat_id}"))
                for admin_id in [aid for aid in ADMIN_IDS if aid != 0]:
                    bot.send_message(admin_id, f"تمت إضافة البوت إلى مجموعة جديدة: {title} (ID: {chat_id})", reply_markup=markup)
            else:
                bot.send_message(chat_id, "البوت تمت الموافقة عليه وجاهز للاستخدام!")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.from_user.id not in [aid for aid in ADMIN_IDS if aid != 0]:
        bot.answer_callback_query(call.id, "غير مخول لك.")
        return
    
    data = call.data
    if data.startswith("approve_"):
        chat_id = int(data.split("_")[1])
        if chat_id not in allowed_groups:
            allowed_groups.append(chat_id)
            if chat_id in known_groups:
                known_groups[chat_id]['status'] = 'allowed'
            save_data(allowed_groups, known_groups, ADMIN_IDS)
            for admin_id in [aid for aid in ADMIN_IDS if aid != 0]:
                bot.send_message(admin_id, f"تمت الموافقة على المجموعة {chat_id} ({known_groups.get(chat_id, {}).get('title', 'غير معروف')}).")
            try:
                bot.send_message(chat_id, "تمت الموافقة على البوت! الآن يعمل.")
            except:
                pass
        bot.answer_callback_query(call.id, "تمت الموافقة على المجموعة.")
    
    elif data.startswith("leave_"):
        chat_id = int(data.split("_")[1])
        try:
            bot.leave_chat(chat_id)
            if chat_id in allowed_groups:
                allowed_groups.remove(chat_id)
            if chat_id in known_groups:
                known_groups[chat_id]['status'] = 'left'
            save_data(allowed_groups, known_groups, ADMIN_IDS)
            for admin_id in [aid for aid in ADMIN_IDS if aid != 0]:
                bot.send_message(admin_id, f"تم مغادرة المجموعة {chat_id} ({known_groups.get(chat_id, {}).get('title', 'غير معروف')}).")
        except:
            pass
        bot.answer_callback_query(call.id, "تم مغادرة المجموعة.")
    
    elif data == "list_allowed":
        list_groups(call, 'allowed')
    
    elif data == "list_pending":
        list_groups(call, 'pending')
    
    elif data == "toggle_mute":
        global mute_notifications
        mute_notifications = not mute_notifications
        save_data(allowed_groups, known_groups, ADMIN_IDS)
        status = "تم كتم الإشعارات." if mute_notifications else "تم إلغاء كتم الإشعارات."
        for admin_id in [aid for aid in ADMIN_IDS if aid != 0]:
            bot.send_message(admin_id, status)
        bot.answer_callback_query(call.id, status)
    
    elif data == "manage_admins":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("إضافة مشرف", callback_data="add_admin"))
        markup.add(InlineKeyboardButton("إزالة مشرف", callback_data="remove_admin"))
        markup.add(InlineKeyboardButton("قائمة المشرفين", callback_data="list_admins"))
        bot.send_message(call.from_user.id, "إدارة المشرفين:", reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    elif data == "add_admin":
        bot.send_message(call.from_user.id, "أرسل معرف المستخدم (ID) للمشرف الجديد:")
        bot.register_next_step_handler(call.message, add_admin)
        bot.answer_callback_query(call.id)
    
    elif data == "remove_admin":
        list_admins_for_removal(call)
        bot.answer_callback_query(call.id)
    
    elif data == "list_admins":
        admins_list = "\n".join([f"ID: {admin_id}" for admin_id in [aid for aid in ADMIN_IDS if aid != 0]])
        bot.send_message(call.from_user.id, f"قائمة المشرفين:\n{admins_list}")
        bot.answer_callback_query(call.id)
    
    elif data.startswith("remove_admin_"):
        admin_id = int(data.split("_")[2])
        if admin_id in ADMIN_IDS:
            if len([aid for aid in ADMIN_IDS if aid != 0]) > 1:
                if admin_id in ADMIN_IDS:
                    ADMIN_IDS.remove(admin_id)
                else:
                    idx = ADMIN_IDS.index(0)
                    ADMIN_IDS[idx] = 0
                save_data(allowed_groups, known_groups, ADMIN_IDS)
                for remaining_admin in [aid for aid in ADMIN_IDS if aid != 0]:
                    bot.send_message(remaining_admin, f"تم إزالة المشرف {admin_id}.")
            else:
                bot.send_message(call.from_user.id, "لا يمكن إزالة المشرف الأخير.")
        bot.answer_callback_query(call.id, "تمت العملية.")

def add_admin(message):
    try:
        new_admin_id = int(message.text.strip())
        if new_admin_id not in ADMIN_IDS:
            if 0 in ADMIN_IDS:
                idx = ADMIN_IDS.index(0)
                ADMIN_IDS[idx] = new_admin_id
            else:
                ADMIN_IDS.append(new_admin_id)
            save_data(allowed_groups, known_groups, ADMIN_IDS)
            for admin_id in [aid for aid in ADMIN_IDS if aid != 0]:
                bot.send_message(admin_id, f"تمت إضافة المشرف {new_admin_id}.")
        else:
            bot.send_message(message.chat.id, "هذا المعرف موجود بالفعل في قائمة المشرفين.")
    except ValueError:
        bot.send_message(message.chat.id, "يرجى إدخال معرف مستخدم صحيح (رقم).")

def list_admins_for_removal(call):
    markup = InlineKeyboardMarkup()
    for admin_id in [aid for aid in ADMIN_IDS if aid != 0]:
        markup.add(InlineKeyboardButton(f"إزالة {admin_id}", callback_data=f"remove_admin_{admin_id}"))
    bot.send_message(call.from_user.id, "اختر مشرفًا لإزالته:", reply_markup=markup)

def list_groups(call, status_filter):
    status_text = "مسموح بها" if status_filter == 'allowed' else "معلقة"
    filtered_groups = [cid for cid, info in known_groups.items() if info.get('status') == status_filter]
    if not filtered_groups:
        bot.send_message(call.from_user.id, f"لا توجد مجموعات {status_text}.")
        return
    
    for chat_id in filtered_groups:
        title = known_groups[chat_id]['title']
        markup = InlineKeyboardMarkup()
        if status_filter == 'pending':
            markup.add(InlineKeyboardButton("الموافقة", callback_data=f"approve_{chat_id}"))
        markup.add(InlineKeyboardButton("المغادرة", callback_data=f"leave_{chat_id}"))
        bot.send_message(call.from_user.id, f"المجموعة: {title}\nالمعرف: {chat_id}\nاسم المستخدم: (أسماء المستخدمين للمجموعات غير متاحة مباشرة)", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if text in ["نزار", "مدام نزار"]:
        if message.chat.type in ['group', 'supergroup'] and chat_id not in allowed_groups:
            return
        
        try:
            is_group = message.chat.type in ['group', 'supergroup']
            user_status = bot.get_chat_member(chat_id, message.from_user.id).status if is_group else 'private'
            is_admin = user_status in ['administrator', 'creator']
            
            current_time = time.time()
            
            if is_group and not is_admin:
                if current_time - last_request_time[chat_id] < 300:
                    if not chat_warned[chat_id]:
                        bot.reply_to(message, "عليك الانتظار 5 دقائق لطلب الموقع مرة أخرى.")
                        chat_warned[chat_id] = True
                    return
            
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            
            image_url = data['data']['location']['image']
            
            caption = f"موقع مدام نزار اليوم 📍\n\nالبوت خاص بقروب ⤹\n{GROUP_LINK}"
            
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            img = BytesIO(img_response.content)
            img.name = 'nazar_location.jpg'
            
            bot.send_photo(chat_id, photo=img, caption=caption)
            
            if is_group:
                last_request_time[chat_id] = current_time
                chat_warned[chat_id] = False
            
            if not mute_notifications:
                user = message.from_user
                for admin_id in [aid for aid in ADMIN_IDS if aid != 0]:
                    bot.send_message(admin_id, f"المستخدم @{user.username} (ID: {user.id}) استخدم البوت في {'المجموعة' if is_group else 'الدردشة الخاصة'} {chat_id} ({known_groups.get(chat_id, {}).get('title', 'غير معروف') if is_group else 'خاص'}).")
        
        except telebot.apihelper.ApiTelegramException as te:
            bot.reply_to(message, "خطأ في التحقق من حالة العضو. تأكد من أن البوت هو مشرف في المجموعة.")
        except requests.exceptions.RequestException as e:
            bot.reply_to(message, f"خطأ في جلب البيانات: {str(e)}")
        except KeyError:
            bot.reply_to(message, "تنسيق استجابة API غير متوقع. يرجى التحقق من API.")

if __name__ == '__main__':
    print("البوت يعمل...")
    bot.infinity_polling()
