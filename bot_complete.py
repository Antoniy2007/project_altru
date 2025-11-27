import http.client
import json
import time
import sqlite3
import urllib.parse
import os
import requests
from datetime import datetime

# Настройки
BOT_TOKEN = "8388489190:AAH3S8KE3Fvw6v8JcOStoiS4U2CsVjQ6dVE"
ADMIN_IDS = [2035361591, 1139652841, 5064564101, 1687624123, 1201446229]

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
    """Простая инициализация - предполагаем что база уже создана"""
    try:
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        # Проверяем что таблица requests существует
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='requests'")
        if not cur.fetchone():
            print("❌ Таблица 'requests' не найдена! Создайте базу через create_new_database.py")
            return False
        conn.close()
        print("✅ База данных подключена")
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к базе: {e}")
        return False

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

def download_file(file_id, filename):
    """Скачивает файл с Telegram сервера"""
    try:
        # Получаем информацию о файе
        file_info = telegram_api("getFile", {"file_id": file_id})
        if not file_info.get("ok"):
            print(f"❌ Ошибка получения file_info: {file_info}")
            return False
            
        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        
        print(f"📥 Скачиваем файл: {file_url}")
        
        # Скачиваем файл
        response = requests.get(file_url, timeout=30)
        if response.status_code == 200:
            # Создаем папку если нет
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"✅ Файл сохранен: {filename}")
            return True
        else:
            print(f"❌ Ошибка HTTP: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка скачивания файла: {e}")
        return False

def send_message(chat_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "text": text}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    return telegram_api("sendMessage", params)

def get_updates(offset=None):
    params = {"timeout": 60}
    if offset:
        params["offset"] = offset
    return telegram_api("getUpdates", params)

