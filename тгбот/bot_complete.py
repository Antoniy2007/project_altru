import http.client
import json
import time
import sqlite3
import urllib.parse

# Настройки
BOT_TOKEN = "8388489190:AAH3S8KE3Fvw6v8JcOStoiS4U2CsVjQ6dVE"
ADMIN_IDS = [2035361591, 1139652841,5064564101,1687624123,1201446229]

MOSCOW_DISTRICTS = [
    "ЦАО", "САО", "СВАО", "ВАО", "ЮВАО", 
    "ЮАО", "ЮЗАО", "ЗАО", "СЗАО", "Троицкий", "Новомосковский"
]

PROBLEM_TYPES = [
    "Настройка звука",
    "Установка приложений", 
    "Проблемы с интернетом",
    "Синхронизация устройств",
    "Другое"
]

def init_db():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            problem_type TEXT,
            district TEXT,
            details TEXT,
            status TEXT DEFAULT 'new',
            volunteer_id INTEGER,
            rating INTEGER,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS volunteers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            user_name TEXT,
            district TEXT,
            is_active BOOLEAN DEFAULT 1,
            completed_requests INTEGER DEFAULT 0,
            rating_avg REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

def telegram_api(method, params=None):
    try:
        conn = http.client.HTTPSConnection("api.telegram.org")
        query = ""
        if params:
            query = "?" + urllib.parse.urlencode(params)
        
        conn.request("GET", f"/bot{BOT_TOKEN}/{method}{query}")
        response = conn.getresponse()
        data = response.read().decode()
        conn.close()
        
        return json.loads(data)
    except Exception as e:
        print(f"Ошибка API: {e}")
        return {"ok": False, "result": []}

def send_message(chat_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "text": text}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    result = telegram_api("sendMessage", params)
    print(f"📤 Отправлено сообщение {chat_id}: {text[:50]}...")
    return result

def get_updates(offset=None):
    params = {"timeout": 60}
    if offset:
        params["offset"] = offset
    return telegram_api("getUpdates", params)

