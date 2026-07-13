import telebot
import os
import json
from pymongo import MongoClient

# для Flask
from flask import Flask
import threading

# создание Flask-приложения для health check
health_app = Flask(__name__)

@health_app.route('/')
def health():
    return "Бот работает", 200

def run_health_server():
    # Render передаёт порт через переменную PORT
    port = int(os.environ.get("PORT", 10000))
    health_app.run(host="0.0.0.0", port=port)

# запуск HTTP-сервер в отдельном потоке
threading.Thread(target=run_health_server, daemon=True).start()

BOT_TOKEN = "8345325076:AAFreetpBya03pUSwABL6VgrCFQ644mJt-s"
ADMIN_ID = 1743237033
MONGODB_URI = "mongodb+srv://makarychev887_db_user:VjHYgC26wBnnmMUW@cluster0.omk9t2w.mongodb.net/?appName=Cluster0"

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGODB_URI)
db = client["neimark_secure"]
users_collection = db["users"]

@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    bot.reply_to(message, "🔐 NEIMARK Secure бот. Команды: /users, /stats")

@bot.message_handler(commands=['users'])
def users(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    users = list(users_collection.find({}))
    if not users:
        bot.reply_to(message, "📭 Нет пользователей.")
        return
    msg = "📋 Список пользователей:\n"
    for u in users:
        msg += f"👤 {u['username']}\n"
    bot.reply_to(message, msg)

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    count = users_collection.count_documents({})
    bot.reply_to(message, f"👥 Всего пользователей: {count}")

print("Бот запущен")
bot.polling(none_stop=True)