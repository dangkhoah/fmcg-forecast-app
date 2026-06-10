import sqlite3

def list_users():
    conn = sqlite3.connect('backend/fmcg_forecast.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, email, full_name FROM users")
        users = cursor.fetchall()
        print("Users in database:")
        for user in users:
            print(user)
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    list_users()
