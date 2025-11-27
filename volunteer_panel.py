import http.client
import json
import time
import sqlite3
import urllib.parse
from config import BOT_TOKEN, ADMIN_IDS, MOSCOW_DISTRICTS

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
    return telegram_api("sendMessage", params)

def get_updates(offset=None):
    params = {"timeout": 60}
    if offset:
        params["offset"] = offset
    return telegram_api("getUpdates", params)

def get_new_requests(district=None):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    if district and district != "Любой":
        cur.execute('''
            SELECT r.*, u.user_name 
            FROM requests r
            LEFT JOIN (SELECT user_id, user_name FROM requests GROUP BY user_id) u ON r.user_id = u.user_id
            WHERE r.status = 'new' AND r.district = ?
            ORDER BY r.created_at
        ''', (district,))
    else:
        cur.execute('''
            SELECT r.*, u.user_name 
            FROM requests r
            LEFT JOIN (SELECT user_id, user_name FROM requests GROUP BY user_id) u ON r.user_id = u.user_id
            WHERE r.status = 'new'
            ORDER BY r.created_at
        ''')
    
    requests = cur.fetchall()
    conn.close()
    return requests

def get_my_requests(volunteer_id):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM requests 
        WHERE volunteer_id = ? AND status = 'in_progress'
        ORDER BY created_at
    ''', (volunteer_id,))
    requests = cur.fetchall()
    conn.close()
    return requests

def take_request(request_id, volunteer_id, volunteer_name):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    # Берем заявку в работу
    cur.execute('''
        UPDATE requests 
        SET status = 'in_progress', volunteer_id = ?
        WHERE id = ? AND status = 'new'
    ''', (volunteer_id, request_id))
    
    if cur.rowcount > 0:
        # Получаем данные заявки
        cur.execute('SELECT user_id, user_name FROM requests WHERE id = ?', (request_id,))
        request_data = cur.fetchone()
        
        conn.commit()
        conn.close()
        
        if request_data:
            user_id, user_name = request_data
            # Уведомляем пользователя
            send_message(user_id, 
                        f"🎉 Вашу заявку #{request_id} принял волонтер {volunteer_name}!\n\n"
                        f"Свяжитесь с волонтером для решения проблемы.")
        
        return True
    else:
        conn.close()
        return False

def complete_request(request_id, volunteer_id, rating, feedback):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    # Завершаем заявку
    cur.execute('''
        UPDATE requests 
        SET status = 'completed', rating = ?, feedback = ?, completed_at = CURRENT_TIMESTAMP
        WHERE id = ? AND volunteer_id = ?
    ''', (rating, feedback, request_id, volunteer_id))
    
    if cur.rowcount > 0:
        # Обновляем статистику волонтера
        cur.execute('''
            UPDATE volunteers 
            SET completed_requests = completed_requests + 1
            WHERE user_id = ?
        ''', (volunteer_id,))
        
        conn.commit()
        conn.close()
        
        # Уведомляем пользователя
        cur.execute('SELECT user_id FROM requests WHERE id = ?', (request_id,))
        user_id = cur.fetchone()[0]
        
        send_message(user_id,
                    f"✅ Ваша заявка #{request_id} завершена!\n\n"
                    f"Спасибо за использование нашего сервиса!")
        
        return True
    else:
        conn.close()
        return False

def register_volunteer(user_id, user_name, district):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    cur.execute('''
        INSERT OR REPLACE INTO volunteers (user_id, user_name, district, is_active) 
        VALUES (?, ?, ?, 1)
    ''', (user_id, user_name, district))
    
    conn.commit()
    conn.close()

def main():
    last_update_id = None
    volunteer_states = {}
    
    print("👥 Панель волонтера запущена!")
    print("Отправьте /start в ЛС боту для регистрации волонтером")
    
    while True:
        try:
            updates = get_updates(last_update_id)
            
            if updates.get("ok") and updates["result"]:
                for update in updates["result"]:
                    chat_id = update["message"]["chat"]["id"]
                    user_name = update["message"]["chat"].get("first_name", "Волонтер")
                    text = update["message"].get("text", "")
                    update_id = update["update_id"]
                    
                    # Обработка команд волонтера
                    if text == "/start":
                        register_volunteer(chat_id, user_name, "Любой")
                        
                        send_message(chat_id,
                                    f"👋 Добро пожаловать, {user_name}!\n\n"
                                    f"Вы зарегистрированы как волонтер.\n"
                                    f"Доступные команды:\n"
                                    f"/new - Новые заявки\n"
                                    f"/my - Мои заявки\n"
                                    f"/stats - Статистика\n"
                                    f"/district - Сменить район")
                        
                        volunteer_states[chat_id] = "menu"
                    
                    elif text == "/new":
                        requests = get_new_requests()
                        
                        if not requests:
                            send_message(chat_id, "📭 Новых заявок пока нет")
                        else:
                            for req in requests[:5]:  # Показываем первые 5 заявок
                                req_text = (f"🆔 Заявка #{req[0]}\n"
                                          f"👤 Пользователь: {req[2]}\n"
                                          f"🔧 Проблема: {req[3]}\n"
                                          f"📍 Район: {req[4]}\n"
                                          f"📝 Описание: {req[5]}\n"
                                          f"📅 Создана: {req[10]}\n\n"
                                          f"Для принятия заявки отправьте:\n"
                                          f"/take_{req[0]}")
                                send_message(chat_id, req_text)
                    
                    elif text.startswith("/take_"):
                        try:
                            request_id = int(text.split("_")[1])
                            if take_request(request_id, chat_id, user_name):
                                send_message(chat_id, f"✅ Вы приняли заявку #{request_id}")
                            else:
                                send_message(chat_id, "❌ Заявка уже занята или не существует")
                        except:
                            send_message(chat_id, "❌ Неверный формат команды")
                    
                    elif text == "/my":
                        requests = get_my_requests(chat_id)
                        
                        if not requests:
                            send_message(chat_id, "📭 У вас нет активных заявок")
                        else:
                            for req in requests:
                                req_text = (f"🆔 Заявка #{req[0]}\n"
                                          f"👤 Пользователь: {req[2]}\n"
                                          f"🔧 Проблема: {req[3]}\n"
                                          f"📍 Район: {req[4]}\n"
                                          f"📝 Описание: {req[5]}\n\n"
                                          f"Для завершения отправьте:\n"
                                          f"/complete_{req[0]}")
                                send_message(chat_id, req_text)
                    
                    elif text.startswith("/complete_"):
                        try:
                            request_id = int(text.split("_")[1])
                            volunteer_states[chat_id] = f"waiting_rating_{request_id}"
                            send_message(chat_id,
                                        "📊 Оцените выполнение заявки (1-5):\n"
                                        "1 - Очень плохо\n"
                                        "2 - Плохо\n"  
                                        "3 - Удовлетворительно\n"
                                        "4 - Хорошо\n"
                                        "5 - Отлично")
                        except:
                            send_message(chat_id, "❌ Неверный формат команды")
                    
                    elif text in ["1", "2", "3", "4", "5"] and volunteer_states.get(chat_id, "").startswith("waiting_rating_"):
                        try:
                            request_id = int(volunteer_states[chat_id].split("_")[2])
                            rating = int(text)
                            volunteer_states[chat_id] = f"waiting_feedback_{request_id}_{rating}"
                            send_message(chat_id, "💬 Оставьте комментарий к заявке:")
                        except:
                            send_message(chat_id, "❌ Ошибка обработки оценки")
                    
                    elif volunteer_states.get(chat_id, "").startswith("waiting_feedback_"):
                        try:
                            parts = volunteer_states[chat_id].split("_")
                            request_id = int(parts[2])
                            rating = int(parts[3])
                            feedback = text
                            
                            if complete_request(request_id, chat_id, rating, feedback):
                                send_message(chat_id, f"✅ Заявка #{request_id} завершена!")
                                volunteer_states[chat_id] = "menu"
                            else:
                                send_message(chat_id, "❌ Ошибка завершения заявки")
                        except:
                            send_message(chat_id, "❌ Ошибка обработки отзыва")
                    
                    elif text == "/stats":
                        conn = sqlite3.connect('bot.db')
                        cur = conn.cursor()
                        cur.execute('''
                            SELECT completed_requests FROM volunteers WHERE user_id = ?
                        ''', (chat_id,))
                        stats = cur.fetchone()
                        conn.close()
                        
                        if stats:
                            send_message(chat_id, f"📊 Ваша статистика:\nЗавершенных заявок: {stats[0]}")
                        else:
                            send_message(chat_id, "❌ Статистика не найдена")
                    
                    elif text == "/district":
                        districts_kb = []
                        for i in range(0, len(MOSCOW_DISTRICTS), 2):
                            row = [{"text": MOSCOW_DISTRICTS[i]}]
                            if i + 1 < len(MOSCOW_DISTRICTS):
                                row.append({"text": MOSCOW_DISTRICTS[i + 1]})
                            districts_kb.append(row)
                        districts_kb.append([{"text": "Любой"}])
                        
                        keyboard = {"keyboard": districts_kb, "resize_keyboard": True}
                        send_message(chat_id, "📍 Выберите ваш район:", keyboard)
                        volunteer_states[chat_id] = "waiting_district"
                    
                    elif volunteer_states.get(chat_id) == "waiting_district":
                        if text in MOSCOW_DISTRICTS + ["Любой"]:
                            register_volunteer(chat_id, user_name, text)
                            send_message(chat_id, f"✅ Район изменен на: {text}", {"remove_keyboard": True})
                            volunteer_states[chat_id] = "menu"
                        else:
                            send_message(chat_id, "Пожалуйста, выберите район из списка")
                    
                    last_update_id = update_id + 1
            
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Ошибка в панели волонтера: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()