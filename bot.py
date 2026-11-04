import os
import telebot

# Токен будет браться из настроек BotHost
BOT_TOKEN = os.environ.get('BOT_TOKEN')

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "Привет! Я Дора. Я на связи!")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    text = message.text
    bot.reply_to(message, f"Я получила текст: '{text}'. (Я живая!)")

print("Дора запущена...")
bot.infinity_polling()
