import logging
import datetime
import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def get_roulette_items():
    items = []
    file_name = 'data.txt' if os.path.exists('data.txt') else 'данные.txt'
    
    if not os.path.exists(file_name):
        print("Файл не найден")
        return items

    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        current_block = "all"
        for line in lines:
            clean_line = line.strip()
            if not clean_line:
                continue
            
            if "Дела" in clean_line:
                current_block = "дела"
                continue
            elif "Отдых" in clean_line:
                current_block = "отдых"
                continue
            
            num_str = ""
            for char in clean_line:
                if char.isdigit():
                    num_str += char
                else:
                    break
            
            if num_str:
                task_text = clean_line[len(num_str):].strip()
                if task_text.startswith('.'):
                    task_text = task_text[1:].strip()
                
                items.append({
                    "num": int(num_str), 
                    "text": task_text, 
                    "block": current_block
                })
                
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
    return items

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['🎲 Рулетка']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я Дора. Нажми «🎲 Рулетка», чтобы выбрать дело.",
        reply_markup=reply_markup
    )

async def start_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Весь банк", callback_data="spin_all")],
        [InlineKeyboardButton("На дела", callback_data="spin_дела"), InlineKeyboardButton("На отдых", callback_data="spin_отдых")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что крутим?", reply_markup=reply_markup)

async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data.replace("spin_", "")
    
    now = query.message.date + datetime.timedelta(hours=4)
    seed = now.hour + now.minute
    if seed == 0:
        seed = 1 
        
    all_items = get_roulette_items()
    
    if choice == "all":
        filtered = all_items
    else:
        filtered = [i for i in all_items if i["block"] == choice]
        
    if not filtered:
        await query.edit_message_text("В этом блоке пока нет задач.")
        return

    total = len(filtered)
    target_num = (seed - 1) % total + 1
    
    chosen = None
    for item in filtered:
        if item["num"] == target_num:
            chosen = item
            break
            
    if not chosen:
        chosen = filtered[target_num - 1]

    debug_text = (
        f"\n\n🕵️‍♀️ Отладка:\n"
        f"Время: {now.hour}:{now.minute:02d} (сумма {seed})\n"
        f"Блок: {choice} (всего {total})\n"
        f"Вычислено: {target_num}\n"
        f"Номер задачи: {chosen['num']}"
    )

    await query.edit_message_text(
        f"🎲 №{chosen['num']} — {chosen['text']}{debug_text}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if text in ['🎲 рулетка', 'рулетка', 'крути рулетку', 'дора, крути рулетку']:
        await start_roulette(update, context)
    else:
        await update.message.reply_text(f"Я получила текст: '{update.message.text}'.")

def main():
    TOKEN = "9264445469:AAEUpRdZ2acRyyDRvh4WAAgzgFqNg9p9ARI"
    
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(spin, pattern="^spin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
