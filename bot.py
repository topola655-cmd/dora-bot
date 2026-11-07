import logging
import datetime
import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройка логов
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ФУНКЦИЯ ЧТЕНИЯ БАНКА РУЛЕТКИ ---
def get_roulette_items():
    items = []
    file_name = 'data.txt' if os.path.exists('data.txt') else 'данные.txt'
    
    if not os.path.exists(file_name):
        return items

    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        current_block = "all"
        for line in lines:
            clean_line = line.strip()
            
            # Жестко ловим блоки
            if "Дела" in clean_line:
                current_block = "дела"
            elif "Отдых" in clean_line:
                current_block = "отдых"
            
            # Жестко ловим только те строки, где есть цифра и точка
            if len(clean_line) > 2 and clean_line[0].isdigit() and clean_line[1] == '.':
                try:
                    num = int(clean_line[0])
                except:
                    num = 0
                
                task_text = clean_line[2:].strip()
                items.append({"num": num, "text": task_text, "block": current_block})
                
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
    return items

# --- СТАРТ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['🎲 Рулетка']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я Дора. Нажми «🎲 Рулетка», чтобы выбрать дело.",
        reply_markup=reply_markup
    )

# --- ЗАПУСК РУЛЕТКИ (Выбор фильтра) ---
async def start_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Весь банк", callback_data="spin_all")],
        [InlineKeyboardButton("На дела", callback_data="spin_дела"), InlineKeyboardButton("На отдых", callback_data="spin_отдых")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что крутим?", reply_markup=reply_markup)

# --- ЛОГИКА ВРАЩЕНИЯ ---
async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data.replace("spin_", "")
    
    # Берем время нажатия кнопки (часы + минуты)
    now = datetime.datetime.now()
    seed = now.hour + now.minute
    if seed == 0:
        seed = 1 
        
    all_items = get_roulette_items()
    
    # Фильтруем по блоку
    if choice == "all":
        filtered = all_items
    else:
        filtered = [i for i in all_items if i["block"] == choice]
        
    if not filtered:
        await query.edit_message_text("В этом блоке пока нет задач.")
        return

    # Честный рандом по кругу
    index = seed % len(filtered)
    chosen = filtered[index]
    
    await query.edit_message_text(
        f"🎲 №{chosen['num']} — {chosen['text']}"
    )

# --- ОБРАБОТЧИК ТЕКСТА ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if text in ['🎲 рулетка', 'рулетка', 'крути рулетку', 'дора, крути рулетку']:
        await start_roulette(update, context)
    else:
        await update.message.reply_text(f"Я получила текст: '{update.message.text}'.")

# --- ЗАПУСК БОТА ---
def main():
    # ВСТАВЬ СЮДА СВОЙ ТОКЕН
    TOKEN = "9264445469:AAEUpRdZ2acRyyDRvh4WAAgzgFqNg9p9ARI"
    
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(spin, pattern="^spin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