def save_request(user_id, first_name, username, problem_type, district, details=""):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    # Сохраняем оба имени в базу - используем username если есть, иначе first_name
    user_display_name = f"@{username}" if username else first_name
    cur.execute('''
        INSERT INTO requests (user_id, user_name, problem_type, district, details) 
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, user_display_name, problem_type, district, details))
    
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    # Логирование
    import os
    from datetime import datetime
    
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    with open('logs/requests_log.txt', 'a', encoding='utf-8') as f:
        log_line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Заявка #{request_id} | "
        if username:
            log_line += f"Username: @{username} | "
        log_line += f"Имя: {first_name} | ID: {user_id} | Проблема: {problem_type} | Район: {district} | Детали: {details}\n"
        f.write(log_line)
    
    # Уведомление админам
    for admin_id in ADMIN_IDS:
        message = f"🚨 НОВАЯ ЗАЯВКА #{request_id}\n👤 Имя: {first_name}\n"
        
        if username:
            message += f"👤 Username: @{username}\n"
            
        message += f"🔧 Проблема: {problem_type}\n📍 Район: {district}\n📝 Детали: {details}"
        
        send_message(admin_id, message)
    
    return request_id



def main():
    init_db()
    last_update_id = None
    user_states = {}
    processed_updates = set()  # Множество для отслеживания обработанных сообщений
    
    print("🤖 Бот запущен! Ищите: t.me/altrumsk_bot")
    
    while True:
        try:
            # Получаем обновления с правильным offset
            updates = get_updates(last_update_id)
            
            if updates.get("ok") and updates["result"]:
                for update in updates["result"]:
                    current_update_id = update["update_id"]
                    
                    # Пропускаем уже обработанные сообщения
                    if current_update_id in processed_updates:
                        print(f"⏩ Пропущено дублирующее сообщение ID: {current_update_id}")
                        continue
                    
                    # Добавляем в обработанные
                    processed_updates.add(current_update_id)
                    
                    # Обновляем last_update_id
                    last_update_id = current_update_id + 1
                    
                    # Проверяем что это текстовое сообщение
                    if "message" not in update or "text" not in update["message"]:
                        continue

                    chat_id = update["message"]["chat"]["id"]
                    user_data = update["message"]["chat"]
                    first_name = user_data.get("first_name", "Пользователь")  # ⭐ Настоящее имя
                    username = user_data.get("username", "")  # ⭐ username
                    user_display_name = f"@{username}" if username else first_name  # ⭐ Для отображения
                    text = update["message"].get("text", "").strip()

                    print(f"📨 Обрабатывается сообщение от {first_name}({chat_id}): {text}")  # ⭐ Используем first_name
                    
                    # Обработка команд пользователя
                    if text == "/start":
                        # Отправляем только ОДНО приветственное сообщение
                        send_message(chat_id, 
                                    "👋 Привет! Я бот помощи пожилым людям.\n\n"
                                    "Выберите тип проблемы:")
                        
                        keyboard = {
                            "keyboard": [[{"text": pt}] for pt in PROBLEM_TYPES],
                            "resize_keyboard": True
                        }
                        send_message(chat_id, "Выберите вариант:", keyboard)
                        user_states[chat_id] = "waiting_problem"
                        print(f"🔄 Состояние пользователя {chat_id}: waiting_problem")
                    
                    elif user_states.get(chat_id) == "waiting_problem":
                        if text in PROBLEM_TYPES:
                            user_states[f"{chat_id}_problem"] = text
                            user_states[chat_id] = "waiting_district"
                            
                            districts_kb = []
                            for i in range(0, len(MOSCOW_DISTRICTS), 2):
                                row = [{"text": MOSCOW_DISTRICTS[i]}]
                                if i + 1 < len(MOSCOW_DISTRICTS):
                                    row.append({"text": MOSCOW_DISTRICTS[i + 1]})
                                districts_kb.append(row)
                            
                            keyboard = {"keyboard": districts_kb, "resize_keyboard": True}
                            send_message(chat_id, "📍 Выберите ваш район Москвы:", keyboard)
                            print(f"🔄 Состояние пользователя {chat_id}: waiting_district")
                        else:
                            send_message(chat_id, "Пожалуйста, выберите вариант из списка")
                    
                    elif user_states.get(chat_id) == "waiting_district":
                        if text in MOSCOW_DISTRICTS:
                            district = text
                            problem_type = user_states.get(f"{chat_id}_problem")
                            
                            user_states[chat_id] = "waiting_details"
                            send_message(chat_id, 
                                        "📝 Опишите проблему подробнее:",
                                        {"remove_keyboard": True})
                            user_states[f"{chat_id}_district"] = district
                            print(f"🔄 Состояние пользователя {chat_id}: waiting_details")
                        else:
                            send_message(chat_id, "Пожалуйста, выберите район из списка")
                    
                    elif user_states.get(chat_id) == "waiting_details":
                        details = text
                        problem_type = user_states.get(f"{chat_id}_problem")
                        district = user_states.get(f"{chat_id}_district")
                        
                        request_id = save_request(chat_id, first_name, username, problem_type, district, details)
                        
                        send_message(chat_id, 
                                    f"✅ Заявка #{request_id} принята!\n\n"
                                    f"📋 Тип проблемы: {problem_type}\n"
                                    f"📍 Район: {district}\n"
                                    f"📝 Описание: {details}\n\n"
                                    f"⏳ Ожидайте связи волонтера.")
                        
                        # Сбрасываем состояние
                        user_states[chat_id] = None
                        for key in [f"{chat_id}_problem", f"{chat_id}_district"]:
                            if key in user_states:
                                del user_states[key]
                        print(f"🔄 Состояние пользователя {chat_id}: сброшено")
                    
                    else:
                        if text.startswith("/"):
                            send_message(chat_id, "Отправьте /start для создания новой заявки")
            
            # Очищаем старые processed_updates чтобы не накапливать слишком много
            if len(processed_updates) > 1000:
                processed_updates = set()
            
            time.sleep(0.5)  # Уменьшаем задержку
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()