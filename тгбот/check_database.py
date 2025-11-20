import sqlite3
from datetime import datetime

def check_database():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    # Проверяем таблицы
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    print("📊 ТАБЛИЦЫ В БАЗЕ:")
    for table in tables:
        print(f"  ✅ {table[0]}")
    
    # Проверяем заявки
    print("\n📋 ЗАЯВКИ:")
    cur.execute("SELECT * FROM requests ORDER BY created_at DESC")
    requests = cur.fetchall()
    
    if not requests:
        print("  📭 Заявок пока нет")
    else:
        for req in requests:
            print(f"  🆔 ID: {req[0]}")
            print(f"    👤 User: {req[2]} (ID: {req[1]})")
            print(f"    🔧 Проблема: {req[3]}")
            print(f"    📍 Район: {req[4]}")
            print(f"    📝 Детали: {req[5]}")
            print(f"    📊 Статус: {req[6]}")
            print(f"    📅 Дата: {req[10]}")
            print("    " + "-" * 30)
    
    # Проверяем волонтеров
    print("\n👥 ВОЛОНТЕРЫ:")
    cur.execute("SELECT * FROM volunteers")
    volunteers = cur.fetchall()
    
    if not volunteers:
        print("  📭 Волонтеров пока нет")
    else:
        for vol in volunteers:
            print(f"  👤 {vol[2]} (ID: {vol[1]})")
            print(f"    📍 Район: {vol[3]}")
            print(f"    ✅ Завершено заявок: {vol[5]}")
    
    # Статистика
    print("\n📈 СТАТИСТИКА:")
    cur.execute("SELECT COUNT(*) FROM requests")
    total_requests = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM requests WHERE status = 'new'")
    new_requests = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM volunteers")
    total_volunteers = cur.fetchone()[0]
    
    print(f"  📨 Всего заявок: {total_requests}")
    print(f"  🆕 Новых заявок: {new_requests}")
    print(f"  👥 Волонтеров: {total_volunteers}")
    
    conn.close()

if __name__ == "__main__":
    check_database()