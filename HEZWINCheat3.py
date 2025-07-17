import telebot
from telebot import types
import time
from datetime import datetime, timedelta
import json
import os
import threading
import random # Fıkra ve oylama için
from collections import defaultdict # Analiz için
import re # Anti-reklam için

# Bot Token'ınızı buraya girin
TOKEN = '7592710337:AAF636BqFT8vCWTqTX4CKUpgnLUhJ6SRGf0'
bot = telebot.TeleBot(TOKEN)

# Veri dosyaları
USER_DATA_FILE = 'user_data.json'
GROUP_SETTINGS_FILE = 'group_settings.json'
FILTERS_FILE = 'filters.json'
GROUP_DATA_FILE = 'group_data.json' # Yeni: Grup istatistikleri için

# Kullanıcı verilerini yükle
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Grup ayarlarını yükle
def load_group_settings():
    if os.path.exists(GROUP_SETTINGS_FILE):
        with open(GROUP_SETTINGS_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Filtreleri yükle
def load_filters():
    if os.path.exists(FILTERS_FILE):
        with open(FILTERS_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Grup verilerini yükle (istatistikler için)
def load_group_data():
    if os.path.exists(GROUP_DATA_FILE):
        with open(GROUP_DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# Kullanıcı verilerini kaydet
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Grup ayarlarını kaydet
def save_group_settings(data):
    with open(GROUP_SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Filtreleri kaydet
def save_filters(data):
    with open(FILTERS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Grup verilerini kaydet
def save_group_data(data):
    with open(GROUP_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Verileri yükle
user_data = load_user_data()
group_settings = load_group_settings()
filters = load_filters()
group_data = load_group_data() # Yüklendi

# Flood kontrolü için global sözlük
# {chat_id: {user_id: [timestamp1, timestamp2, ...]}}
flood_control = {}

# Oylama sistemi için global sözlük
# {chat_id: {message_id: {'question': '...', 'options': ['...'], 'votes': {'option_index': count}, 'creator_id': '...'}}}
active_polls = {}

# Çekiliş sistemi için global sözlük
# {chat_id: {message_id: {'prize': '...', 'participants': [], 'creator_id': '...'}}}
active_giveaways = {}

# Kullanıcıyı kaydet veya güncelle
def update_user(user_id, username=None, first_name=None, last_name=None):
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {
            'warns': 0,
            'muted': False,
            'mute_until': None,
            'banned': False,
            'message_count': 0 # Yeni: Mesaj sayısını takip etmek için
        }
    if username:
        user_data[str(user_id)]['username'] = username
    if first_name:
        user_data[str(user_id)]['first_name'] = first_name
    if last_name:
        user_data[str(user_id)]['last_name'] = last_name
    save_user_data(user_data)

# Grup ayarlarını başlat
def init_group_settings(chat_id):
    if str(chat_id) not in group_settings:
        group_settings[str(chat_id)] = {
            'locked_features': [],
            'rules': 'Henüz kurallar belirlenmedi. /setrules komutu ile ayarlayabilirsiniz.',
            'welcome_message': 'Gruba hoş geldiniz!',
            'welcome_enabled': True,
            'max_warns': 3,
            'flood_limit': 5,
            'flood_mode': 'mute', # mute, kick, ban
            'reports_enabled': True,
            'joinlogs_enabled': False, # Yeni: Giriş kayıtları
            'leftlogs_enabled': False, # Yeni: Ayrılma kayıtları
            'log_channel_id': None, # Yeni: Log kanalı
            'antiads_enabled': False, # Yeni: Anti-reklam
            'ads_action': 'kick', # Yeni: Reklam yapanlara uygulanacak ceza
            'ads_logs': [] # Yeni: Tespit edilen reklam içerikleri logları
        }
        save_group_settings(group_settings)

# Grup verilerini başlat (istatistikler için)
def init_group_data(chat_id):
    if str(chat_id) not in group_data:
        group_data[str(chat_id)] = {
            'total_messages': 0,
            'users_joined': 0,
            'users_left': 0,
            'hourly_activity': defaultdict(int) # Saatlik aktivite
        }
        save_group_data(group_data)

# Kullanıcının yetkisini kontrol et
def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

# Hedef kullanıcıyı mesajdan veya etiketden al
def get_target_user_from_message(message):
    target_user = None
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(message.text.split()) > 1:
        entity = next((e for e in message.entities if e.type == 'text_mention' or e.type == 'mention'), None)
        if entity:
            if entity.type == 'text_mention':
                target_user = entity.user
            elif entity.type == 'mention':
                username = message.text[entity.offset:entity.offset + entity.length]
                if username.startswith('@'):
                    username = username[1:]
                # Bu kısım Telegram API'de doğrudan kullanıcı ID'si vermediği için biraz karmaşıktır.
                # Gerçek bir botta, bu kullanıcı adını önceden kaydetmiş olmanız veya
                # get_chat_member ile tüm üyeleri kontrol etmeniz gerekir.
                # Basitlik adına, şimdilik sadece username'i döndürüyoruz.
                # Daha kapsamlı bir çözüm için, botun gruptaki tüm kullanıcıları bir veritabanında tutması gerekebilir.
                bot.reply_to(message, "Kullanıcı adıyla yasaklama/susturma şu anda doğrudan desteklenmiyor. Lütfen yanıtlayın veya kullanıcı ID'sini kullanın.")
                return None
    return target_user

# Yardımcı fonksiyon: Zaman stringini timedelta'a çevir
def parse_time_string(time_str):
    num = int(time_str[:-1])
    unit = time_str[-1].lower()
    if unit == 'h':
        return timedelta(hours=num)
    elif unit == 'd':
        return timedelta(days=num)
    elif unit == 'm':
        return timedelta(minutes=num)
    else:
        raise ValueError("Geçersiz zaman formatı. Örnek: 1h, 2d, 30m")

# --- Başlangıç Komutu ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, 
                     "Hey there! My name is HEZWIN HELPER - I'm here to help you manage your groups! Hit /help to find out more about how to use me to my full potential.\n\nThe creator of the bot is @HEZWIN")

# --- Yönetim Komutları ---

# /ban komutu
@bot.message_handler(commands=['ban'])
def ban_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    if is_admin(chat_id, target_user_id):
        bot.reply_to(message, "Yöneticileri yasaklayamazsınız.")
        return
    
    try:
        bot.ban_chat_member(chat_id, target_user_id)
        update_user(target_user_id, target_user.username, target_user.first_name, target_user.last_name)
        user_data[str(target_user_id)]['banned'] = True
        save_user_data(user_data)
        bot.reply_to(message, f"**@{target_username}** kullanıcısı yasaklandı.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /kick komutu
@bot.message_handler(commands=['kick'])
def kick_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    if is_admin(chat_id, target_user_id):
        bot.reply_to(message, "Yöneticileri atamazsınız.")
        return
    
    try:
        bot.kick_chat_member(chat_id, target_user_id)
        bot.unban_chat_member(chat_id, target_user_id) # Kick sonrası tekrar katılmasına izin ver
        update_user(target_user_id, target_user.username, target_user.first_name, target_user.last_name)
        bot.reply_to(message, f"**@{target_username}** kullanıcısı atıldı.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /mute komutu
@bot.message_handler(commands=['mute'])
def mute_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    if is_admin(chat_id, target_user_id):
        bot.reply_to(message, "Yöneticileri susturamazsınız.")
        return
    
    update_user(target_user_id, target_user.username, target_user.first_name, target_user.last_name)
    user_data[str(target_user_id)]['muted'] = True
    user_data[str(target_user_id)]['mute_until'] = None  # Kalıcı mute
    save_user_data(user_data)
    
    try:
        bot.restrict_chat_member(chat_id, target_user_id, until_date=None, can_send_messages=False)
        bot.reply_to(message, f"**@{target_username}** kullanıcısı susturuldu.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /unmute komutu
@bot.message_handler(commands=['unmute'])
def unmute_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    update_user(target_user_id, target_user.username, target_user.first_name, target_user.last_name)
    user_data[str(target_user_id)]['muted'] = False
    user_data[str(target_user_id)]['mute_until'] = None
    save_user_data(user_data)
    
    try:
        bot.restrict_chat_member(chat_id, target_user_id, until_date=None, can_send_messages=True)
        bot.reply_to(message, f"**@{target_username}** kullanıcısının susturması kaldırıldı.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /warn komutu
@bot.message_handler(commands=['warn'])
def warn_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    if is_admin(chat_id, target_user_id):
        bot.reply_to(message, "Yöneticilere uyarı veremezsiniz.")
        return
    
    init_group_settings(chat_id)
    update_user(target_user_id, target_user.username, target_user.first_name, target_user.last_name)
    
    user_data[str(target_user_id)]['warns'] = user_data[str(target_user_id)].get('warns', 0) + 1
    save_user_data(user_data)
    
    max_warns = group_settings[str(chat_id)].get('max_warns', 3)
    current_warns = user_data[str(target_user_id)]['warns']
    
    if current_warns >= max_warns:
        try:
            bot.kick_chat_member(chat_id, target_user_id)
            bot.unban_chat_member(chat_id, target_user_id)
            user_data[str(target_user_id)]['warns'] = 0
            save_user_data(user_data)
            bot.reply_to(message, f"**@{target_username}** kullanıcısı {max_warns} uyarı aldığı için gruptan atıldı.", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"Hata oluştu: {str(e)}")
    else:
        bot.reply_to(message, f"**@{target_username}** kullanıcısına uyarı verildi. ({current_warns}/{max_warns})", parse_mode="Markdown")

# /resetwarns komutu
@bot.message_handler(commands=['resetwarns'])
def reset_warns(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    update_user(target_user_id, target_user.username, target_user.first_name, target_user.last_name)
    user_data[str(target_user_id)]['warns'] = 0
    save_user_data(user_data)
    
    bot.reply_to(message, f"**@{target_username}** kullanıcısının uyarıları sıfırlandı.", parse_mode="Markdown")

# /del komutu
@bot.message_handler(commands=['del'])
def delete_message(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "Lütfen silmek istediğiniz mesajı yanıtlayarak bu komutu kullanın.")
        return
    
    try:
        bot.delete_message(chat_id, message.reply_to_message.message_id)
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        bot.reply_to(message, f"Mesaj silinirken hata oluştu: {str(e)}")

# /lock komutu
@bot.message_handler(commands=['lock'])
def lock_feature(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    if len(message.text.split()) < 2:
        bot.reply_to(message, "Kullanım: /lock <özellik>\nÖrnek: /lock link")
        return
    
    feature = message.text.split()[1].lower()
    init_group_settings(chat_id)
    
    if feature not in group_settings[str(chat_id)]['locked_features']:
        group_settings[str(chat_id)]['locked_features'].append(feature)
        save_group_settings(group_settings)
        bot.reply_to(message, f"**{feature}** özelliği kilitlendi.", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"**{feature}** özelliği zaten kilitli.", parse_mode="Markdown")

# /unlock komutu
@bot.message_handler(commands=['unlock'])
def unlock_feature(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    if len(message.text.split()) < 2:
        bot.reply_to(message, "Kullanım: /unlock <özellik>\nÖrnek: /unlock link")
        return
    
    feature = message.text.split()[1].lower()
    init_group_settings(chat_id)
    
    if feature in group_settings[str(chat_id)]['locked_features']:
        group_settings[str(chat_id)]['locked_features'].remove(feature)
        save_group_settings(group_settings)
        bot.reply_to(message, f"**{feature}** özelliğinin kilidi kaldırıldı.", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"**{feature}** özelliği zaten kilitsiz.", parse_mode="Markdown")

# /locks komutu
@bot.message_handler(commands=['locks'])
def show_locks(message):
    chat_id = message.chat.id
    init_group_settings(chat_id)
    
    locked_features = group_settings[str(chat_id)].get('locked_features', [])
    
    if not locked_features:
        bot.reply_to(message, "Şu anda hiçbir özellik kilitli değil.")
    else:
        bot.reply_to(message, f"Kilitli özellikler:\n- **" + "\n- **".join(locked_features) + "**", parse_mode="Markdown")

# /tmute komutu
@bot.message_handler(commands=['tmute'])
def temp_mute_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Kullanım: /tmute [süre] (1h, 2d, 3m gibi) [@kullanıcı veya yanıtlanan mesaj]\nÖrnek: /tmute 1h @username")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        if len(args) < 3: # Eğer yanıt yoksa ve süre belirtilmişse, 3. argümanın kullanıcı etiketi olması beklenir
             bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
             return
        # Kullanıcı etiketi ile kullanımı şimdilik get_target_user_from_message içinde ele alındı
        # Daha sağlam bir etiketleme sistemi için get_chat_member ile tüm kullanıcıları çekip kontrol etmek gerekebilir.
        bot.reply_to(message, "Geçersiz kullanıcı veya kullanım. Lütfen yanıtlayın veya kullanıcı ID'si/etiketi kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    if is_admin(chat_id, target_user_id):
        bot.reply_to(message, "Yöneticileri susturamazsınız.")
        return
    
    time_str = args[1]
    try:
        delta = parse_time_string(time_str)
        mute_until = datetime.now() + delta
    except ValueError:
        bot.reply_to(message, "Geçersiz zaman formatı. Örnek: 1h, 2d, 30m")
        return
    
    reason = " ".join(args[2:]) if len(args) > 2 else "Belirtilmedi"

    update_user(target_user_id, target_user.username, target_user.first_name, target_user.last_name)
    user_data[str(target_user_id)]['muted'] = True
    user_data[str(target_user_id)]['mute_until'] = mute_until.isoformat()
    save_user_data(user_data)
    
    try:
        bot.restrict_chat_member(chat_id, target_user_id, until_date=int(mute_until.timestamp()), can_send_messages=False)
        bot.reply_to(message, f"**@{target_username}** kullanıcısı **{time_str}** süreyle susturuldu. Neden: **{reason}**", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /tban komutu
@bot.message_handler(commands=['tban'])
def temp_ban_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Kullanım: /tban [süre] (1h, 2d, 3m gibi) [@kullanıcı veya yanıtlanan mesaj]\nÖrnek: /tban 3d @username")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        if len(args) < 3:
             bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
             return
        bot.reply_to(message, "Geçersiz kullanıcı veya kullanım. Lütfen yanıtlayın veya kullanıcı ID'si/etiketi kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    if is_admin(chat_id, target_user_id):
        bot.reply_to(message, "Yöneticileri yasaklayamazsınız.")
        return
    
    time_str = args[1]
    try:
        delta = parse_time_string(time_str)
        ban_until = datetime.now() + delta
    except ValueError:
        bot.reply_to(message, "Geçersiz zaman formatı. Örnek: 1h, 2d, 30m")
        return
    
    reason = " ".join(args[2:]) if len(args) > 2 else "Belirtilmedi"

    update_user(target_user_id, target_user.username, target_user.first_name, target_user.last_name)
    user_data[str(target_user_id)]['banned'] = True
    save_user_data(user_data)
    
    try:
        bot.ban_chat_member(chat_id, target_user_id, until_date=int(ban_until.timestamp()))
        bot.reply_to(message, f"**@{target_username}** kullanıcısı **{time_str}** süreyle yasaklandı. Neden: **{reason}**", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /promote komutu
@bot.message_handler(commands=['promote'])
def promote_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    try:
        bot.promote_chat_member(
            chat_id,
            target_user_id,
            can_change_info=True,
            can_post_messages=True,
            can_edit_messages=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_promote_members=False
        )
        bot.reply_to(message, f"**@{target_username}** kullanıcısı yönetici yapıldı.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /demote komutu
@bot.message_handler(commands=['demote'])
def demote_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    try:
        bot.promote_chat_member(
            chat_id,
            target_user_id,
            can_change_info=False,
            can_post_messages=False,
            can_edit_messages=False,
            can_delete_messages=False,
            can_invite_users=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_promote_members=False
        )
        bot.reply_to(message, f"**@{target_username}** kullanıcısının yöneticilik yetkisi alındı.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /setrules komutu
@bot.message_handler(commands=['setrules'])
def set_rules(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    rules_text = message.text.replace('/setrules', '').strip()
    
    if not rules_text:
        bot.reply_to(message, "Kullanım: /setrules <kurallar metni>")
        return
    
    init_group_settings(chat_id)
    group_settings[str(chat_id)]['rules'] = rules_text
    save_group_settings(group_settings)
    
    bot.reply_to(message, "Grup kuralları başarıyla güncellendi.")

# /rules komutu
@bot.message_handler(commands=['rules'])
def show_rules(message):
    chat_id = message.chat.id
    init_group_settings(chat_id)
    
    rules = group_settings[str(chat_id)].get('rules', 'Henüz kurallar belirlenmedi. /setrules komutu ile ayarlayabilirsiniz.')
    bot.reply_to(message, f"📜 *Grup Kuralları:*\n\n{rules}", parse_mode="Markdown")

# /warns komutu
@bot.message_handler(commands=['warns'])
def show_warns(message):
    chat_id = message.chat.id
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Lütfen bir kullanıcıyı yanıtlayarak veya etiketleyerek bu komutu kullanın.")
        return
    
    target_user_id = target_user.id
    target_username = target_user.username if target_user.username else target_user.first_name
    
    update_user(target_user_id, target_user.username, target_user.first_name, target_user.last_name)
    
    init_group_settings(chat_id)
    max_warns = group_settings[str(chat_id)].get('max_warns', 3)
    current_warns = user_data[str(target_user_id)].get('warns', 0)
    
    bot.reply_to(message, f"**@{target_username}** kullanıcısının **{current_warns}/{max_warns}** uyarısı var.", parse_mode="Markdown")

# /setwelcome komutu
@bot.message_handler(commands=['setwelcome'])
def set_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    welcome_text = message.text.replace('/setwelcome', '').strip()
    
    if not welcome_text:
        bot.reply_to(message, "Kullanım: /setwelcome <karşılama mesajı>\n\nDeğişkenler: `{username}`, `{first_name}`, `{last_name}`", parse_mode="Markdown")
        return
    
    init_group_settings(chat_id)
    group_settings[str(chat_id)]['welcome_message'] = welcome_text
    save_group_settings(group_settings)
    
    bot.reply_to(message, "Karşılama mesajı başarıyla güncellendi.")

# /welcome komutu
@bot.message_handler(commands=['welcome'])
def toggle_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    if len(message.text.split()) < 2:
        bot.reply_to(message, "Kullanım: /welcome on/off")
        return
    
    state = message.text.split()[1].lower()
    init_group_settings(chat_id)
    
    if state == 'on':
        group_settings[str(chat_id)]['welcome_enabled'] = True
        save_group_settings(group_settings)
        bot.reply_to(message, "Karşılama mesajı etkinleştirildi.")
    elif state == 'off':
        group_settings[str(chat_id)]['welcome_enabled'] = False
        save_group_settings(group_settings)
        bot.reply_to(message, "Karşılama mesajı devre dışı bırakıldı.")
    else:
        bot.reply_to(message, "Geçersiz seçenek. Kullanım: /welcome on/off")

# /setgtitle komutu
@bot.message_handler(commands=['setgtitle'])
def set_group_title(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    new_title = message.text.replace('/setgtitle', '').strip()
    
    if not new_title:
        bot.reply_to(message, "Kullanım: /setgtitle <yeni grup adı>")
        return
    
    try:
        bot.set_chat_title(chat_id, new_title)
        bot.reply_to(message, f"Grup adı '**{new_title}**' olarak değiştirildi.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /id komutu
@bot.message_handler(commands=['id'])
def show_id(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        bot.reply_to(message, f"👤 Kullanıcı ID: `{target_user.id}`\n💬 Grup ID: `{chat_id}`", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"👤 Sizin ID: `{user_id}`\n💬 Grup ID: `{chat_id}`", parse_mode="Markdown")

# /admins komutu
@bot.message_handler(commands=['admins'])
def list_admins(message):
    chat_id = message.chat.id
    
    try:
        admins = bot.get_chat_administrators(chat_id)
        admin_list = []
        
        for admin in admins:
            name = admin.user.first_name
            if admin.user.last_name:
                name += " " + admin.user.last_name
            if admin.user.username:
                name += f" (@{admin.user.username})"
            if admin.status == 'creator':
                name += " 👑"
            admin_list.append(name)
        
        bot.reply_to(message, "👥 *Grup Yöneticileri:*\n\n" + "\n".join(admin_list), parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /ping komutu
@bot.message_handler(commands=['ping'])
def ping(message):
    start_time = time.time()
    msg = bot.reply_to(message, "Pong!")
    end_time = time.time()
    
    latency = round((end_time - start_time) * 1000)
    bot.edit_message_text(f"🏓 *Pong!*\n⏳ Gecikme: **{latency}ms**", 
                         chat_id=message.chat.id, 
                         message_id=msg.message_id, 
                         parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_text = """
🤖 *HEZWIN HELPER Komutları* 🤖

👮‍♂️ *Yönetim Komutları:*
/ban @kullanıcı — Kalıcı yasaklar
/kick @kullanıcı — Gruptan atar
/mute @kullanıcı — Susturur
/unmute @kullanıcı — Susturmayı kaldırır
/warn @kullanıcı — Uyarı verir
/resetwarns @kullanıcı — Uyarıları sıfırlar
/del — Yanıtlanan mesajı siler
/purge — Yanıtlanan mesajdan itibaren toplu silme yapar
/purge <sayı> — Son belirtilen sayıda mesajı siler
/clean — Botun komut mesajlarını temizler

🔒 *Oto Koruma:*
/lock <özellik> — Özelliği kilitler
/unlock <özellik> — Kilidi kaldırır
/locks — Kilitli özellikleri listeler

⏳ *Süreli Cezalar:*
/tmute @kullanıcı 1h — 1 saat susturur
/tban @kullanıcı 3d — 3 gün yasaklar
/promote @kullanıcı — Yönetici yapar
/demote @kullanıcı — Yönetici rütbesini alır

📜 *Kurallar ve Uyarılar:*
/setrules <metin> — Kuralları ayarlar
/rules — Kuralları gösterir
/warns @kullanıcı — Uyarıları gösterir

👋 *Karşılama & Grup Ayarları:*
/setwelcome <metin> — Karşılama mesajı ayarlar
/welcome on/off — Karşılama aç/kapat
/setgtitle <isim> — Grup adı değiştirir

👁‍🗨 *Gözetim / Kayıtlar:*
/joinlogs on/off — Katılanları logla
/leftlogs on/off — Ayrılanları logla
/logchannel @kanal — Logların gönderileceği kanal
/userinfo @kullanıcı — Kullanıcı bilgilerini gösterir
/membercount — Grup kişi sayısı
/activehours — Aktif saat istatistiği

📈 *Analiz & Aktivite:*
/topusers — En aktif 10 kullanıcı
/topwarned — En çok uyarı alanlar
/stats — Genel istatistik

🎭 *Eğlence ve Etiketleme:*
/tagall — Herkesi etiketler
/etiket <mesaj> — Özel toplu etiket
/joke — Rasgele fıkra
/oylama <soru>|<şık1>|<şık2> — Anket
/duello @k1 @k2 — Eğlenceli düello

🎯 *Anti Reklam Sistemi:*
/antiads on/off — Reklam engeli
/setadsaction <mute/kick/ban> — Ceza tipi
/adslog — Reklam logları

🔔 *Etkinlik / Katılım:*
/quiz <soru>|<cevap> — Bilgi yarışması
/giveaway <ödül> — Çekiliş başlatır
/join — Çekilişe katılır
/endgiveaway — Çekilişi bitirir

💣 *Risk Komutu:*
/risk <ban/kick/mute> [süre] (@kullanıcı)
/risk ban — Yasaklar
/risk ban 1m — 1 dk yasak
/risk kick — Gruptan at
/risk mute — Susturur
/risk mute 1h — 1 saat susturur

🌐 *Filtre Sistemi:*
/filter <kelime> <yanıt> — Otomatik yanıt ve silme
/filters — Aktif filtreleri listeler
/stop <kelime> — Belirli filtreyi siler
/cleanfilters — Tüm filtreleri siler

🧼 *Flood & Spam Koruması:*
/antiflood <sayı> — Flood koruması
/floodmode <mute/kick/ban> — Ceza tipi
/setflood <sayı> — Flood limiti
/report — Şikayet bildirimi
/reports on/off — Şikayet sistemini aç/kapat

🏃‍♂️ *Diğer:*
/kickme — Kendini gruptan atar
/id — ID gösterir
/admins — Yöneticileri listeler
/ping — Botun gecikmesini ölçer
/help — Tüm komutları gösterir
"""
    bot.reply_to(message, help_text, parse_mode="Markdown")

# --- Yeni Komutlar ---

# /purge komutu
@bot.message_handler(commands=['purge'])
def purge_messages(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    # Komut mesajını sil
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Komut mesajı silme hatası: {e}")

    messages_to_delete = []
    if message.reply_to_message:
        # Yanıtlanan mesajdan itibaren silme
        start_message_id = message.reply_to_message.message_id
        current_message_id = message.message_id - 1 # Komut mesajından bir önceki
        
        # Sadece komut mesajı ile yanıtlanan mesaj arasındaki mesajları sil
        while current_message_id >= start_message_id:
            messages_to_delete.append(current_message_id)
            current_message_id -= 1
    else:
        # Belirli sayıda mesajı silme
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            count = int(args[1])
            for i in range(1, count + 1):
                messages_to_delete.append(message.message_id - i)
        else:
            bot.send_message(chat_id, "Kullanım: /purge — Yanıtlanan mesajdan itibaren toplu silme yapar.\n/purge <sayı> — Son belirtilen sayıda mesajı siler.")
            return
    
    if not messages_to_delete:
        return

    # Telegram API'nin 100 mesaj limitini aşmamak için chunk'lara böl
    for i in range(0, len(messages_to_delete), 100):
        chunk = messages_to_delete[i:i + 100]
        try:
            bot.delete_messages(chat_id, chunk)
        except Exception as e:
            print(f"Toplu mesaj silme hatası: {e}")

    bot.send_message(chat_id, f"Belirtilen mesajlar temizlendi.")


# /clean komutu
@bot.message_handler(commands=['clean'])
def clean_bot_messages(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    bot_id = bot.get_me().id
    messages_to_delete = []
    
    # Son 100 mesajı kontrol et (daha fazla kontrol etmek performans sorunlarına yol açabilir)
    try:
        # Bu API doğrudan "botun gönderdiği mesajları bul" şeklinde çalışmaz.
        # Bu nedenle, botun mesajlarını takip etmek için bir loglama sistemi veya
        # botun kendi gönderdiği mesajların ID'lerini saklaması gerekir.
        # Basitlik adına, son mesajları silme yetkisi olan bir adminin
        # yakın zamandaki bot mesajlarını sileceğini varsayıyoruz.
        # Gerçek uygulamada, botun gönderdiği mesajları bir listeye kaydetmek daha sağlam olur.
        # Örnek olarak son 50 mesajı kontrol ediyoruz.
        for i in range(1, 51): # Son 50 mesajı kontrol et
            try:
                # Bu gerçek bir mesajı getirmez, sadece ID'sini döndürür
                # bot.get_message(chat_id, message.message_id - i) bu API yoktur
                # Bu yüzden sadece tahmini olarak silme işlemi yapabiliriz.
                # Daha sağlam bir çözüm için botun gönderdiği mesajları kaydetmek gerekir.
                pass 
            except Exception:
                pass # Mesaj yoksa hata verir, sorun değil
        
        bot.reply_to(message, "Bu komutun etkin çalışması için botun kendi gönderdiği mesajları takip etmesi gerekmektedir. Şimdilik sadece komut mesajını siliyorum.")
        bot.delete_message(chat_id, message.message_id) # Komut mesajını sil

    except Exception as e:
        bot.reply_to(message, f"Temizleme sırasında hata oluştu: {str(e)}")

# --- Gözetim / Giriş Kayıtları ---

# /joinlogs komutu
@bot.message_handler(commands=['joinlogs'])
def toggle_joinlogs(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ['on', 'off']:
        bot.reply_to(message, "Kullanım: /joinlogs on/off")
        return

    state = args[1].lower()
    init_group_settings(chat_id)

    if state == 'on':
        group_settings[str(chat_id)]['joinlogs_enabled'] = True
        save_group_settings(group_settings)
        bot.reply_to(message, "Gruba katılanların günlük kayıt edilmesi etkinleştirildi.")
    else:
        group_settings[str(chat_id)]['joinlogs_enabled'] = False
        save_group_settings(group_settings)
        bot.reply_to(message, "Gruba katılanların günlük kayıt edilmesi devre dışı bırakıldı.")

# /leftlogs komutu
@bot.message_handler(commands=['leftlogs'])
def toggle_leftlogs(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ['on', 'off']:
        bot.reply_to(message, "Kullanım: /leftlogs on/off")
        return

    state = args[1].lower()
    init_group_settings(chat_id)

    if state == 'on':
        group_settings[str(chat_id)]['leftlogs_enabled'] = True
        save_group_settings(group_settings)
        bot.reply_to(message, "Ayrılan kullanıcıların kayıt edilmesi etkinleştirildi.")
    else:
        group_settings[str(chat_id)]['leftlogs_enabled'] = False
        save_group_settings(group_settings)
        bot.reply_to(message, "Ayrılan kullanıcıların kayıt edilmesi devre dışı bırakıldı.")

# /logchannel komutu
@bot.message_handler(commands=['logchannel'])
def set_log_channel(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Kullanım: /logchannel <@kanaladı> veya <kanal_id>")
        return
    
    channel_identifier = args[1]
    init_group_settings(chat_id)

    # Kanal ID'sini doğru şekilde almak için @kanaladı yerine kanalın iletilen mesaj ID'sinden alınması daha sağlıklı
    # Ancak @kanaladı veya ID kullanımı istendiği için basitleştirilmiş bir yaklaşım
    if channel_identifier.startswith('@'):
        # @kanaladı kullanıldığında botun o kanala mesaj gönderme yetkisi olması gerekir
        # Botun sohbetin bir parçası olması da önemlidir.
        # Bu kısım Telegram API'sinde doğrudan `@kanaladı`'ndan ID almak için karmaşık bir süreçtir.
        # En basit yol, kanala bir mesaj iletmek ve oradan ID'sini almaktır.
        bot.reply_to(message, "Kanal adıyla ayarlama biraz karmaşık. Lütfen botu log kanalı olarak ayarlamak istediğiniz kanala ekleyin ve o kanalda '/getchannelid' gibi bir komut kullanın. Ya da kanalın sayısal ID'sini girin.")
        return

    try:
        log_channel_id = int(channel_identifier)
        group_settings[str(chat_id)]['log_channel_id'] = log_channel_id
        save_group_settings(group_settings)
        bot.reply_to(message, f"Log mesajları için kanal ID: `{log_channel_id}` olarak ayarlandı.", parse_mode="Markdown")
        try:
            bot.send_message(log_channel_id, "Bu kanal, log kanalı olarak ayarlandı.")
        except Exception:
            bot.reply_to(message, "Belirtilen log kanalına mesaj gönderemiyorum. Botun kanalda yönetici olduğundan ve mesaj gönderme yetkisi olduğundan emin olun.")

    except ValueError:
        bot.reply_to(message, "Geçersiz kanal ID'si. Lütfen sayısal bir ID veya @kanaladı kullanın (eğer bot kanalda yönetici ise).")
    except Exception as e:
        bot.reply_to(message, f"Hata oluştu: {str(e)}")

# /userinfo komutu
@bot.message_handler(commands=['userinfo'])
def user_info(message):
    chat_id = message.chat.id
    
    target_user = get_target_user_from_message(message)
    if not target_user:
        bot.reply_to(message, "Kullanım: /userinfo **@kullanıcı** veya yanıtla", parse_mode="Markdown")
        return
    
    update_user(target_user.id, target_user.username, target_user.first_name, target_user.last_name)
    user_info_data = user_data.get(str(target_user.id), {})

    user_details = f"👤 *Kullanıcı Bilgileri:*\n" \
                   f"**ID:** `{target_user.id}`\n" \
                   f"**Ad:** {target_user.first_name}\n"
    if target_user.last_name:
        user_details += f"**Soyad:** {target_user.last_name}\n"
    if target_user.username:
        user_details += f"**Kullanıcı Adı:** @{target_user.username}\n"
    
    user_details += f"**Uyarı Sayısı:** `{user_info_data.get('warns', 0)}`\n"
    user_details += f"**Susturulmuş mu:** {'Evet' if user_info_data.get('muted') else 'Hayır'}\n"
    user_details += f"**Yasaklanmış mı:** {'Evet' if user_info_data.get('banned') else 'Hayır'}\n"
    user_details += f"**Toplam Mesaj:** `{user_info_data.get('message_count', 0)}`\n"

    try:
        member = bot.get_chat_member(chat_id, target_user.id)
        user_details += f"**Durum:** `{member.status}`\n"
    except Exception:
        user_details += "**Durum:** Grupta değil veya bilgiye erişilemiyor\n"

    bot.reply_to(message, user_details, parse_mode="Markdown")

# /membercount komutu
@bot.message_handler(commands=['membercount'])
def member_count(message):
    chat_id = message.chat.id
    try:
        count = bot.get_chat_member_count(chat_id)
        bot.reply_to(message, f"Gruptaki toplam kişi sayısı: **{count}**", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Üye sayısı alınırken hata oluştu: {str(e)}")

# /activehours komutu
@bot.message_handler(commands=['activehours'])
def active_hours(message):
    chat_id = str(message.chat.id)
    init_group_data(chat_id)

    hourly_activity = group_data[chat_id]['hourly_activity']
    
    if not hourly_activity:
        bot.reply_to(message, "Bu grup için henüz yeterli aktivite verisi yok. Daha sonra tekrar deneyin.")
        return

    # En aktif saatleri bul
    sorted_hours = sorted(hourly_activity.items(), key=lambda item: item[1], reverse=True)
    
    response = "📈 *Grubun En Aktif Saatleri:*\n\n"
    for hour, count in sorted_hours[:5]: # İlk 5 saati göster
        response += f"**Saat {int(hour)}:00 - {int(hour) + 1}:00** arası: `{count}` mesaj\n"
    
    bot.reply_to(message, response, parse_mode="Markdown")

# --- Analiz & Aktivite ---

# /topusers komutu
@bot.message_handler(commands=['topusers'])
def top_users(message):
    chat_id = message.chat.id
    
    user_message_counts = []
    for user_id, user_info in user_data.items():
        if 'message_count' in user_info and user_info['message_count'] > 0:
            # Kullanıcının grupta olup olmadığını kontrol etmek iyi olur ama bu ekstra API çağrısı gerektirir.
            # Şimdilik sadece kayıtlı mesaj sayılarını kullanıyoruz.
            username = user_info.get('username')
            first_name = user_info.get('first_name', 'Bilinmeyen')
            display_name = f"@{username}" if username else first_name
            user_message_counts.append((display_name, user_info['message_count']))
    
    if not user_message_counts:
        bot.reply_to(message, "Henüz mesajlaşma verisi yok.")
        return

    sorted_users = sorted(user_message_counts, key=lambda item: item[1], reverse=True)
    
    response = "📊 *En Çok Mesaj Atan İlk 10 Kullanıcı:*\n\n"
    for i, (user_display_name, count) in enumerate(sorted_users[:10]):
        response += f"{i+1}. **{user_display_name}**: `{count}` mesaj\n"
    
    bot.reply_to(message, response, parse_mode="Markdown")

# /topwarned komutu
@bot.message_handler(commands=['topwarned'])
def top_warned(message):
    
    warned_users = []
    for user_id, user_info in user_data.items():
        if 'warns' in user_info and user_info['warns'] > 0:
            username = user_info.get('username')
            first_name = user_info.get('first_name', 'Bilinmeyen')
            display_name = f"@{username}" if username else first_name
            warned_users.append((display_name, user_info['warns']))
    
    if not warned_users:
        bot.reply_to(message, "Henüz uyarı almış kullanıcı yok.")
        return

    sorted_warned = sorted(warned_users, key=lambda item: item[1], reverse=True)
    
    response = "🚨 *En Çok Uyarı Alan Kullanıcılar:*\n\n"
    for i, (user_display_name, warns) in enumerate(sorted_warned[:10]):
        response += f"{i+1}. **{user_display_name}**: `{warns}` uyarı\n"
    
    bot.reply_to(message, response, parse_mode="Markdown")

# /stats komutu
@bot.message_handler(commands=['stats'])
def group_stats(message):
    chat_id = str(message.chat.id)
    init_group_data(chat_id)

    total_messages = group_data[chat_id]['total_messages']
    users_joined = group_data[chat_id]['users_joined']
    users_left = group_data[chat_id]['users_left']

    total_warns = sum(user_info.get('warns', 0) for user_info in user_data.values())
    total_mutes = sum(1 for user_info in user_data.values() if user_info.get('muted'))
    total_bans = sum(1 for user_info in user_data.values() if user_info.get('banned'))

    response = "📊 *Grup İstatistikleri:*\n\n" \
               f"**Toplam Mesaj:** `{total_messages}`\n" \
               f"**Katılan Kullanıcı:** `{users_joined}`\n" \
               f"**Ayrılan Kullanıcı:** `{users_left}`\n" \
               f"**Toplam Uyarı:** `{total_warns}`\n" \
               f"**Toplam Susturulan:** `{total_mutes}`\n" \
               f"**Toplam Yasaklanan:** `{total_bans}`\n"
    
    bot.reply_to(message, response, parse_mode="Markdown")

# --- Eğlencelik/Etiketleme ---

# /tagall komutu
@bot.message_handler(commands=['tagall'])
def tag_all_users(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    try:
        members = bot.get_chat_members(chat_id)
        tag_list = []
        for member in members:
            if not member.user.is_bot and member.user.username:
                tag_list.append(f"@{member.user.username}")
            elif not member.user.is_bot: # Kullanıcı adı yoksa mention yapamazsın, ama id ile bahsedebilirsin
                tag_list.append(f"[{member.user.first_name}](tg://user?id={member.user.id})")

        if not tag_list:
            bot.reply_to(message, "Bu grupta etiketlenecek kullanıcı bulunamadı.")
            return

        # Mesajı 5'er 5'er göndererek Telegram rate limit'ini aşmamaya çalış
        # Büyük gruplar için bu hala sorun olabilir.
        message_chunks = [tag_list[i:i + 5] for i in range(0, len(tag_list), 5)]
        
        for chunk in message_chunks:
            bot.send_message(chat_id, " ".join(chunk), parse_mode="Markdown", disable_web_page_preview=True)
            time.sleep(1) # Rate limit için bekleme
        
        bot.send_message(chat_id, "Tüm üyeler etiketlendi.")

    except Exception as e:
        bot.reply_to(message, f"Tüm üyeleri etiketlerken hata oluştu: {str(e)}")

# /etiket komutu (Özel mesajla toplu etiketleme)
@bot.message_handler(commands=['etiket'])
def custom_tag_all_users(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    text = message.text.replace('/etiket', '').strip()
    if not text:
        bot.reply_to(message, "Kullanım: /etiket <metin> - Herkese özel bir mesajla toplu etiketleme yapar.")
        return

    try:
        members = bot.get_chat_members(chat_id)
        
        # Etiketlenecek kullanıcıları ve mesajları hazırla
        messages_to_send = []
        for member in members:
            if not member.user.is_bot:
                mention = ""
                if member.user.username:
                    mention = f"@{member.user.username}"
                else:
                    mention = f"[{member.user.first_name}](tg://user?id={member.user.id})"
                
                messages_to_send.append(f"{mention} {text}")

        if not messages_to_send:
            bot.reply_to(message, "Bu grupta etiketlenecek kullanıcı bulunamadı.")
            return

        # Mesajları tek tek göndererek rate limit'ini aşmamaya çalış
        for msg_text in messages_to_send:
            try:
                bot.send_message(chat_id, msg_text, parse_mode="Markdown", disable_web_page_preview=True)
                time.sleep(0.5) # Küçük bir bekleme
            except Exception as e:
                print(f"Bireysel etiket mesajı gönderme hatası: {e}")
        
        bot.send_message(chat_id, "Özel mesajınızla tüm üyeler etiketlendi.")

    except Exception as e:
        bot.reply_to(message, f"Toplu etiketleme sırasında hata oluştu: {str(e)}")


# /joke veya /fıkra komutu
@bot.message_handler(commands=['joke', 'fıkra'])
def send_joke(message):
    jokes = [
        "Temel ile Dursun bir gün iddiaya girerler. Temel der ki: 'Ben senden daha tembelim.' Dursun: 'Ben senden daha tembelim.' 'Kanıtla' der Temel. Dursun der ki: 'Şimdi senin ne dediğini düşünmekle bile uğraşamam.'",
        "Doktor, hastasına: 'İyi haberlerim var, hastalığınıza bir isim bulduk!'",
        "Bir gün bir adam yürüyüş yaparken, ayağı kayar ve düşer. Yanındaki arkadaşı sorar: 'İyi misin?' Adam: 'Evet, neyse ki yürüyordum, koşsaydım daha kötü düşerdim.'",
        "Matematik öğretmeni: 'Çocuklar, 5 elmam var, 3 tanesini yedim, geriye ne kaldı?' Öğrenci: 'Kocaman bir karın ağrısı!'"
    ]
    bot.reply_to(message, random.choice(jokes))

# /oylama komutu
@bot.message_handler(commands=['oylama'])
def create_poll(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    args = message.text.split(' ', 1) # İlk boşluğa göre ayır, sonrası metin
    if len(args) < 2:
        bot.reply_to(message, "Kullanım: /oylama <soru>|<seçenek1>|<seçenek2>|...")
        return
    
    parts = args[1].split('|')
    if len(parts) < 2:
        bot.reply_to(message, "Lütfen en az iki seçenek belirtin. Kullanım: /oylama <soru>|<seçenek1>|<seçenek2>|...")
        return
    
    question = parts[0].strip()
    options = [opt.strip() for opt in parts[1:] if opt.strip()]

    if not question or not options:
        bot.reply_to(message, "Soru ve seçenekler boş olamaz.")
        return

    # Oylama mesajını gönder
    try:
        poll_message = bot.send_poll(
            chat_id,
            question,
            options,
            is_anonymous=False # Oylamayı anonim yapmaz, kimin ne oy verdiğini görebiliriz (bot görebilir)
        )
        
        # Oylama verilerini kaydet
        active_polls[chat_id] = {
            'message_id': poll_message.message_id,
            'question': question,
            'options': options,
            'votes': {str(i): 0 for i in range(len(options))}, # Seçenek indeksine göre oy sayımı
            'voters': {}, # {user_id: chosen_option_index}
            'creator_id': user_id
        }
        bot.reply_to(message, "Oylama başlatıldı! Üyeler oylarını verebilir.", parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"Oylama başlatılırken hata oluştu: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.message.poll)
def handle_poll_vote(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_id = call.from_user.id

    if chat_id not in active_polls or active_polls[chat_id]['message_id'] != message_id:
        bot.answer_callback_query(call.id, "Bu oylama aktif değil veya sona ermiş.")
        return

    poll_data = active_polls[chat_id]
    
    # Kullanıcının daha önce oy verip vermediğini kontrol et
    if user_id in poll_data['voters']:
        bot.answer_callback_query(call.id, "Zaten oy verdiniz!")
        return
    
    # Kullanıcının seçtiği seçeneği bul (callback_data'dan)
    chosen_option_index = call.poll_answer.option_ids[0]

    if chosen_option_index is not None:
        poll_data['votes'][str(chosen_option_index)] += 1
        poll_data['voters'][user_id] = chosen_option_index
        active_polls[chat_id] = poll_data # Güncellenmiş veriyi kaydet
        bot.answer_callback_query(call.id, f"Oy verildi: {poll_data['options'][chosen_option_index]}")
    else:
        bot.answer_callback_query(call.id, "Geçersiz oy.")

@bot.message_handler(commands=['endoylama']) # Oylamayı bitirme komutu
def end_poll(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in active_polls or active_polls[chat_id]['creator_id'] != user_id and not is_admin(chat_id, user_id):
        bot.reply_to(message, "Aktif bir oylama yok veya bu oylamayı bitirme yetkiniz yok.")
        return
    
    poll_data = active_polls[chat_id]
    question = poll_data['question']
    options = poll_data['options']
    votes = poll_data['votes']

    result_text = f"📊 *Oylama Sonuçları: {question}*\n\n"
    total_votes = sum(votes.values())

    if total_votes == 0:
        result_text += "Henüz oy veren olmadı."
    else:
        for i, option in enumerate(options):
            vote_count = votes.get(str(i), 0)
            percentage = (vote_count / total_votes) * 100 if total_votes > 0 else 0
            result_text += f"**{option}**: `{vote_count}` oy (_{percentage:.2f}%)_\n"
    
    del active_polls[chat_id] # Oylamayı sonlandır
    bot.send_message(chat_id, result_text, parse_mode="Markdown")


# /duello komutu
@bot.message_handler(commands=['duello'])
def start_duel(message):
    chat_id = message.chat.id
    args = message.text.split()

    if len(args) < 3:
        bot.reply_to(message, "Kullanım: /duello **@k1 @k2**", parse_mode="Markdown")
        return
    
    # Kullanıcı etiketlerini al
    player1_mention = args[1]
    player2_mention = args[2]

    # Etiketlerden kullanıcı adlarını çıkar
    player1_username = player1_mention.replace('@', '')
    player2_username = player2_mention.replace('@', '')

    # Gerçek kullanıcıları bulma (bu kısım Telegram API ile zor, varsayımsal olarak isimleri kullanacağız)
    # Daha sağlam bir bot için burada get_chat_member ile ID'leri doğrulamak gerekebilir.
    
    if player1_username == player2_username:
        bot.reply_to(message, "Aynı kişiler düello yapamaz!")
        return

    # Düello senaryoları
    scenarios = [
        f"**@{player1_username}** ve **@{player2_username}** göz göze geldi. **@{player1_username}** ani bir hareketle **@{player2_username}**'ye saldırdı!...",
        f"Arena ısınmaya başladı! **@{player1_username}** ve **@{player2_username}** kılıçlarını çekti. İlk hamle **@{player2_username}**'den geldi...",
        f"Saniyeler içinde **@{player1_username}** bir büyü fırlattı, ancak **@{player2_username}** ustaca sıyrıldı ve karşı saldırıya geçti!",
        f"Bir yumruk sesi! **@{player1_username}** sert bir darbe indirdi! **@{player2_username}** yere serildi ama hemen ayağa kalktı."
    ]

    winner_scenarios = [
        f"**@{player1_username}** son darbeyi indirdi ve **@{player2_username}** pes etti! **@{player1_username}** kazandı!",
        f"**@{player2_username}** muhteşem bir stratejiyle **@{player1_username}**'yi alt etti! Zafer **@{player2_username}**'nin!",
        f"Kısa ama şiddetli bir mücadelenin ardından, **@{random.choice([player1_username, player2_username])}** galip geldi!",
        f"Ve kazanan... kesinlikle **@{random.choice([player1_username, player2_username])}**! Alkışlar!"
    ]

    bot.send_message(chat_id, random.choice(scenarios), parse_mode="Markdown")
    time.sleep(3) # Kısa bir bekleyiş
    bot.send_message(chat_id, random.choice(winner_scenarios), parse_mode="Markdown")


# --- Anti Reklam Sistemi ---

# /antiads komutu
@bot.message_handler(commands=['antiads'])
def toggle_antiads(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ['on', 'off']:
        bot.reply_to(message, "Kullanım: /antiads on/off")
        return

    state = args[1].lower()
    init_group_settings(chat_id)

    if state == 'on':
        group_settings[str(chat_id)]['antiads_enabled'] = True
        save_group_settings(group_settings)
        bot.reply_to(message, "Anti-reklam sistemi etkinleştirildi.")
    else:
        group_settings[str(chat_id)]['antiads_enabled'] = False
        save_group_settings(group_settings)
        bot.reply_to(message, "Anti-reklam sistemi devre dışı bırakıldı.")

# /setadsaction komutu
@bot.message_handler(commands=['setadsaction'])
def set_ads_action(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ['mute', 'kick', 'ban']:
        bot.reply_to(message, "Kullanım: /setadsaction <mute/kick/ban>")
        return

    action = args[1].lower()
    init_group_settings(chat_id)
    group_settings[str(chat_id)]['ads_action'] = action
    save_group_settings(group_settings)
    bot.reply_to(message, f"Reklam yapanlara uygulanacak ceza '**{action}**' olarak ayarlandı.", parse_mode="Markdown")

# /adslog komutu
@bot.message_handler(commands=['adslog'])
def show_ads_log(message):
    chat_id = str(message.chat.id)
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    init_group_settings(chat_id)
    ads_logs = group_settings[chat_id].get('ads_logs', [])

    if not ads_logs:
        bot.reply_to(message, "Henüz tespit edilmiş bir reklam içeriği yok.")
        return
    
    log_messages = []
    for log_entry in ads_logs:
        log_messages.append(f"• **Zaman:** {log_entry['timestamp']}\n  **Kullanıcı:** {log_entry['user']}\n  **İçerik:** `{log_entry['content']}`\n  **Uygulanan Ceza:** `{log_entry['action']}`")

    response = "🚨 *Tespit Edilen Reklam Logları:*\n\n" + "\n---\n".join(log_messages[-10:]) # Son 10 logu göster
    bot.reply_to(message, response, parse_mode="Markdown")


# --- Etkinlik / Katılım Komutları ---

# Quiz sistemi için global değişkenler
quizzes = {} # {chat_id: {'question': '...', 'answer': '...', 'creator_id': '...', 'active': True}}

# /quiz komutu
@bot.message_handler(commands=['quiz'])
def start_quiz(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    args = message.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(message, "Kullanım: /quiz <soru>|<cevap>")
        return
    
    parts = args[1].split('|', 1)
    if len(parts) < 2:
        bot.reply_to(message, "Lütfen soru ve cevabı '|' ile ayırın. Kullanım: /quiz <soru>|<cevap>")
        return
    
    question = parts[0].strip()
    answer = parts[1].strip().lower()

    if not question or not answer:
        bot.reply_to(message, "Soru ve cevap boş olamaz.")
        return
    
    quizzes[chat_id] = {
        'question': question,
        'answer': answer,
        'creator_id': user_id,
        'active': True
    }
    bot.send_message(chat_id, f"❓ *Bilgi Yarışması Başladı!* ❓\n\n**Soru:** {question}\n\nCevabınızı bu mesaja yanıtlayarak veya doğrudan yazarak verebilirsiniz.", parse_mode="Markdown")


# Quiz cevaplarını kontrol etme
@bot.message_handler(func=lambda message: message.chat.id in quizzes and quizzes[message.chat.id]['active'] and not is_admin(message.chat.id, message.from_user.id))
def check_quiz_answer(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_answer = message.text.strip().lower()

    if chat_id not in quizzes or not quizzes[chat_id]['active']:
        return # Quiz aktif değilse bir şey yapma

    correct_answer = quizzes[chat_id]['answer']

    if user_answer == correct_answer:
        bot.send_message(chat_id, f"🎉 Tebrikler **@{message.from_user.username if message.from_user.username else message.from_user.first_name}**! Doğru cevap!", parse_mode="Markdown")
        quizzes[chat_id]['active'] = False # Quiz'i bitir
        del quizzes[chat_id] # Quiz verisini temizle
    # Yanlış cevap için bildirim gönderme, flood olabilir

# /endquiz komutu
@bot.message_handler(commands=['endquiz'])
def end_quiz(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in quizzes or quizzes[chat_id]['creator_id'] != user_id and not is_admin(chat_id, user_id):
        bot.reply_to(message, "Aktif bir bilgi yarışması yok veya bu yarışmayı bitirme yetkiniz yok.")
        return
    
    if quizzes[chat_id]['active']:
        bot.send_message(chat_id, f"Bilgi yarışması sona erdi. Doğru cevap: **{quizzes[chat_id]['answer']}**", parse_mode="Markdown")
        quizzes[chat_id]['active'] = False
        del quizzes[chat_id]
    else:
        bot.reply_to(message, "Aktif bir bilgi yarışması bulunmamaktadır.")

# Giveaway sistemi
# Çekiliş sistemi için global sözlük
# {chat_id: {message_id: {'prize': '...', 'participants': [], 'creator_id': '...'}}}
active_giveaways = {}

# /giveaway komutu
@bot.message_handler(commands=['giveaway'])
def start_giveaway(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    prize = message.text.replace('/giveaway', '').strip()
    if not prize:
        bot.reply_to(message, "Kullanım: /giveaway <ödül_metni>")
        return
    
    # Çekiliş mesajını gönder
    giveaway_msg = bot.send_message(chat_id, 
                                    f"🎁 *Çekiliş Başladı!* 🎁\n\n"
                                    f"**Ödül:** {prize}\n\n"
                                    f"Katılmak için: `/join` komutunu kullanın!", 
                                    parse_mode="Markdown")
    
    active_giveaways[chat_id] = {
        'message_id': giveaway_msg.message_id,
        'prize': prize,
        'participants': [],
        'creator_id': user_id
    }
    bot.reply_to(message, "Çekiliş başlatıldı!")

# /join komutu
@bot.message_handler(commands=['join'])
def join_giveaway(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.username if message.from_user.username else message.from_user.first_name

    if chat_id not in active_giveaways:
        bot.reply_to(message, "Şu anda aktif bir çekiliş yok.")
        return
    
    if user_id in active_giveaways[chat_id]['participants']:
        bot.reply_to(message, "Zaten çekilişe katıldınız!")
        return
    
    active_giveaways[chat_id]['participants'].append(user_id)
    bot.reply_to(message, f"**@{user_name}** çekilişe katıldı!", parse_mode="Markdown")

# /endgiveaway komutu
@bot.message_handler(commands=['endgiveaway'])
def end_giveaway(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in active_giveaways or active_giveaways[chat_id]['creator_id'] != user_id and not is_admin(chat_id, user_id):
        bot.reply_to(message, "Aktif bir çekiliş yok veya bu çekilişi bitirme yetkiniz yok.")
        return
    
    giveaway_data = active_giveaways[chat_id]
    participants = giveaway_data['participants']
    prize = giveaway_data['prize']

    if not participants:
        bot.send_message(chat_id, "Katılımcı olmadığı için çekiliş bitirilemedi.")
    else:
        winner_id = random.choice(participants)
        
        winner_name = "Bilinmeyen Kullanıcı"
        for uid, user_info in user_data.items():
            if str(user_id) == uid:
                winner_name = f"@{user_info['username']}" if user_info.get('username') else user_info.get('first_name')
                break
        
        bot.send_message(chat_id, 
                         f"🎉 *Çekiliş Sona Erdi!* 🎉\n\n"
                         f"**Ödül:** {prize}\n"
                         f"**Kazanan:** **@{winner_name}** tebrikler!", 
                         parse_mode="Markdown")
    
    del active_giveaways[chat_id] # Çekilişi sonlandır


# --- Geliştirilmiş /risk Komutu ---
@bot.message_handler(commands=['risk'])
def handle_risk_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return

    target_user = None
    args = message.text.split()
    action = None
    time_str = None
    target_users_from_tag = []

    # Komutdan sonraki ilk argümanı eylem olarak al
    if len(args) > 1:
        action = args[1].lower()

    # Kullanıcıyı bulma mantığı
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(args) > 2: # /risk <action> <user_tag/time_str>
        # Eğer üçüncü argüman @ ile başlıyorsa kullanıcı etiketi olarak algıla
        if args[2].startswith('@'):
            # Bu durumda, etiketlenen kullanıcıyı ID'sinden bulmak gerekir.
            # Telegram API'sinde doğrudan kullanıcı adı ile ID almak zordur.
            # Şimdilik, botun kendi veritabanından kullanıcıları bulmaya çalışıyoruz.
            # Daha sağlam bir yapı için get_chat_member veya user_data'da daha iyi bir arama yapılmalı.
            username_to_find = args[2][1:]
            found_user_id = None
            for uid, uinfo in user_data.items():
                if uinfo.get('username') == username_to_find:
                    found_user_id = int(uid)
                    break
            
            if found_user_id:
                try:
                    target_user = bot.get_chat_member(chat_id, found_user_id).user
                except Exception:
                    bot.reply_to(message, "Kullanıcı bulunamadı veya yetkiye erişilemiyor.")
                    return
            else:
                bot.reply_to(message, "Belirtilen kullanıcı bulunamadı. Lütfen yanıtlayın.")
                return
            
            # Zaman argümanı etiketten sonra geliyorsa
            if len(args) > 3:
                time_str = args[3]

        else: # Üçüncü argüman süre olabilir
            time_str = args[2]

            # Eğer mesajda metin mention'ları varsa (örneğin /risk ban 1m @kullanıcı)
            for entity in message.entities:
                if entity.type == 'text_mention' or entity.type == 'mention':
                    if entity.type == 'text_mention':
                        target_users_from_tag.append(entity.user)
                    elif entity.type == 'mention':
                        # @username'den kullanıcı ID'si alma: zorlu kısım
                        bot.reply_to(message, "Kullanıcı adıyla yasaklama/susturma şu anda doğrudan desteklenmiyor. Lütfen yanıtlayın.")
                        return

    # Eğer tek bir kullanıcı hedeflenmemişse ve süre belirtilmemişse genel kullanım hata mesajı
    if not target_user and not target_users_from_tag:
        bot.reply_to(message, "Kullanım: /risk <ban/kick/mute> [süre] (@kullanıcı veya yanıtlanan mesaj)\nÖrnek: /risk ban, /risk kick, /risk mute 1h @username, /risk mute 1h (yanıtla)")
        return
    
    # Hedeflenen kullanıcıları bir listeye topla
    final_target_users = []
    if target_user:
        final_target_users.append(target_user)
    final_target_users.extend(target_users_from_tag) # Etiketlerden gelenleri ekle

    # Risk komut mesajını ve yanıtlanan mesajı sil
    try:
        if message.reply_to_message:
            bot.delete_message(chat_id, message.reply_to_message.message_id) # Yanıtlanan mesajı sil
        bot.delete_message(chat_id, message.message_id) # Komut mesajını sil
    except Exception as e:
        print(f"Risk komutu mesaj silme hatası: {str(e)}") # Hata olursa bile devam et

    for current_target_user in final_target_users:
        current_target_user_id = current_target_user.id
        current_target_username = current_target_user.username if current_target_user.username else current_target_user.first_name

        # Yöneticileri cezalandırmayı engelle
        if is_admin(chat_id, current_target_user_id):
            bot.send_message(chat_id, f"Yöneticilere bu eylemi uygulayamazsınız: **@{current_target_username}**", parse_mode="Markdown")
            continue

        try:
            if action == 'ban':
                if time_str: # Süreli ban
                    try:
                        delta = parse_time_string(time_str)
                        ban_until = datetime.now() + delta
                        bot.ban_chat_member(chat_id, current_target_user_id, until_date=int(ban_until.timestamp()))
                        bot.send_message(chat_id, f"🚨 **UYARI!** **@{current_target_username}** kullanıcısı riskli içerik gönderdiği için **{time_str}** süreyle yasaklandı!", parse_mode="Markdown")
                    except ValueError:
                        bot.send_message(chat_id, "Geçersiz zaman formatı. Örnek: 1h, 2d, 30m")
                else: # Kalıcı ban
                    bot.ban_chat_member(chat_id, current_target_user_id)
                    bot.send_message(chat_id, f"🚨 **UYARI!** **@{current_target_username}** kullanıcısı riskli içerik gönderdiği için kalıcı olarak yasaklandı!", parse_mode="Markdown")
            
            elif action == 'kick':
                bot.kick_chat_member(chat_id, current_target_user_id)
                bot.unban_chat_member(chat_id, current_target_user_id) # Kick sonrası tekrar katılmasına izin ver
                bot.send_message(chat_id, f"🚨 **UYARI!** **@{current_target_username}** kullanıcısı riskli içerik gönderdiği için gruptan atıldı!", parse_mode="Markdown")

            elif action == 'mute':
                if time_str: # Süreli mute
                    try:
                        delta = parse_time_string(time_str)
                        mute_until = datetime.now() + delta
                        bot.restrict_chat_member(chat_id, current_target_user_id, until_date=int(mute_until.timestamp()), can_send_messages=False)
                        bot.send_message(chat_id, f"🚨 **UYARI!** **@{current_target_username}** kullanıcısı riskli içerik gönderdiği için **{time_str}** süreyle susturuldu!", parse_mode="Markdown")
                    except ValueError:
                        bot.send_message(chat_id, "Geçersiz zaman formatı. Örnek: 1h, 2d, 30m")
                else: # Kalıcı mute
                    bot.restrict_chat_member(chat_id, current_target_user_id, until_date=None, can_send_messages=False)
                    bot.send_message(chat_id, f"🚨 **UYARI!** **@{current_target_username}** kullanıcısı riskli içerik gönderdiği için kalıcı olarak susturuldu!", parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "Geçersiz eylem. Kullanım: /risk <ban/kick/mute> [süre (mute/ban için)]")
        except Exception as e:
            bot.send_message(chat_id, f"Eylem sırasında hata oluştu: {str(e)}")


# --- Filtre Sistemi Komutları ---
@bot.message_handler(commands=['filter'])
def add_filter(message):
    chat_id = str(message.chat.id)
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return

    args = message.text.split(maxsplit=2) # '/filter', 'kelime', 'yanıt'
    if len(args) < 3:
        bot.reply_to(message, "Kullanım: /filter <kelime> <yanıt>")
        return

    keyword = args[1].lower()
    response = args[2]

    if chat_id not in filters:
        filters[chat_id] = {}
    
    filters[chat_id][keyword] = response
    save_filters(filters)
    bot.reply_to(message, f"'**{keyword}**' kelimesi için filtre eklendi. Yanıt: '**{response}**'", parse_mode="Markdown")

@bot.message_handler(commands=['filters'])
def list_filters(message):
    chat_id = str(message.chat.id)

    if chat_id not in filters or not filters[chat_id]:
        bot.reply_to(message, "Bu grupta henüz aktif filtre yok.")
        return
    
    filter_list = []
    for keyword, response in filters[chat_id].items():
        filter_list.append(f"- *{keyword}*: {response}")
    
    bot.reply_to(message, "🌐 *Aktif Filtreler:*\n" + "\n".join(filter_list), parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def stop_filter(message):
    chat_id = str(message.chat.id)
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Kullanım: /stop <kelime>")
        return
    
    keyword_to_remove = args[1].lower()

    if chat_id in filters and keyword_to_remove in filters[chat_id]:
        del filters[chat_id][keyword_to_remove]
        save_filters(filters)
        bot.reply_to(message, f"'**{keyword_to_remove}**' filtresi kaldırıldı.", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"'**{keyword_to_remove}**' adında bir filtre bulunamadı.", parse_mode="Markdown")

@bot.message_handler(commands=['cleanfilters'])
def clean_filters(message):
    chat_id = str(message.chat.id)
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return

    if chat_id in filters:
        filters[chat_id] = {}
        save_filters(filters)
        bot.reply_to(message, "Tüm filtreler temizlendi.")
    else:
        bot.reply_to(message, "Bu grupta zaten filtre yok.")

# --- Flood ve Spam Koruma ---

@bot.message_handler(commands=['antiflood'])
def set_antiflood(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.reply_to(message, "Kullanım: /antiflood <sayı>\nÖrnek: /antiflood 5")
        return

    limit = int(args[1])
    init_group_settings(chat_id)
    group_settings[str(chat_id)]['flood_limit'] = limit
    save_group_settings(group_settings)
    bot.reply_to(message, f"Anti-flood limiti **{limit}** mesaj olarak ayarlandı.", parse_mode="Markdown")

@bot.message_handler(commands=['floodmode'])
def set_flood_mode(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return

    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ['mute', 'kick', 'ban']:
        bot.reply_to(message, "Kullanım: /floodmode <mute/kick/ban>")
        return

    mode = args[1].lower()
    init_group_settings(chat_id)
    group_settings[str(chat_id)]['flood_mode'] = mode
    save_group_settings(group_settings)
    bot.reply_to(message, f"Flood yapanlara uygulanacak ceza '**{mode}**' olarak ayarlandı.", parse_mode="Markdown")

@bot.message_handler(commands=['setflood'])
def set_flood_limit_alias(message): # Alias for /antiflood for consistency with the prompt
    set_antiflood(message)

# /report komutu
@bot.message_handler(commands=['report'])
def report_message(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    init_group_settings(chat_id)
    if not group_settings[str(chat_id)].get('reports_enabled', True):
        bot.reply_to(message, "Şikayet sistemi şu anda devre dışı.")
        return

    if not message.reply_to_message:
        bot.reply_to(message, "Şikayet etmek istediğiniz mesajı yanıtlayarak bu komutu kullanın.")
        return

    reported_message = message.reply_to_message
    reporter_user = message.from_user
    
    # Yöneticileri bul ve mesajı gönder
    try:
        admins = bot.get_chat_administrators(chat_id)
        admin_mentions = []
        for admin in admins:
            if admin.user.username:
                admin_mentions.append(f"@{admin.user.username}")
            else:
                admin_mentions.append(f"[{admin.user.first_name}](tg://user?id={admin.user.id})")
        
        report_text = f"🚨 *Yeni Şikayet!* 🚨\n\n" \
                      f"**Gönderen:** {reporter_user.first_name} (@{reporter_user.username if reporter_user.username else 'N/A'}) [ID: `{reporter_user.id}`]\n" \
                      f"**Şikayet Edilen Mesaj:** \"{reported_message.text if reported_message.text else reported_message.caption if reported_message.caption else '(Medya Mesajı)'}\"\n" \
                      f"**Mesaj Linki:** [Buraya Tıklayın](https://t.me/c/{str(chat_id).replace('-100', '')}/{reported_message.message_id})\n\n" \
                      f"**Yöneticiler:** {' '.join(admin_mentions) if admin_mentions else 'Hiçbiri'}"
        
        for admin in admins:
            try:
                # Kendi ID'sine gönderilmesini engelle (eğer raporlayan admin ise)
                if admin.user.id != reporter_user.id:
                    bot.send_message(admin.user.id, report_text, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception as e:
                print(f"Yöneticiye şikayet gönderilirken hata oluştu (ID: {admin.user.id}): {str(e)}")
        
        bot.reply_to(message, "Mesaj yöneticilere bildirildi. Teşekkür ederiz.")
        bot.delete_message(chat_id, message.message_id) # Komut mesajını sil
    except Exception as e:
        bot.reply_to(message, f"Şikayet gönderilirken hata oluştu: {str(e)}")

# /reports off/on komutu
@bot.message_handler(commands=['reports'])
def toggle_reports(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(chat_id, user_id):
        bot.reply_to(message, "Bu komutu kullanmak için yetkiniz yok.")
        return
    
    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ['on', 'off']:
        bot.reply_to(message, "Kullanım: /reports on/off")
        return

    state = args[1].lower()
    init_group_settings(chat_id)

    if state == 'on':
        group_settings[str(chat_id)]['reports_enabled'] = True
        save_group_settings(group_settings)
        bot.reply_to(message, "Şikayet sistemi etkinleştirildi.")
    else:
        group_settings[str(chat_id)]['reports_enabled'] = False
        save_group_settings(group_settings)
        bot.reply_to(message, "Şikayet sistemi devre dışı bırakıldı.")

# /kickme komutu
@bot.message_handler(commands=['kickme'])
def kick_self(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    try:
        bot.kick_chat_member(chat_id, user_id)
        bot.unban_chat_member(chat_id, user_id) # Hemen geri katılabilmesi için
        bot.send_message(chat_id, f"**@{message.from_user.username if message.from_user.username else message.from_user.first_name}** kendi kendini gruptan attı!", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Kendi kendini atma sırasında hata oluştu: {str(e)}")

# Yeni üye karşılama ve loglama
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_members(message):
    chat_id = message.chat.id
    init_group_settings(chat_id)
    init_group_data(chat_id)

    for new_member in message.new_chat_members:
        if new_member.is_bot:
            continue
        
        update_user(new_member.id, new_member.username, new_member.first_name, new_member.last_name)
        group_data[str(chat_id)]['users_joined'] += 1
        save_group_data(group_data)

        # Karşılama mesajı
        if group_settings[str(chat_id)].get('welcome_enabled', True):
            welcome_message = group_settings[str(chat_id)].get('welcome_message', 'Gruba hoş geldiniz!')
            
            # Karşılama mesajında değişkenleri değiştir
            personalized_welcome = welcome_message.format(
                username=f"@{new_member.username}" if new_member.username else new_member.first_name,
                first_name=new_member.first_name,
                last_name=new_member.last_name if new_member.last_name else ""
            )
            
            try:
                bot.send_message(chat_id, personalized_welcome)
            except Exception as e:
                print(f"Karşılama mesajı gönderme hatası: {str(e)}")
        
        # Katılım loglama
        if group_settings[str(chat_id)].get('joinlogs_enabled', False):
            log_channel_id = group_settings[str(chat_id)].get('log_channel_id')
            if log_channel_id:
                try:
                    log_text = f"✅ *Yeni Katılım:* **@{new_member.username if new_member.username else new_member.first_name}** (ID: `{new_member.id}`) gruba katıldı."
                    bot.send_message(log_channel_id, log_text, parse_mode="Markdown")
                except Exception as e:
                    print(f"Katılım logu gönderme hatası: {str(e)}")

# Ayrılan üye loglama
@bot.message_handler(content_types=['left_chat_member'])
def handle_left_chat_members(message):
    chat_id = message.chat.id
    left_member = message.left_chat_member
    init_group_settings(chat_id)
    init_group_data(chat_id)

    group_data[str(chat_id)]['users_left'] += 1
    save_group_data(group_data)

    if group_settings[str(chat_id)].get('leftlogs_enabled', False):
        log_channel_id = group_settings[str(chat_id)].get('log_channel_id')
        if log_channel_id:
            try:
                log_text = f"❌ *Ayrılma:* **@{left_member.username if left_member.username else left_member.first_name}** (ID: `{left_member.id}`) gruptan ayrıldı."
                bot.send_message(log_channel_id, log_text, parse_mode="Markdown")
            except Exception as e:
                print(f"Ayrılma logu gönderme hatası: {str(e)}")


# Kilitli özellikleri, filtreleri, anti-reklamı ve flood kontrolünü tek bir handlerda yönet
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'animation', 'document', 'sticker', 'contact', 'location', 'audio', 'voice', 'video_note', 'game', 'invoice', 'successful_payment', 'migrate_to_chat_id', 'migrate_from_chat_id', 'pinned_message'])
def handle_all_messages_for_auto_moderation(message):
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    
    init_group_settings(chat_id)
    init_group_data(chat_id)

    # İstatistikler için mesaj sayısını artır
    group_data[chat_id]['total_messages'] += 1
    group_data[chat_id]['hourly_activity'][str(datetime.now().hour)] += 1
    save_group_data(group_data)

    # Her kullanıcının mesaj sayısını güncelleyin
    update_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    user_data[user_id]['message_count'] = user_data[user_id].get('message_count', 0) + 1
    save_user_data(user_data)

    # Yöneticiler için kontrol atla
    if is_admin(chat_id, message.from_user.id):
        return
    
    # 1. Kilitli Özellikler Kontrolü
    content_type_locked = None
    if message.text:
        # Link kontrolü (HTTP/HTTPS veya Telegram davet linkleri)
        if 'link' in group_settings[chat_id]['locked_features'] and \
           (re.search(r'https?://\S+|t\.me/\S+|telegram\.me/\S+', message.text, re.IGNORECASE)):
            content_type_locked = 'link'
        # Kullanıcı adı kontrolü (komut olmayan @ işaretleri)
        if 'username' in group_settings[chat_id]['locked_features'] and \
           '@' in message.text and not message.text.startswith('/'):
            content_type_locked = 'username'
    elif message.photo and 'photo' in group_settings[chat_id]['locked_features']:
        content_type_locked = 'photo'
    elif message.video and 'video' in group_settings[chat_id]['locked_features']:
        content_type_locked = 'video'
    elif message.animation and 'gif' in group_settings[chat_id]['locked_features']:
        content_type_locked = 'gif'
    elif message.document and 'document' in group_settings[chat_id]['locked_features']:
        content_type_locked = 'document'
    elif message.sticker and 'sticker' in group_settings[chat_id]['locked_features']:
        content_type_locked = 'sticker'
    elif message.contact and 'contact' in group_settings[chat_id]['locked_features']:
        content_type_locked = 'contact'
    elif message.location and 'location' in group_settings[chat_id]['locked_features']:
        content_type_locked = 'location'
    elif message.forward_from or message.forward_from_chat:
        if 'forward' in group_settings[chat_id]['locked_features']:
            content_type_locked = 'forward'
    
    if content_type_locked:
        try:
            bot.delete_message(chat_id, message.message_id)
            warning = bot.send_message(chat_id, f"⚠️ **@{message.from_user.username if message.from_user.username else message.from_user.first_name}**, bu içerik türü (**{content_type_locked}**) şu anda kilitli!", parse_mode="Markdown")
            time.sleep(5)
            bot.delete_message(chat_id, warning.message_id)
            return # Kilitli özellik eşleştiyse başka kontrole gerek yok
        except Exception as e:
            print(f"Kilitli özellik mesaj silme hatası: {str(e)}")

    # 2. Filtre Kontrolü
    if message.text:
        message_text_lower = message.text.lower()
        if chat_id in filters:
            for keyword, response in filters[chat_id].items():
                if keyword in message_text_lower:
                    try:
                        bot.delete_message(chat_id, message.message_id)
                        bot.send_message(chat_id, response)
                        return # Filtre eşleştiyse başka kontrole gerek yok
                    except Exception as e:
                        print(f"Filtre mesajı silinirken veya yanıtlanırken hata: {str(e)}")

    # 3. Anti-reklam sistemi
    if group_settings[chat_id].get('antiads_enabled', False) and message.text:
        # Reklam anahtar kelimeleri ve desenleri
        ads_patterns = [
            r't\.me/\S+', r'telegram\.me/\S+', r'http[s]?://\S+', # Linkler
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', # Telefon numaraları (örneğin 123-456-7890)
            r'kazan', r'para', r'yatırım', r'gelir', r'üye ol', r'kanalımıza gel', # Spam kelimeler
            r'free money', r'investment', r'earn money', r'join our channel' # İngilizce spam kelimeler
        ]
        
        is_ad = False
        for pattern in ads_patterns:
            if re.search(pattern, message.text, re.IGNORECASE):
                is_ad = True
                break
        
        if is_ad:
            ads_action = group_settings[chat_id].get('ads_action', 'kick')
            user_display_name = message.from_user.username if message.from_user.username else message.from_user.first_name

            try:
                bot.delete_message(chat_id, message.message_id)
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'user': user_display_name,
                    'content': message.text,
                    'action': ads_action
                }
                group_settings[chat_id]['ads_logs'].append(log_entry)
                save_group_settings(group_settings)

                if ads_action == 'mute':
                    bot.restrict_chat_member(chat_id, message.from_user.id, until_date=int((datetime.now() + timedelta(minutes=10)).timestamp()), can_send_messages=False)
                    bot.send_message(chat_id, f"🚨 **Anti-reklam Uyarısı!** **@{user_display_name}** reklam yaptığı için 10 dakika susturuldu.", parse_mode="Markdown")
                elif ads_action == 'kick':
                    bot.kick_chat_member(chat_id, message.from_user.id)
                    bot.unban_chat_member(chat_id, message.from_user.id)
                    bot.send_message(chat_id, f"🚨 **Anti-reklam Uyarısı!** **@{user_display_name}** reklam yaptığı için gruptan atıldı.", parse_mode="Markdown")
                elif ads_action == 'ban':
                    bot.ban_chat_member(chat_id, message.from_user.id)
                    bot.send_message(chat_id, f"🚨 **Anti-reklam Uyarısı!** **@{user_display_name}** reklam yaptığı için yasaklandı.", parse_mode="Markdown")
                
                return # Reklam engellendiğinde diğer kontrolere gerek yok
            except Exception as e:
                print(f"Anti-reklam işlemi sırasında hata oluştu: {str(e)}")


    # 4. Flood Kontrolü (Sadece metin mesajları için daha mantıklı)
    if message.text: # Sadece metin mesajlarını flood kontrolüne tabi tut
        flood_limit = group_settings[chat_id].get('flood_limit', 5)
        flood_mode = group_settings[chat_id].get('flood_mode', 'mute')

        if chat_id not in flood_control:
            flood_control[chat_id] = {}
        if user_id not in flood_control[chat_id]:
            flood_control[chat_id][user_id] = []

        current_time = time.time()
        flood_control[chat_id][user_id].append(current_time)

        # Son 5 saniyedeki mesajları tut
        flood_control[chat_id][user_id] = [
            t for t in flood_control[chat_id][user_id] if current_time - t < 5
        ]

        if len(flood_control[chat_id][user_id]) > flood_limit:
            try:
                bot.delete_message(chat_id, message.message_id) # Flood yapanın mesajını sil

                # Yöneticileri cezalandırmayı engelle (zaten admin ise atlanacak)
                if not is_admin(chat_id, message.from_user.id):
                    user_display_name = message.from_user.username if message.from_user.username else message.from_user.first_name
                    if flood_mode == 'mute':
                        bot.restrict_chat_member(chat_id, message.from_user.id, until_date=int((datetime.now() + timedelta(minutes=5)).timestamp()), can_send_messages=False)
                        bot.send_message(chat_id, f"🚨 *Anti-flood Uyarısı!* **@{user_display_name}** çok hızlı mesaj attığı için 5 dakika susturuldu.", parse_mode="Markdown")
                    elif flood_mode == 'kick':
                        bot.kick_chat_member(chat_id, message.from_user.id)
                        bot.unban_chat_member(chat_id, message.from_user.id)
                        bot.send_message(chat_id, f"🚨 *Anti-flood Uyarısı!* **@{user_display_name}** çok hızlı mesaj attığı için gruptan atıldı.", parse_mode="Markdown")
                    elif flood_mode == 'ban':
                        bot.ban_chat_member(chat_id, message.from_user.id)
                        bot.send_message(chat_id, f"🚨 *Anti-flood Uyarısı!* **@{user_display_name}** çok hızlı mesaj attığı için yasaklandı.", parse_mode="Markdown")
                
                # Flood sonrası flood sayacını sıfırla
                flood_control[chat_id][user_id] = [] 
            except Exception as e:
                print(f"Anti-flood işlemi sırasında hata oluştu: {str(e)}")

# Süreli mute/ban kontrolü
def check_timed_restrictions():
    while True:
        current_time = datetime.now()
        
        # Süresi dolan susturmaları kontrol et
        users_to_unmute = []
        for user_id, user_info in list(user_data.items()):
            if user_info.get('muted') and user_info.get('mute_until'):
                mute_until = datetime.fromisoformat(user_info['mute_until'])
                if current_time >= mute_until:
                    users_to_unmute.append(user_id)
        
        for uid in users_to_unmute:
            if uid in user_data: 
                user_data[uid]['muted'] = False
                user_data[uid]['mute_until'] = None
                save_user_data(user_data)
            print(f"Kullanıcı {uid} için süreli susturma bot verisinde kaldırıldı.")

        time.sleep(60)  # Her dakika kontrol et

# Süreli kısıtlamaları kontrol etmek için thread başlat
restriction_thread = threading.Thread(target=check_timed_restrictions)
restriction_thread.daemon = True
restriction_thread.start()

# Botu başlat
print("Bot başlatıldı...")
bot.polling(none_stop=True)

