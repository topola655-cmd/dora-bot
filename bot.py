import logging
import datetime
import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ЧТЕНИЕ ФАЙЛА ---
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

# --- СТАРТ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['🎲 Рулетка']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я Дора. Нажми «🎲 Рулетка», чтобы выбрать дело.",
        reply_markup=reply_markup
    )

# --- ВЫБОР ФИЛЬТРА ---
async def start_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сбрасываем старые "Вето" при новом заходе
    context.user_data['veto_list'] = []
    context.user_data['base_time'] = None
    context.user_data['current_block'] = None

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
    
    # Если это первый запуск (нет времени), берем время из сообщения
    if context.user_data.get('base_time') is None:
        now = query.message.date + datetime.timedelta(hours=4)
        context.user_data['base_time'] = now.hour + now.minute
        context.user_data['current_block'] = choice
        context.user_data['veto_list'] = []
    else:
        # Если мы уже в процессе (нажали Вето), берем сохраненное время
        choice = context.user_data['current_block']
    
    base_seed = context.user_data['base_time']
    veto_list = context.user_data.get('veto_list', [])
    
    all_items = get_roulette_items()
    
    # Фильтруем по блоку
    if choice == "all":
        filtered = all_items
    else:
        filtered = [i for i in all_items if i["block"] == choice]
        
    # Убираем вычеркнутые
    filtered = [i for i in filtered if i["num"] not in veto_list]
    
    if not filtered:
        await query.edit_message_text("Задач больше нет. Нажми Рулетка.")
        return

    total = len(filtered)
    target_num = (base_seed - 1) % total + 1
    
    chosen = None
    for item in filtered:
        if item["num"] == target_num:
            chosen = item
            break
            
    if not chosen:
        chosen = filtered[target_num - 1]

    debug_text = (
        f"\n\n🕵️‍♀️ Отладка:\n"
        f"Время: {base_seed} (сумма)\n"
        f"Блок: {choice} (доступно {total})\n"
        f"Вычислено: {target_num}\n"
        f"Номер задачи: {chosen['num']}\n"
        f"Вето: {veto_list}"
    )

    # Создаем кнопку Вето
    keyboard = [[InlineKeyboardButton("🚫 Вето", callback_data=f"veto_{chosen['num']}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"🎲 №{chosen['num']} — {chosen['text']}{debug_text}",
        reply_markup=reply_markup
    )

# --- ОБРАБОТКА ВЕТО ---
async def veto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Достаем номер задачи из callback_data (например, veto_14)
    veto_num = int(query.data.replace("veto_", ""))
    
    # Добавляем в список вычеркнутых
    if 'veto_list' not in context.user_data:
        context.user_data['veto_list'] = []
    context.user_data['veto_list'].append(veto_num)
    
    # Вызываем spin заново, чтобы он выдал следующую
    await spin(update, context)

# --- ОБРАБОТЧИК ТЕКСТА ---
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
    app.add_handler(CallbackQueryHandler(veto, pattern="^veto_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
