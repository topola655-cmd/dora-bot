import logging
import datetime
import os
import base64
import requests
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ЧТЕНИЕ ФАЙЛА РУЛЕТКИ ---
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

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ РУЛЕТКИ ---
async def do_spin(query, context):
    choice = context.user_data['current_block']
    base_seed = context.user_data['base_time']
    veto_list = context.user_data.get('veto_list', [])
    
    all_items = get_roulette_items()
    
    if choice == "all":
        filtered = all_items
    else:
        filtered = [i for i in all_items if i["block"] == choice]
        
    filtered = [i for i in filtered if i["num"] not in veto_list]
    
    if not filtered:
        await query.message.reply_text("Задач больше нет. Нажми Рулетка.")
        return

    total = len(filtered)
    
    if context.user_data.get('last_index') is None:
        start_index = 0
    else:
        start_index = context.user_data['last_index']
        if start_index >= total:
            start_index = 0

    final_index = (start_index + (base_seed - 1)) % total
    chosen = filtered[final_index]
    context.user_data['last_index'] = final_index

    debug_text = (
        f"\n\n🕵️‍♀️ Отладка:\n"
        f"Время: {base_seed}\n"
        f"Блок: {choice} (доступно {total})\n"
        f"Номер задачи: {chosen['num']}\n"
        f"Пропущено: {veto_list}"
    )

    keyboard = [[
        InlineKeyboardButton("✅ Беру", callback_data=f"take_{chosen['num']}"),
        InlineKeyboardButton("⏭ Пропустить", callback_data=f"skip_{chosen['num']}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        f"🎲 №{chosen['num']} — {chosen['text']}{debug_text}",
        reply_markup=reply_markup
    )

# --- СТАРТ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ['🎲 Рулетка', '📥 Инбокс'],
        ['📋 Показать Инбокс']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я Дора. Выбирай, что будем делать.",
        reply_markup=reply_markup
    )

# --- РУЛЕТКА: ВЫБОР ФИЛЬТРА ---
async def start_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = 'roulette'
    context.user_data['veto_list'] = []
    context.user_data['base_time'] = None
    context.user_data['current_block'] = None
    context.user_data['last_index'] = None

    keyboard = [
        [InlineKeyboardButton("Весь банк", callback_data="spin_all")],
        [InlineKeyboardButton("На дела", callback_data="spin_дела"), InlineKeyboardButton("На отдых", callback_data="spin_отдых")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что крутим?", reply_markup=reply_markup)

# --- РУЛЕТКА: ПЕРВЫЙ ЗАПУСК ---
async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data.replace("spin_", "")
    
    if context.user_data.get('base_time') is None:
        now = query.message.date + datetime.timedelta(hours=4)
        context.user_data['base_time'] = now.hour + now.minute
        context.user_data['current_block'] = choice
        context.user_data['veto_list'] = []
        context.user_data['last_index'] = None
    
    await do_spin(query, context)

# --- РУЛЕТКА: ПРОПУСТИТЬ ---
async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    skip_num = int(query.data.replace("skip_", ""))
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    
    if 'veto_list' not in context.user_data:
        context.user_data['veto_list'] = []
    context.user_data['veto_list'].append(skip_num)
    
    await do_spin(query, context)

# --- РУЛЕТКА: БЕРУ ---
async def take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
        
    await query.message.reply_text("Отлично, пошла делать! 💪")

# --- ИНБОКС: НАЧАЛО ---
async def start_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = 'inbox'
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_inbox")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Готова записать задачу в Инбокс.",
        reply_markup=reply_markup
    )

# --- ИНБОКС: ОТМЕНА ---
async def cancel_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['mode'] = None
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
        
    await query.message.reply_text("Хорошо, отменила.")

# --- ИНБОКС: ПОКАЗАТЬ ---
async def show_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists('inbox.txt'):
        await update.message.reply_text("Инбокс пока пуст.")
        return
        
    try:
        with open('inbox.txt', 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            
        if not lines:
            await update.message.reply_text("Инбокс пока пуст.")
            return
            
        text = "📋 Твой Инбокс:\n\n"
        for i, line in enumerate(lines, 1):
            text += f"{i}. {line}\n"
            
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при чтении Инбокса: {e}")

# --- ФУНКЦИЯ СОХРАНЕНИЯ В GITHUB ---
async def save_to_github(text):
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        return False, "Токен не найден"
        
    repo = "topola655-cmd/dora-bot"
    path = "inbox.txt"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        content_data = response.json()
        sha = content_data['sha']
        current_content = base64.b64decode(content_data['content']).decode('utf-8')
    elif response.status_code == 404:
        sha = None
        current_content = ""
    else:
        return False, f"Ошибка API: {response.status_code}"
        
    new_content = current_content + text + "\n"
    encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    
    data = {
        "message": "Добавлена задача в Инбокс",
        "content": encoded_content
    }
    if sha:
        data["sha"] = sha
        
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        # После сохранения в GitHub, обновляем локальный файл
        try:
            with open('inbox.txt', 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception:
            pass
        return True, "Успешно"
    else:
        return False, f"Ошибка сохранения: {response.text}"

# --- ОБРАБОТЧИК ТЕКСТА ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if text in ['🎲 рулетка', 'рулетка', 'крути рулетку', 'дора, крути рулетку']:
        await start_roulette(update, context)
    elif text == '📥 инбокс':
        await start_inbox(update, context)
    elif text in ['📋 показать инбокс', 'показать инбокс']:
        await show_inbox(update, context)
    else:
        if context.user_data.get('mode') == 'inbox':
            success, message = await save_to_github(update.message.text)
            if success:
                await update.message.reply_text("Записала в Инбокс ✅")
            else:
                await update.message.reply_text(f"Ошибка: {message}")
            context.user_data['mode'] = None
        else:
            await update.message.reply_text(f"Я получила текст: '{update.message.text}'.")

def main():
    TOKEN = os.environ.get('BOT_TOKEN')
    if not TOKEN:
        print("Ошибка: BOT_TOKEN не найден в переменных окружения!")
        return
        
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(spin, pattern="^spin_"))
    app.add_handler(CallbackQueryHandler(skip, pattern="^skip_"))
    app.add_handler(CallbackQueryHandler(take, pattern="^take_"))
    app.add_handler(CallbackQueryHandler(cancel_inbox, pattern="^cancel_inbox"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
