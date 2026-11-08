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
        ['🎲 Рулетка', '📥 Инбокс']
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

# --- ИНБОКС: ГЛАВНОЕ МЕНЮ ---
async def inbox_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = None
    keyboard = [
        [InlineKeyboardButton("✍️ Добавить задачу", callback_data="inbox_add")],
        [InlineKeyboardButton("📋 Показать список", callback_data="inbox_show"), InlineKeyboardButton("🌿 Разобрать", callback_data="inbox_sort")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что делаем с Инбоксом?", reply_markup=reply_markup)

# --- ИНБОКС: НАЧАЛО ДОБАВЛЕНИЯ ---
async def start_inbox_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['mode'] = 'inbox'
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_inbox")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
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
    query = update.callback_query
    await query.answer()
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    if not os.path.exists('inbox.txt'):
        await query.message.reply_text("Инбокс пока пуст.")
        return
        
    try:
        with open('inbox.txt', 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            
        if not lines:
            await query.message.reply_text("Инбокс пока пуст.")
            return
            
        text = "📋 Твой Инбокс:\n\n"
        for i, line in enumerate(lines, 1):
            text += f"{i}. {line}\n"
            
        keyboard = [[InlineKeyboardButton("🗑 Удалить задачу", callback_data="delete_task_prompt")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
            
        await query.message.reply_text(text, reply_markup=reply_markup)
    except Exception as e:
        await query.message.reply_text(f"Ошибка при чтении Инбокса: {e}")

# --- ИНБОКС: УДАЛЕНИЕ (ЗАПРОС НОМЕРА) ---
async def delete_task_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['mode'] = 'delete_inbox'
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
        
    await query.message.reply_text("Напиши номер задачи, которую нужно удалить.")

# --- ИНБОКС: РАЗБОР ---
async def start_sorting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    if not os.path.exists('inbox.txt'):
        await query.message.reply_text("Инбокс пуст, нечего разбирать.")
        return
        
    with open('inbox.txt', 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        
    if not lines:
        await query.message.reply_text("Инбокс пуст, нечего разбирать.")
        return
    
    # Берем первую задачу
    context.user_data['sorting_task'] = lines[0]
    context.user_data['mode'] = 'sorting'
    
    keyboard = [
        [InlineKeyboardButton("📅 Будущее", callback_data="sort_future")],
        [InlineKeyboardButton("🔁 Регулярные", callback_data="sort_regular"), InlineKeyboardButton("📦 Инкубатор", callback_data="sort_incubator")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        f"Разбираем задачу:\n«{lines[0]}»\n\nКуда её?",
        reply_markup=reply_markup
    )

# --- РАЗБОР: ВЫБРАНО БУДУЩЕЕ ---
async def sort_future(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_dest'] = 'future'
    context.user_data['mode'] = 'sort_date'
    await query.message.reply_text("Напиши дату (например, «7 ноября»).")

# --- РАЗБОР: ВЫБРАНЫ РЕГУЛЯРНЫЕ ---
async def sort_regular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_dest'] = 'regular'
    context.user_data['mode'] = 'sort_rule'
    await query.message.reply_text("Напиши правило (например, «каждую субботу»).")

# --- РАЗБОР: ВЫБРАН ИНКУБАТОР ---
async def sort_incubator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_dest'] = 'incubator'
    
    keyboard = [
        [InlineKeyboardButton("Шкаф", callback_data="inc_shkaf")],
        [InlineKeyboardButton("Балкон", callback_data="inc_balkon"), InlineKeyboardButton("Дача", callback_data="inc_dacha")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("В какой шкаф?", reply_markup=reply_markup)

# --- РАЗБОР: ВЫБРАН ШКАФ ИНКУБАТОРА ---
async def inc_shkaf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_extra'] = 'Шкаф'
    await save_sorted_task(query, context)

async def inc_balkon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_extra'] = 'Балкон'
    await save_sorted_task(query, context)

async def inc_dacha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_extra'] = 'Дача'
    await save_sorted_task(query, context)

# --- ФУНКЦИЯ СОХРАНЕНИЯ РАЗОБРАННОЙ ЗАДАЧИ ---
async def save_sorted_task(query, context):
    task_text = context.user_data.get('sorting_task')
    dest = context.user_data.get('sort_dest')
    extra = context.user_data.get('sort_extra', '')
    
    if not task_text:
        return
        
    # Формируем строку для tasks.txt
    if dest == 'future':
        line = f"📅 {task_text} ({extra})\n"
    elif dest == 'regular':
        line = f"🔁 {task_text} ({extra})\n"
    elif dest == 'incubator':
        line = f"📦 [{extra}] {task_text}\n"
        
    # Сохраняем в tasks.txt (через GitHub)
    success, msg = await append_to_github("tasks.txt", line)
    
    if success:
        # Удаляем первую задачу из inbox.txt (через GitHub)
        await delete_first_from_inbox()
        await query.message.reply_text(f"Задача отправлена в {dest}. ✅")
    else:
        await query.message.reply_text(f"Ошибка сохранения: {msg}")

# --- ФУНКЦИЯ ДОБАВЛЕНИЯ В ФАЙЛ НА GITHUB ---
async def append_to_github(path, text):
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        return False, "Токен не найден"
        
    repo = "topola655-cmd/dora-bot"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
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
        
    new_content = current_content + text
    encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    
    data = {"message": f"Обновление {path}", "content": encoded_content}
    if sha:
        data["sha"] = sha
        
    response = requests.put(url, headers=headers, json=data)
    return response.status_code in [200, 201], "OK"

# --- ФУНКЦИЯ УДАЛЕНИЯ ПЕРВОЙ ЗАДАЧИ ИЗ ИНБОКСА ---
async def delete_first_from_inbox():
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        return
        
    repo = "topola655-cmd/dora-bot"
    path = "inbox.txt"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return
        
    content_data = response.json()
    sha = content_data['sha']
    current_content = base64.b64decode(content_data['content']).decode('utf-8')
    
    lines = [line.strip() for line in current_content.split('\n') if line.strip()]
    if lines:
        del lines[0] # Удаляем первую задачу
        new_content = "\n".join(lines) + "\n" if lines else ""
        
        encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
        data = {"message": "Удалена разобранная задача", "content": encoded_content, "sha": sha}
        requests.put(url, headers=headers, json=data)
        
        # Обновляем локальный файл
        with open('inbox.txt', 'w', encoding='utf-8') as f:
            f.write(new_content)

# --- ОБРАБОТЧИК ТЕКСТА ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if text in ['🎲 рулетка', 'рулетка', 'крути рулетку', 'дора, крути рулетку']:
        await start_roulette(update, context)
    elif text == '📥 инбокс':
        await inbox_menu(update, context)
    else:
        mode = context.user_data.get('mode')
        
        if mode == 'inbox':
            success, message = await append_to_github("inbox.txt", update.message.text + "\n")
            if success:
                await update.message.reply_text("Записала в Инбокс ✅")
                context.user_data['mode'] = None
            else:
                await update.message.reply_text(f"Ошибка: {message}")
                
        elif mode == 'delete_inbox':
            try:
                task_num = int(update.message.text.strip())
                success, message = await delete_task_from_github(task_num)
                if success:
                    await update.message.reply_text("Задача удалена ✅")
                else:
                    await update.message.reply_text(f"Ошибка: {message}")
            except ValueError:
                await update.message.reply_text("Напиши число.")
            context.user_data['mode'] = None
            
        elif mode == 'sort_date':
            context.user_data['sort_extra'] = update.message.text
            # Сохраняем задачу (вызовем функцию сохранения)
            class FakeQuery: # Заглушка, чтобы передать в функцию
                async def answer(self): pass
                class Message:
                    async def reply_text(self, text, **kwargs): await update.message.reply_text(text, **kwargs)
                message = Message()
            await save_sorted_task(FakeQuery(), context)
            context.user_data['mode'] = None
            
        elif mode == 'sort_rule':
            context.user_data['sort_extra'] = update.message.text
            class FakeQuery:
                async def answer(self): pass
                class Message:
                    async def reply_text(self, text, **kwargs): await update.message.reply_text(text, **kwargs)
                message = Message()
            await save_sorted_task(FakeQuery(), context)
            context.user_data['mode'] = None
            
        else:
            await update.message.reply_text(f"Я получила текст: '{update.message.text}'.")

# --- УДАЛЕНИЕ КОНКРЕТНОЙ ЗАДАЧИ ИЗ ИНБОКСА ---
async def delete_task_from_github(task_number):
    token = os.environ.get('GITHUB_TOKEN')
    if not token: return False, "Нет токена"
    repo = "topola655-cmd/dora-bot"
    url = f"https://api.github.com/repos/{repo}/contents/inbox.txt"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200: return False, "Нет файла"
    
    data = res.json()
    sha = data['sha']
    content = base64.b64decode(data['content']).decode('utf-8')
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    
    if task_number < 1 or task_number > len(lines):
        return False, "Нет такой задачи"
        
    del lines[task_number - 1]
    new_content = "\n".join(lines) + "\n" if lines else ""
    
    encoded = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Удаление задачи {task_number}", "content": encoded, "sha": sha}
    res2 = requests.put(url, headers=headers, json=payload)
    return res2.status_code in [200, 201], "OK"

def main():
    TOKEN = os.environ.get('BOT_TOKEN')
    if not TOKEN:
        print("Ошибка: BOT_TOKEN не найден!")
        return
        
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(spin, pattern="^spin_"))
    app.add_handler(CallbackQueryHandler(skip, pattern="^skip_"))
    app.add_handler(CallbackQueryHandler(take, pattern="^take_"))
    app.add_handler(CallbackQueryHandler(start_inbox_add, pattern="^inbox_add"))
    app.add_handler(CallbackQueryHandler(show_inbox, pattern="^inbox_show"))
    app.add_handler(CallbackQueryHandler(start_sorting, pattern="^inbox_sort"))
    app.add_handler(CallbackQueryHandler(cancel_inbox, pattern="^cancel_inbox"))
    app.add_handler(CallbackQueryHandler(delete_task_prompt, pattern="^delete_task_prompt"))
    app.add_handler(CallbackQueryHandler(sort_future, pattern="^sort_future"))
    app.add_handler(CallbackQueryHandler(sort_regular, pattern="^sort_regular"))
    app.add_handler(CallbackQueryHandler(sort_incubator, pattern="^sort_incubator"))
    app.add_handler(CallbackQueryHandler(inc_shkaf, pattern="^inc_shkaf"))
    app.add_handler(CallbackQueryHandler(inc_balkon, pattern="^inc_balkon"))
    app.add_handler(CallbackQueryHandler(inc_dacha, pattern="^inc_dacha"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
