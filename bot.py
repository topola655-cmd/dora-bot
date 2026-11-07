import logging
import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройка логов
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ФУНКЦИЯ ЧТЕНИЯ БАНКА РУЛЕТКИ ---
def get_roulette_items():
    items = []
    try:
        # Открываем файл, который лежит в репозитории
        with open('data.txt', 'r', encoding='utf-8') as f:
            text = f.read()
            
        current_block = "all"
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            if "🧹 Дела" in line:
                current_block = "дела"
            elif "🎈 Отдых" in line:
                current_block = "отдых"
            elif line[0].isdigit():
                # Извлекаем номер и текст
                dot_index = line.find('.')
                if dot_index != -1:
                    num = int(line[:dot_index])
                    task_text = line[dot_index+1:].strip()
                    items.append({"num": num, "text": task_text, "block": current_block})
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
    return items

# --- СТАРТ БОТА ---
async def start_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ТЕСТОВЫЙ БЛОК: считаем пункты
    items = get_roulette_items()
    count = len(items)
    first = items[0]['text'] if items else "Пусто"
    last = items[-1]['text'] if items else "Пусто"
    
    await update.message.reply_text(
        f"🕵️‍♀️ Проверка файла:\n"
        f"Я нашел: {count} задач.\n"
        f"Первая: {first}\n"
        f"Последняя: {last}"
    )

# --- ЗАПУСК РУЛЕТКИ (Выбор фильтра) ---
async def start_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Инлайн-кнопки (появляются под сообщением)
    keyboard = [
        [InlineKeyboardButton("Весь банк", callback_data="spin_all")],
        [InlineKeyboardButton("На дела", callback_data="spin_дела"), InlineKeyboardButton("На отдых", callback_data="spin_отдых")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что крутим?", reply_markup=reply_markup)

# --- ЛОГИКА ВРАЩЕНИЯ ---
async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Убираем "часики" с кнопки
    
    choice = query.data.replace("spin_", "")
    
    # Берем время нажатия кнопки (часы + минуты)
    now = datetime.datetime.now()
    seed = now.hour + now.minute
    if seed == 0:
        seed = 1 # Защита от нуля
        
    all_items = get_roulette_items()
    
    # Фильтруем по блоку
    if choice == "all":
        filtered = all_items
    else:
        filtered = [i for i in all_items if i["block"] == choice]
        
    if not filtered:
        await query.edit_message_text("В этом блоке пока нет задач.")
        return

    # Честный рандом по кругу (используем остаток от деления)
    index = seed % len(filtered)
    chosen = filtered[index]
    
    await query.edit_message_text(
        f"🎲 №{chosen['num']} — {chosen['text']}",
        parse_mode=None
    )

# --- ОБРАБОТЧИК ТЕКСТА ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    # Если нажали кнопку внизу или написали "рулетка"
    if text in ['🎲 рулетка', 'рулетка', 'крути рулетку', 'дора, крути рулетку']:
        await start_roulette(update, context)
    else:
        # Пока просто эхо для других сообщений (потом заменим на Инбокс)
        await update.message.reply_text(f"Я получила текст: '{update.message.text}'. (Скоро научусь его разбирать!)")

# --- ЗАПУСК БОТА ---
def main():
    # ВСТАВЬ СЮДА СВОЙ ТОКЕН (который ты сохранила)
    TOKEN = "9264445469:AAEUpRdZ2acRyyDRvh4WAAgzgFqNg9p9ARI"
    
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(spin, pattern="^spin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
