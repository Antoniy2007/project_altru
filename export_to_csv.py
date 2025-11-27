import sqlite3
import csv
from datetime import datetime

def export_to_csv():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    # Экспорт заявок
    cur.execute("SELECT * FROM requests")
    requests = cur.fetchall()
    
    with open('заявки.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'User ID', 'User Name', 'Problem Type', 'District', 'Details', 'Status', 'Volunteer ID', 'Rating', 'Feedback', 'Created At', 'Completed At'])
        writer.writerows(requests)
    
    # Экспорт волонтеров
    cur.execute("SELECT * FROM volunteers")
    volunteers = cur.fetchall()
    
    with open('волонтеры.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'User ID', 'User Name', 'District', 'Is Active', 'Completed Requests', 'Rating Avg', 'Created At'])
        writer.writerows(volunteers)
    
    conn.close()
    print("✅ Данные экспортированы в CSV файлы:")
    print("   - заявки.csv")
    print("   - волонтеры.csv")

if __name__ == "__main__":
    export_to_csv()