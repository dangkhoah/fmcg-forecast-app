import sqlite3
conn = sqlite3.connect('backend/fmcg_forecast.db')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE name='users'")
print(cursor.fetchone()[0])
conn.close()
