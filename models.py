import os
import sqlite3
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp
import requests
from pymongo import MongoClient, errors

# ---------- НАСТРОЙКИ ----------
# MongoDB 
MONGO_URI = "mongodb+srv://makarychev887_db_user:VjHYgC26wBnnmMUW@cluster0.omk9t2w.mongodb.net/?appName=Cluster0"
DB_NAME = "neimark_secure"

# Telegram 
BOT_TOKEN = "8345325076:AAFreetpBya03pUSwABL6VgrCFQ644mJt-s"
ADMIN_ID = 1743237033

# ---------- ВЫБОР БД ----------
USE_MONGO = False
mongo_client = None
users_collection = None

try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command('ping')  # проверка соединения
    db = mongo_client[DB_NAME]
    users_collection = db["users"]
    users_collection.create_index("username", unique=True)
    USE_MONGO = True
    print("✅ Подключено к MongoDB Atlas")
except Exception as e:
    print(f"⚠️ Ошибка подключения к MongoDB: {e}")
    print("ℹ️ Будет использована локальная SQLite БД (для демонстрации)")
    # подключение SQLite как запасной вариант
    DB_NAME_SQLITE = "users.db"
    conn = sqlite3.connect(DB_NAME_SQLITE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        totp_secret TEXT NOT NULL,
        created_at TEXT NOT NULL,
        profile_data TEXT
    )''')
    conn.commit()
    conn.close()

# ---------- ФУНКЦИИ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ----------
def get_user(username):
    if USE_MONGO:
        doc = users_collection.find_one({"username": username})
        if doc:
            return {
                "id": str(doc["_id"]),
                "username": doc["username"],
                "password_hash": doc["password_hash"],
                "totp_secret": doc["totp_secret"],
                "created_at": doc["created_at"],
                "profile_data": doc.get("profile_data")
            }
        return None
    else:
        # SQLite
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT id, username, password_hash, totp_secret, created_at, profile_data FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "totp_secret": row[3],
                "created_at": row[4],
                "profile_data": row[5]
            }
        return None

def create_user(username, password):
    if get_user(username):
        return None, "Пользователь уже существует"
    password_hash = generate_password_hash(password)
    totp_secret = pyotp.random_base32()
    created_at = datetime.now().isoformat()
    if USE_MONGO:
        user_doc = {
            "username": username,
            "password_hash": password_hash,
            "totp_secret": totp_secret,
            "created_at": created_at,
            "profile_data": None
        }
        try:
            users_collection.insert_one(user_doc)
            # отправка уведомления админу
            send_telegram_message(ADMIN_ID, f"🆕 *Новый пользователь*\n👤 {username}\n📅 {created_at[:10]}")
            return {"username": username, "totp_secret": totp_secret}, None
        except errors.DuplicateKeyError:
            return None, "Пользователь уже существует"
        except Exception as e:
            return None, f"Ошибка БД: {e}"
    else:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password_hash, totp_secret, created_at, profile_data) VALUES (?,?,?,?,?)",
                      (username, password_hash, totp_secret, created_at, None))
            conn.commit()
            conn.close()
            return {"username": username, "totp_secret": totp_secret}, None
        except sqlite3.IntegrityError:
            conn.close()
            return None, "Пользователь уже существует"

def update_profile(username, profile_data_json):
    if USE_MONGO:
        users_collection.update_one({"username": username}, {"$set": {"profile_data": profile_data_json}})
    else:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("UPDATE users SET profile_data = ? WHERE username = ?", (profile_data_json, username))
        conn.commit()
        conn.close()

def verify_password(username, password):
    user = get_user(username)
    if not user:
        return False
    return check_password_hash(user["password_hash"], password)

def verify_totp(username, code):
    user = get_user(username)
    if not user:
        return False
    totp = pyotp.TOTP(user["totp_secret"])
    return totp.verify(code, valid_window=2)

def get_totp_uri(username):
    user = get_user(username)
    if not user:
        return None
    totp = pyotp.TOTP(user["totp_secret"])
    return totp.provisioning_uri(name=username, issuer_name="NEIMARK Secure")

def log_security_event(event_type, username, details=""):
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] {event_type} | user: {username} | {details}\n"
    with open("security.log", "a", encoding="utf-8") as f:
        f.write(log_entry)

def is_password_strong(password):
    if len(password) < 8:
        return False, "Пароль должен содержать минимум 8 символов"
    if not any(c.isupper() for c in password):
        return False, "Пароль должен содержать хотя бы одну заглавную букву"
    if not any(c.islower() for c in password):
        return False, "Пароль должен содержать хотя бы одну строчную букву"
    if not any(c.isdigit() for c in password):
        return False, "Пароль должен содержать хотя бы одну цифру"
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Пароль должен содержать хотя бы один специальный символ"
    return True, "Пароль надёжный"

def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass