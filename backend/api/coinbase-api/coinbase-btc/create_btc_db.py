import sqlite3

conn = sqlite3.connect('btc_ticks.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS btc_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        price REAL NOT NULL
    )
''')
conn.commit()
conn.close()

print("Database and table created.")