import os
import telebot
from telebot import types

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_night = types.KeyboardButton('🌙 Спокойной ночи')
    markup.add(btn_night)
    bot.reply_to(message, "Привет! Я Дора. Я на связи!", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    text = message.text.lower()
    if "спокойной ночи" in text or "споки" in text:
        bot.reply_to(message, "Спокойной ночи, Оля! 🌙 Отдыхай, завтра будет новый день. Не забудь умыться и подвести итоги 😉")
    else:
        bot.reply_to(message, f"Я получила текст: '{message.text}'. (Я живая!)")

print("Дора запущена...")
bot.infinity_polling()
