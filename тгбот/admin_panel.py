import http.client
import json
import time
import sqlite3
import urllib.parse
from config import BOT_TOKEN, ADMINS, ADMIN_IDS

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

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_statistics():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    # Общая статистика
    cur.execute("SELECT COUNT(*) FROM requests")
    total_requests = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM requests WHERE status = 'new'")
    new_requests = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM requests WHERE status = 'in_progress'")
    in_progress = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM requests WHERE status = 'completed'")
    completed = cur.fetchone()[0]
    
    # Статистика по волонтерам
    cur.execute("SELECT COUNT(*) FROM volunteers")
    total_volunteers = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM volunteers WHERE is_active = 1")
    active_volunteers = cur.fetchone()[0]
    
    # Топ волонтеров
    cur.execute('''
        SELECT user_name, completed_requests, district 
        FROM volunteers 
        WHERE completed_requests > 0 
        ORDER BY completed_requests DESC 
        LIMIT 5
    ''')
    top_volunteers = cur.fetchall()
    
    conn.close()
    
    return {
        'total_requests': total_requests,
        'new_requests': new_requests,
        'in_progress': in_progress,
        'completed': completed,
        'total_volunteers': total_volunteers,
        'active_volunteers': active_volunteers,
        'top_volunteers': top_volunteers
    }

def get_all_requests():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT r.*, v.user_name as volunteer_name 
        FROM requests r 
        LEFT JOIN volunteers v ON r.volunteer_id = v.user_id
        ORDER BY r.created_at DESC
        LIMIT 10
    ''')
    requests = cur.fetchall()
    conn.close()
    return requests

def get_all_volunteers():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM volunteers 
        ORDER BY completed_requests DESC
    ''')
    volunteers = cur.fetchall()
    conn.close()
    return volunteers

def broadcast_message(admin_id, message_text):
    """Отправка сообщения всем пользователям"""
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    # Получаем всех уникальных пользователей
    cur.execute("SELECT DISTINCT user_id FROM requests")
    users = cur.fetchall()
    
    conn.close()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            send_message(user[0], f"📢 ОБЪЯВЛЕНИЕ:\n\n{message_text}")
            sent += 1
            time.sleep(0.1)  # Чтобы не превысить лимиты Telegram
        except:
            failed += 1
    
    return sent, failed

def main():
    last_update_id = None
    
    print("👑 Панель администратора запущена!")
    print("Доступные команды:")
    print("/stats - Статистика")
    print("/requests - Последние заявки") 
    print("/volunteers - Список волонтеров")
    print("/broadcast - Рассылка сообщений")
    print("/help - Помощь")
    
    while True:
        try:
            updates = get_updates(last_update_id)
            
            if updates.get("ok") and updates["result"]:
                for update in updates["result"]:
                    # Пропускаем уже обработанные сообщения
                    if last_update_id and update["update_id"] <= last_update_id:
                        continue
                    
                    chat_id = update["message"]["chat"]["id"]
                    user_name = update["message"]["chat"].get("first_name", "Админ")
                    text = update["message"].get("text", "")
                    update_id = update["update_id"]
                    
                    # Проверяем права админа
                    if not is_admin(chat_id):
                        send_message(chat_id, "❌ У вас нет доступа к панели администратора")
                        last_update_id = update_id
                        continue
                    
                    print(f"👑 Админ {user_name}({chat_id}): {text}")
                    
                    # Обработка команд админа
                    if text == "/start" or text == "/help":
                        admin_name = ADMINS.get(chat_id, "Администратор")
                        send_message(chat_id,
                                    f"👑 Добро пожаловать, {admin_name}!\n\n"
                                    f"Доступные команды:\n"
                                    f"/stats - 📊 Полная статистика\n"
                                    f"/requests - 📋 Последние заявки\n"
                                    f"/volunteers - 👥 Список волонтеров\n"
                                    f"/broadcast - 📢 Рассылка сообщений\n"
                                    f"/help - ❓ Помощь")
                    
                    elif text == "/stats":
                        stats = get_statistics()
                        
                        message = (
                            f"📊 ПОЛНАЯ СТАТИСТИКА:\n\n"
                            f"📨 ЗАЯВКИ:\n"
                            f"• Всего: {stats['total_requests']}\n"
                            f"• 🆕 Новых: {stats['new_requests']}\n"
                            f"• 🔄 В работе: {stats['in_progress']}\n"
                            f"• ✅ Завершено: {stats['completed']}\n\n"
                            f"👥 ВОЛОНТЕРЫ:\n"
                            f"• Всего: {stats['total_volunteers']}\n"
                            f"• ✅ Активных: {stats['active_volunteers']}\n\n"
                            f"🏆 ТОП ВОЛОНТЕРОВ:\n"
                        )
                        
                        if stats['top_volunteers']:
                            for i, (name, completed, district) in enumerate(stats['top_volunteers'], 1):
                                message += f"{i}. {name} ({district}): {completed} заявок\n"
                        else:
                            message += "Пока нет данных\n"
                        
                        send_message(chat_id, message)
                    
                    elif text == "/requests":
                        requests = get_all_requests()
                        
                        if not requests:
                            send_message(chat_id, "📭 Заявок пока нет")
                        else:
                            send_message(chat_id, f"📋 ПОСЛЕДНИЕ {len(requests)} ЗАЯВОК:")
                            for req in requests:
                                status_icons = {"new": "🆕", "in_progress": "🔄", "completed": "✅"}
                                status_icon = status_icons.get(req[6], "❓")
                                
                                req_text = (
                                    f"{status_icon} Заявка #{req[0]}\n"
                                    f"👤 {req[2]} (ID: {req[1]})\n"
                                    f"🔧 {req[3]}\n"
                                    f"📍 {req[4]}\n"
                                    f"📊 {req[6]}\n"
                                    f"📅 {req[10]}\n"
                                )
                                
                                if req[7]:  # volunteer_id
                                    req_text += f"👥 Волонтер: {req[12] or 'Неизвестно'}\n"
                                
                                send_message(chat_id, req_text)
                    
                    elif text == "/volunteers":
                        volunteers = get_all_volunteers()
                        
                        if not volunteers:
                            send_message(chat_id, "👥 Волонтеров пока нет")
                        else:
                            message = "👥 ВСЕ ВОЛОНТЕРЫ:\n\n"
                            for vol in volunteers:
                                status = "✅ Активен" if vol[4] else "❌ Неактивен"
                                message += (
                                    f"👤 {vol[2]}\n"
                                    f"📍 {vol[3]}\n"
                                    f"📊 {status}\n"
                                    f"✅ Заявок: {vol[5]}\n"
                                    f"📅 Регистрация: {vol[7]}\n"
                                    f"────────────────────\n"
                                )
                            
                            send_message(chat_id, message)
                    
                    elif text == "/broadcast":
                        send_message(chat_id, 
                                    "📢 Введите сообщение для рассылки всем пользователям:\n\n"
                                    "Пример: 'Уважаемые пользователи! Завтехнические работы с 14:00 до 16:00.'")
                        # Здесь можно добавить состояние ожидания сообщения для рассылки
                    
                    last_update_id = update_id
            
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Ошибка в панели администратора: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()