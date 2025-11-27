import sqlite3

def update_database():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    try:
        # Пробуем добавить колонку если её нет
        cur.execute("ALTER TABLE requests ADD COLUMN photo_filename TEXT")
        print("✅ Колонка photo_filename добавлена в таблицу requests")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("✅ Колонка photo_filename уже существует")
        else:
            print(f"❌ Ошибка: {e}")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_database()