def save_request_with_photo(user_id, first_name, username, problem_type, district, details="", photo_filename=None):
    """Сохраняет заявку с фото"""
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    user_display_name = f"@{username}" if username else first_name
    cur.execute('''
        INSERT INTO requests (user_id, user_name, problem_type, district, details, photo_filename) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, user_display_name, problem_type, district, details, photo_filename))
    
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    return request_id

def main():
    if not init_db():
        return
    
    last_update_id = None
    user_states = {}
    processed_updates = set()
    
    # Создаем необходимые папки
    os.makedirs('logs', exist_ok=True)
    os.makedirs('photos', exist_ok=True)
    
    print("🤖 Бот запущен! Ищите: t.me/altrumsk_bot")
    
    while True:
        try:
            updates = get_updates(last_update_id)
            
            if updates.get("ok") and updates["result"]:
                for update in updates["result"]:
                    current_update_id = update["update_id"]
                    
                    if current_update_id in processed_updates:
                        continue
                    
                    processed_updates.add(current_update_id)
                    last_update_id = current_update_id + 1
                    
                    chat_id = update["message"]["chat"]["id"]
                    user_data = update["message"]["chat"]
                    first_name = user_data.get("first_name", "Пользователь")
                    username = user_data.get("username", "")
                    
                    # Обработка текстовых сообщений
                    if "text" in update["message"]:
                        text = update["message"]["text"].strip()
                        print(f"📨 Текст от {first_name}({chat_id}): {text}")
                        
                        # Обработка команд пользователя
                        if text == "/start" or text == "🚀 Старт":
                            send_message(chat_id, 
                                        "👋 Привет! Я бот помощи пожилым людям.\n\n"
                                        "Выберите тип проблемы:")
                            
                            keyboard = {
                                "keyboard": [
                                    [{"text": "📖 Узнать подробнее о движении"}],  # ⭐ НОВАЯ КНОПКА
                                    *[[{"text": pt}] for pt in PROBLEM_TYPES],
                                    [{"text": "🔙 Назад"}]
                                ],
                                "resize_keyboard": True
                            }
                            send_message(chat_id, "Выберите вариант:", keyboard)
                            user_states[chat_id] = "waiting_problem"
                        
                        # ⭐ ОБРАБОТКА КНОПКИ "УЗНАТЬ ПОДРОБНЕЕ О ДВИЖЕНИИ"
                        elif text == "📖 Узнать подробнее о движении":
                            about_text = (
                                "📌 Проект «Altru» — система оперативной цифровой\n"
                                "поддержки для жителей Москвы.\n\n"
                                "📱 Пользователи подают заявки через Telegram-бота, сайт или телефон при возникновении технических проблем. Система автоматически распределяет запросы среди обученных добровольцев.\n\n"
                                "🤝 Волонтер связывается с пользователем и в течение 24 часов оказывает помощь дистанционно или лично.\n\n"
                                "⏳ Проект решает сиюминутные проблемы, а не\n"
                                "обучает, что особенно важно для людей с ограниченной мобильностью."
                            )
                            send_message(chat_id, about_text)
                            
                            # ⭐ УБРАЛИ ПОВТОРНОЕ СООБЩЕНИЕ "Выберите тип проблемы"
                            # Просто остаемся в том же состоянии с той же клавиатурой
                        
                        elif text == "🔙 Назад":
                            current_state = user_states.get(chat_id)
                            
                            if current_state == "waiting_problem":
                                send_message(chat_id, 
                                            "👋 Привет! Я бот помощи пожилым людям.\n\n"
                                            "Выберите тип проблемы:")
                                
                                keyboard = {
                                    "keyboard": [
                                        [{"text": "📖 Узнать подробнее о движении"}],
                                        *[[{"text": pt}] for pt in PROBLEM_TYPES],
                                        [{"text": "🔙 Назад"}]
                                    ],
                                    "resize_keyboard": True
                                }
                                send_message(chat_id, "Выберите вариант:", keyboard)
                                user_states[chat_id] = "waiting_problem"
                                
                            elif current_state == "waiting_district":
                                send_message(chat_id, "Выберите тип проблемы:")
                                keyboard = {
                                    "keyboard": [
                                        [{"text": "📖 Узнать подробнее о движении"}],
                                        *[[{"text": pt}] for pt in PROBLEM_TYPES],
                                        [{"text": "🔙 Назад"}]
                                    ],
                                    "resize_keyboard": True
                                }
                                send_message(chat_id, "Выберите вариант:", keyboard)
                                user_states[chat_id] = "waiting_problem"
                                if f"{chat_id}_problem" in user_states:
                                    del user_states[f"{chat_id}_problem"]
                                    
                            elif current_state in ["waiting_details", "waiting_photo", "waiting_text_description"]:
                                send_message(chat_id, "📍 Выберите ваш район Москвы:")
                                
                                districts_kb = []
                                for i in range(0, len(MOSCOW_DISTRICTS), 2):
                                    row = [{"text": MOSCOW_DISTRICTS[i]}]
                                    if i + 1 < len(MOSCOW_DISTRICTS):
                                        row.append({"text": MOSCOW_DISTRICTS[i + 1]})
                                    districts_kb.append(row)
                                districts_kb.append([{"text": "🔙 Назад"}])
                                
                                keyboard = {"keyboard": districts_kb, "resize_keyboard": True}
                                send_message(chat_id, "Выберите район:", keyboard)
                                user_states[chat_id] = "waiting_district"
                                if f"{chat_id}_district" in user_states:
                                    del user_states[f"{chat_id}_district"]
                                    
                            else:
                                keyboard = {
                                    "keyboard": [[{"text": "🚀 Старт"}]],
                                    "resize_keyboard": True
                                }
                                send_message(chat_id, 
                                            "👋 Привет! Нажмите кнопку чтобы начать:",
                                            keyboard)
                                user_states[chat_id] = None
                        
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
                                districts_kb.append([{"text": "🔙 Назад"}])

                                keyboard = {"keyboard": districts_kb, "resize_keyboard": True}
                                send_message(chat_id, "📍 Выберите ваш район Москвы:", keyboard)
                            else:
                                send_message(chat_id, "Пожалуйста, выберите вариант из списка")
                        
                        elif user_states.get(chat_id) == "waiting_district":
                            if text in MOSCOW_DISTRICTS:
                                district = text
                                problem_type = user_states.get(f"{chat_id}_problem")
                                
                                user_states[chat_id] = "waiting_details"
                                
                                keyboard = {
                                    "keyboard": [
                                        [{"text": "📝 Только описание"}],
                                        [{"text": "📷 Добавить фото"}],
                                        [{"text": "🔙 Назад"}]
                                    ],
                                    "resize_keyboard": True
                                }
                                
                                send_message(chat_id, 
                                            "📝 Опишите проблему подробнее или прикрепите фото:",
                                            keyboard)
                                user_states[f"{chat_id}_district"] = district
                            else:
                                send_message(chat_id, "Пожалуйста, выберите район из списка")
                        
                        elif user_states.get(chat_id) == "waiting_details":
                            if text == "📝 Только описание":
                                user_states[chat_id] = "waiting_text_description"
                                send_message(chat_id, 
                                            "📝 Опишите проблему подробнее:",
                                            {"remove_keyboard": True})
                                
                            elif text == "📷 Добавить фото":
                                user_states[chat_id] = "waiting_photo"
                                send_message(chat_id, 
                                            "📷 Прикрепите фото или скриншот проблемы:",
                                            {"remove_keyboard": True})
                                
                            else:
                                send_message(chat_id, "Пожалуйста, выберите вариант из списка")
                        
                        elif user_states.get(chat_id) == "waiting_text_description":
                            details = text
                            problem_type = user_states.get(f"{chat_id}_problem")
                            district = user_states.get(f"{chat_id}_district")
                            
                            request_id = save_request_with_photo(chat_id, first_name, username, problem_type, district, details, None)
                            
                            # Логирование
                            with open('logs/requests_log.txt', 'a', encoding='utf-8') as f:
                                log_line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Заявка #{request_id} | "
                                if username:
                                    log_line += f"Username: @{username} | "
                                log_line += f"Имя: {first_name} | Проблема: {problem_type} | Район: {district} | Детали: {details}\n"
                                f.write(log_line)
                            
                            send_message(chat_id, 
                                        f"✅ Заявка #{request_id} принята!\n\n"
                                        f"⏳ Ожидайте связи волонтера.")
                            
                            keyboard = {
                                "keyboard": [[{"text": "🚀 Создать новую заявку"}]],
                                "resize_keyboard": True
                            }
                            send_message(chat_id, "Хотите создать еще одну заявку?", keyboard)
                            user_states[chat_id] = None
                            for key in [f"{chat_id}_problem", f"{chat_id}_district"]:
                                if key in user_states:
                                    del user_states[key]
                        
                        elif text == "🚀 Создать новую заявку":
                            send_message(chat_id, 
                                        "👋 Создаем новую заявку.\n\n"
                                        "Выберите тип проблемы:")
                            
                            keyboard = {
                                "keyboard": [
                                    [{"text": "📖 Узнать подробнее о движении"}],
                                    *[[{"text": pt}] for pt in PROBLEM_TYPES],
                                    [{"text": "🔙 Назад"}]
                                ],
                                "resize_keyboard": True
                            }
                            send_message(chat_id, "Выберите вариант:", keyboard)
                            user_states[chat_id] = "waiting_problem"
                        
                        else:
                            if text.startswith("/"):
                                keyboard = {
                                    "keyboard": [[{"text": "🚀 Старт"}]],
                                    "resize_keyboard": True
                                }
                                send_message(chat_id, 
                                            "👋 Привет! Нажмите кнопку чтобы начать:",
                                            keyboard)
                    
                    # Обработка фото
                    elif "photo" in update["message"]:
                        current_state = user_states.get(chat_id)
                        
                        if current_state == "waiting_photo":
                            photos = update["message"]["photo"]
                            photo = photos[-1]  # Берем фото наибольшего качества
                            file_id = photo["file_id"]
                            
                            problem_type = user_states.get(f"{chat_id}_problem")
                            district = user_states.get(f"{chat_id}_district")
                            
                            # Сначала сохраняем заявку чтобы получить ID
                            details = "Приложено фото проблемы"
                            request_id = save_request_with_photo(chat_id, first_name, username, problem_type, district, details, "temp")
                            
                            # Теперь сохраняем фото с правильным именем
                            photo_filename = f"{request_id}.png"
                            photo_path = f"photos/{photo_filename}"
                            
                            print(f"🖼️ Сохраняем фото для заявки #{request_id}")
                            
                            if download_file(file_id, photo_path):
                                # Обновляем запись с правильным именем файла
                                conn = sqlite3.connect('bot.db')
                                cur = conn.cursor()
                                cur.execute('''
                                    UPDATE requests SET photo_filename = ? WHERE id = ?
                                ''', (photo_filename, request_id))
                                conn.commit()
                                conn.close()
                                
                                # Логирование
                                with open('logs/requests_log.txt', 'a', encoding='utf-8') as f:
                                    log_line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Заявка #{request_id} | "
                                    if username:
                                        log_line += f"Username: @{username} | "
                                    log_line += f"Имя: {first_name} | Проблема: {problem_type} | Район: {district} | Фото: {photo_filename}\n"
                                    f.write(log_line)
                                
                                # Уведомление админам
                                for admin_id in ADMIN_IDS:
                                    message = (f"🚨 НОВАЯ ЗАЯВКА #{request_id}\n"
                                              f"👤 Имя: {first_name}\n")
                                    
                                    if username:
                                        message += f"👤 Username: @{username}\n"
                                        
                                    message += (f"🔧 Проблема: {problem_type}\n"
                                               f"📍 Район: {district}\n"
                                               f"📷 Приложено фото: {photo_filename}")
                                    
                                    send_message(admin_id, message)
                                
                                send_message(chat_id, 
                                            f"✅ Заявка #{request_id} принята!\n\n"
                                            f"📷 Фото сохранено\n\n"
                                            f"⏳ Ожидайте связи волонтера.")
                                
                                keyboard = {
                                    "keyboard": [[{"text": "🚀 Создать новую заявку"}]],
                                    "resize_keyboard": True
                                }
                                send_message(chat_id, "Хотите создать еще одну заявку?", keyboard)
                                user_states[chat_id] = None
                                for key in [f"{chat_id}_problem", f"{chat_id}_district"]:
                                    if key in user_states:
                                        del user_states[key]
                            else:
                                send_message(chat_id, "❌ Ошибка при загрузке фото. Попробуйте еще раз.")
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()