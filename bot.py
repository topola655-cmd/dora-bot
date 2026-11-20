import logging
import datetime
import os
import base64
import requests
import re
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ЧТЕНИЕ ФАЙЛА РУЛЕТКИ С GITHUB ---
async def get_roulette_items_from_github():
    token = os.environ.get('GITHUB_TOKEN')
    if not token: return []
        
    repo = "topola655-cmd/dora-bot"
    file_name = 'data.txt'
    url = f"https://api.github.com/repos/{repo}/contents/{file_name}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []

    content_data = response.json()
    content = base64.b64decode(content_data['content']).decode('utf-8')
    lines = content.split('\n')
            
    items = []
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
    return items

# --- РУЛЕТКА ---
async def do_spin(query, context):
    choice = context.user_data['current_block']
    base_seed = context.user_data['base_time']
    veto_list = context.user_data.get('veto_list', [])
    
    all_items = await get_roulette_items_from_github()
    
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['🎲 Рулетка', '📥 Инбокс'], ['📋 Задачи']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я Дора. Выбирай, что будем делать.",
        reply_markup=reply_markup
    )

async def start_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = 'roulette'
    context.user_data['veto_list'] = []
    context.user_data['base_time'] = None
    context.user_data['current_block'] = None
    context.user_data['last_index'] = None

    keyboard = [
        [InlineKeyboardButton("🎲 Весь банк", callback_data="spin_all")],
        [InlineKeyboardButton("🧹 На дела", callback_data="spin_дела"), InlineKeyboardButton("☕ На отдых", callback_data="spin_отдых")],
        [InlineKeyboardButton("➕ Добавить", callback_data="roulette_add"), InlineKeyboardButton("🗑 Удалить", callback_data="roulette_delete")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что делаем с Рулеткой?", reply_markup=reply_markup)

async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data.replace("spin_", "")
    
    # Сбрасываем старую сессию и начинаем новую при каждом нажатии
    now = query.message.date + datetime.timedelta(hours=4)
    context.user_data['base_time'] = now.hour + now.minute
    context.user_data['current_block'] = choice
    context.user_data['veto_list'] = []
    context.user_data['last_index'] = None
    
    await do_spin(query, context)

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

async def take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
        
    await query.message.reply_text("Отлично, пошла делать! 💪")

# --- ДОБАВЛЕНИЕ В РУЛЕТКУ ---
async def roulette_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🧹 Дела", callback_data="add_to_дела")],
        [InlineKeyboardButton("☕ Отдых", callback_data="add_to_отдых")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("В какой блок добавить?", reply_markup=reply_markup)

async def add_to_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    block = query.data.replace("add_to_", "")
    context.user_data['add_block'] = block
    context.user_data['mode'] = 'add_roulette'
    
    await query.message.reply_text(f"Напиши текст задачи для блока «{block.capitalize()}».")

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['mode'] = None
    await query.message.reply_text("Хорошо, отменила.")

# --- УДАЛЕНИЕ ИЗ РУЛЕТКИ ---
async def roulette_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['mode'] = 'delete_roulette'
    
    items = await get_roulette_items_from_github()
    if not items:
        await query.message.reply_text("Банк пуст.")
        return
        
    text = "Напиши номер задачи для удаления:\n\n"
    for item in items:
        text += f"{item['num']}. {item['text']}\n"
        
    if len(text) > 4000:
        text = text[:4000] + "...\n(Слишком много задач, напиши номер вслепую)"
        
    await query.message.reply_text(text)

# --- ИНБОКС ---
async def inbox_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = None
    keyboard = [
        [InlineKeyboardButton("✍️ Добавить задачу", callback_data="inbox_add")],
        [InlineKeyboardButton("📋 Показать список", callback_data="inbox_show"), InlineKeyboardButton("🌿 Разобрать", callback_data="inbox_sort")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что делаем с Инбоксом?", reply_markup=reply_markup)

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

async def cancel_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['mode'] = None
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
        
    await query.message.reply_text("Хорошо, отменила.")

async def show_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        await query.message.reply_text("Ошибка: нет доступа к GitHub.")
        return
        
    repo = "topola655-cmd/dora-bot"
    path = "inbox.txt"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 404:
        await query.message.reply_text("Инбокс пока пуст.")
        return
    elif response.status_code != 200:
        await query.message.reply_text(f"Ошибка GitHub: {response.status_code}")
        return
        
    content_data = response.json()
    current_content = base64.b64decode(content_data['content']).decode('utf-8')
    lines = [line.strip() for line in current_content.split('\n') if line.strip()]
        
    if not lines:
        await query.message.reply_text("Инбокс пока пуст.")
        return
        
    text = "📋 Твой Инбокс:\n\n"
    for i, line in enumerate(lines, 1):
        text += f"{i}. {line}\n"
        
    keyboard = [[InlineKeyboardButton("🗑 Удалить задачи", callback_data="delete_task_prompt")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
        
    await query.message.reply_text(text, reply_markup=reply_markup)

async def delete_task_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['mode'] = 'delete_inbox'
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
        
    await query.message.reply_text("Напиши номера задач через запятую (например, 1, 3, 4).")

# --- РАЗБОР ИНБОКСА ---
async def start_sorting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['sort_skip_count'] = 0
    
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
        
    await next_sorting_task(query.message, context)

async def next_sorting_task(message, context):
    token = os.environ.get('GITHUB_TOKEN')
    repo = "topola655-cmd/dora-bot"
    url = f"https://api.github.com/repos/{repo}/contents/inbox.txt"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        await message.reply_text("Инбокс пуст или ошибка доступа.")
        context.user_data['mode'] = None
        return
        
    content_data = response.json()
    current_content = base64.b64decode(content_data['content']).decode('utf-8')
    lines = [line.strip() for line in current_content.split('\n') if line.strip()]
    
    if not lines:
        await message.reply_text("Инбокс пуст! Все разобрали. ✅")
        context.user_data['mode'] = None
        return
        
    skip_count = context.user_data.get('sort_skip_count', 0)
    
    if skip_count >= len(lines):
        await message.reply_text("Все задачи просмотрены. Инбокс можно закрывать. ✅")
        context.user_data['mode'] = None
        return
        
    task_text = lines[skip_count]
    context.user_data['sorting_task'] = task_text
    context.user_data['mode'] = 'sorting'
    
    keyboard = [
        [InlineKeyboardButton("📅 Будущее", callback_data="sort_future")],
        [InlineKeyboardButton("🔁 Регулярные", callback_data="sort_regular"), InlineKeyboardButton("📦 Инкубатор", callback_data="sort_incubator")],
        [InlineKeyboardButton("⏭ Пропустить", callback_data="sort_skip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        f"Разбираем задачу:\n«{task_text}»\n\nКуда её?",
        reply_markup=reply_markup
    )

async def sort_future(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_dest'] = '📅 Будущее'
    context.user_data['mode'] = 'sort_date'
    await query.message.reply_text("Напиши дату (и время, если есть).")

async def sort_regular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_dest'] = '🔁 Регулярные'
    context.user_data['mode'] = 'sort_rule'
    await query.message.reply_text("Напиши правило (например, «каждую субботу»).")

async def sort_incubator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_dest'] = '📦 Инкубатор'
    
    keyboard = [
        [InlineKeyboardButton("Шкаф", callback_data="inc_shkaf")],
        [InlineKeyboardButton("Балкон", callback_data="inc_balkon"), InlineKeyboardButton("Дача", callback_data="inc_dacha")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Куда?", reply_markup=reply_markup)

async def inc_shkaf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_extra'] = 'Шкаф'
    await save_sorted_task(query.message, context)

async def inc_balkon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_extra'] = 'Балкон'
    await save_sorted_task(query.message, context)

async def inc_dacha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['sort_extra'] = 'Дача'
    await save_sorted_task(query.message, context)

async def sort_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    skip_count = context.user_data.get('sort_skip_count', 0)
    context.user_data['sort_skip_count'] = skip_count + 1
    
    await next_sorting_task(query.message, context)

async def save_sorted_task(message, context):
    task_text = context.user_data.get('sorting_task')
    dest = context.user_data.get('sort_dest')
    extra = context.user_data.get('sort_extra', '')
    
    if not task_text:
        return
        
    if dest == '📅 Будущее':
        line = f"📅 {task_text} ({extra})"
        block_header = "📅 БУДУЩЕЕ:"
    elif dest == '🔁 Регулярные':
        line = f"🔁 {task_text} ({extra})"
        block_header = "🔁 РЕГУЛЯРНЫЕ:"
    elif dest == '📦 Инкубатор':
        line = f"📦 [{extra}] {task_text}"
        block_header = "📦 ИНКУБАТОР:"
        
    success, msg = await append_to_github("tasks.txt", line + "\n", block_name=block_header)
    
    if success:
        await delete_first_from_inbox(task_text)
        
        await message.reply_text(f"Задача отправлена в {dest} ✅\n\n{line}")
        
        await next_sorting_task(message, context)
    else:
        await message.reply_text(f"Ошибка сохранения: {msg}")

# --- ПРОСМОТР СПИСКОВ ---
async def show_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Будущее", callback_data="view_future")],
        [InlineKeyboardButton("🔁 Регулярные", callback_data="view_regular"), InlineKeyboardButton("📦 Инкубатор", callback_data="view_incubator")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Какой список показать?", reply_markup=reply_markup)

async def view_future(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_block_from_github(query, "📅")
    
async def view_regular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_block_from_github(query, "🔁")

async def view_incubator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    token = os.environ.get('GITHUB_TOKEN')
    repo = "topola655-cmd/dora-bot"
    url = f"https://api.github.com/repos/{repo}/contents/tasks.txt"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        await query.message.reply_text("Файл задач не найден.")
        return
        
    content_data = response.json()
    content = base64.b64decode(content_data['content']).decode('utf-8')
    lines = [line.strip() for line in content.split('\n')]
    
    shkaf = []
    balkon = []
    dacha = []
    
    for line in lines:
        if line.startswith("📦 [Шкаф]"):
            shkaf.append(line.replace("📦 [Шкаф]", "").strip())
        elif line.startswith("📦 [Балкон]"):
            balkon.append(line.replace("📦 [Балкон]", "").strip())
        elif line.startswith("📦 [Дача]"):
            dacha.append(line.replace("📦 [Дача]", "").strip())
            
    text = "📦 ИНКУБАТОР:\n\n"
    
    if shkaf:
        text += "🗄️ Шкаф:\n"
        for i, t in enumerate(shkaf, 1):
            text += f"{i}. {t}\n"
        text += "\n"
    if balkon:
        text += "🌤 Балкон:\n"
        for i, t in enumerate(balkon, 1):
            text += f"{i}. {t}\n"
        text += "\n"
    if dacha:
        text += "🏡 Дача:\n"
        for i, t in enumerate(dacha, 1):
            text += f"{i}. {t}\n"
        text += "\n"
        
    if not shkaf and not balkon and not dacha:
        text += "Пока пусто."
        
    await query.message.reply_text(text.strip())

async def show_block_from_github(query, emoji):
    token = os.environ.get('GITHUB_TOKEN')
    repo = "topola655-cmd/dora-bot"
    url = f"https://api.github.com/repos/{repo}/contents/tasks.txt"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        await query.message.reply_text("Файл задач не найден.")
        return
        
    content_data = response.json()
    content = base64.b64decode(content_data['content']).decode('utf-8')
    lines = [line.strip() for line in content.split('\n')]
    
    tasks = [l for l in lines if l.startswith(emoji)]
    
    if not tasks:
        await query.message.reply_text("Тут пока пусто.")
        return
        
    text = ""
    for i, t in enumerate(tasks):
        text += f"{t}\n"
        if i == 0:
            text += "\n"
        
    await query.message.reply_text(text.strip())

# --- GITHUB ФУНКЦИИ ---
async def append_to_github(path, text, block_name=None):
    token = os.environ.get('GITHUB_TOKEN')
    if not token: return False, "Токен не найден"
        
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
        
    if block_name:
        lines = current_content.split('\n')
        header_index = -1
        
        for i, line in enumerate(lines):
            if block_name in line:
                header_index = i
                break
                
        if header_index != -1:
            lines.insert(header_index + 1, text.strip())
        else:
            lines.append(block_name)
            lines.append(text.strip())
            
        new_content = "\n".join(lines)
    else:
        new_content = current_content + text

    encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    
    data = {"message": f"Обновление {path}", "content": encoded_content}
    if sha:
        data["sha"] = sha
        
    response = requests.put(url, headers=headers, json=data)
    return response.status_code in [200, 201], "OK"

async def delete_first_from_inbox(task_text_to_delete):
    token = os.environ.get('GITHUB_TOKEN')
    repo = "topola655-cmd/dora-bot"
    url = f"https://api.github.com/repos/{repo}/contents/inbox.txt"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200: return
        
    content_data = response.json()
    sha = content_data['sha']
    current_content = base64.b64decode(content_data['content']).decode('utf-8')
    lines = [line.strip() for line in current_content.split('\n') if line.strip()]
    
    if task_text_to_delete in lines:
        lines.remove(task_text_to_delete)
        
        new_content = "\n".join(lines) + "\n" if lines else ""
        encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
        data = {"message": "Удалена разобранная задача", "content": encoded_content, "sha": sha}
        requests.put(url, headers=headers, json=data)
        
        with open('inbox.txt', 'w', encoding='utf-8') as f:
            f.write(new_content)

async def delete_multiple_from_github(task_numbers):
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
    
    for num in sorted(task_numbers, reverse=True):
        if 1 <= num <= len(lines):
            del lines[num - 1]
            
    new_content = "\n".join(lines) + "\n" if lines else ""
    encoded = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Удаление задач", "content": encoded, "sha": sha}
    res2 = requests.put(url, headers=headers, json=payload)
    return res2.status_code in [200, 201], "OK"

# --- ФУНКЦИИ ДЛЯ РУЛЕТКИ (ДОБАВЛЕНИЕ/УДАЛЕНИЕ) ---
async def add_roulette_task_to_github(block, task_text):
    token = os.environ.get('GITHUB_TOKEN')
    if not token: return False, "Токен не найден"
        
    repo = "topola655-cmd/dora-bot"
    url = f"https://api.github.com/repos/{repo}/contents/data.txt"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return False, "Файл data.txt не найден"
        
    content_data = response.json()
    sha = content_data['sha']
    content = base64.b64decode(content_data['content']).decode('utf-8')
    lines = content.split('\n')
    
    max_num = 0
    for line in lines:
        match = re.match(r'^(\d+)\.', line.strip())
        if match:
            max_num = max(max_num, int(match.group(1)))
            
    new_num = max_num + 1
    
    block_header = "🧹 Дела" if block == "дела" else "🎈 Отдых"
    insert_index = -1
    
    if block == "отдых":
        for i, line in enumerate(lines):
            if "Отдых" in line:
                insert_index = i + 1
                break
    else:
        for i, line in enumerate(lines):
            if "Отдых" in line:
                insert_index = i
                break
        if insert_index == -1:
            insert_index = len(lines)
            
    new_task = f"{new_num}. {task_text}"
    
    if insert_index != -1:
        lines.insert(insert_index, new_task)
    else:
        lines.append(new_task)
        
    new_content = "\n".join(lines)
    encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    
    data = {"message": f"Добавлена задача в Рулетку ({block})", "content": encoded_content, "sha": sha}
    response = requests.put(url, headers=headers, json=data)
    
    return response.status_code in [200, 201], "OK"

async def delete_roulette_task_from_github(task_num):
    token = os.environ.get('GITHUB_TOKEN')
    if not token: return False, "Токен не найден"
        
    repo = "topola655-cmd/dora-bot"
    url = f"https://api.github.com/repos/{repo}/contents/data.txt"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return False, "Файл data.txt не найден"
        
    content_data = response.json()
    sha = content_data['sha']
    content = base64.b64decode(content_data['content']).decode('utf-8')
    lines = content.split('\n')
    
    deleted = False
    for i, line in enumerate(lines):
        match = re.match(r'^(\d+)\.', line.strip())
        if match and int(match.group(1)) == task_num:
            del lines[i]
            deleted = True
            break
            
    if not deleted:
        return False, "Задача с таким номером не найдена"
        
    new_lines = []
    current_num = 1
    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            new_lines.append(line)
            continue
            
        match = re.match(r'^(\d+)\.(.*)$', clean_line)
        if match:
            new_lines.append(f"{current_num}.{match.group(2)}")
            current_num += 1
        else:
            new_lines.append(line)
            
    new_content = "\n".join(new_lines)
    encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    
    data = {"message": f"Удалена задача {task_num} из Рулетки", "content": encoded_content, "sha": sha}
    response = requests.put(url, headers=headers, json=data)
    
    return response.status_code in [200, 201], "OK"

# --- ОБРАБОТЧИК ТЕКСТА ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if text in ['🎲 рулетка', 'рулетка', 'крути рулетку', 'дора, крути рулетку']:
        await start_roulette(update, context)
    elif text == '📥 инбокс':
        await inbox_menu(update, context)
    elif text == '📋 задачи':
        await show_tasks_menu(update, context)
    else:
        mode = context.user_data.get('mode')
        
        if mode == 'inbox':
            lines = update.message.text.split('\n')
            saved_count = 0
            
            for line in lines:
                clean_line = line.strip()
                if clean_line:
                    success, message = await append_to_github("inbox.txt", clean_line + "\n")
                    if success:
                        saved_count += 1
                        
            if saved_count > 0:
                await update.message.reply_text(f"Записала в Инбокс {saved_count} задач(и) ✅")
            else:
                await update.message.reply_text("Нечего записывать (пустое сообщение).")
                
            context.user_data['mode'] = None
            
        elif mode == 'delete_inbox':
            try:
                parts = [int(p.strip()) for p in update.message.text.split(',') if p.strip().isdigit()]
                if not parts:
                    await update.message.reply_text("Не поняла номера. Напиши цифры через запятую (например: 1, 3).")
                    return
                    
                success, msg = await delete_multiple_from_github(parts)
                if success:
                    await update.message.reply_text(f"Задачи {', '.join(map(str, parts))} удалены ✅")
                else:
                    await update.message.reply_text(f"Ошибка: {msg}")
            except Exception:
                await update.message.reply_text("Ошибка при удалении. Проверь номера.")
            context.user_data['mode'] = None
            
        elif mode == 'sort_date':
            context.user_data['sort_extra'] = update.message.text
            await save_sorted_task(update.message, context)
            context.user_data['mode'] = None
            
        elif mode == 'sort_rule':
            context.user_data['sort_extra'] = update.message.text
            await save_sorted_task(update.message, context)
            context.user_data['mode'] = None
            
        elif mode == 'add_roulette':
            block = context.user_data.get('add_block')
            if block:
                success, msg = await add_roulette_task_to_github(block, update.message.text)
                if success:
                    await update.message.reply_text(f"Задача добавлена в блок «{block.capitalize()}» ✅")
                else:
                    await update.message.reply_text(f"Ошибка: {msg}")
            context.user_data['mode'] = None
            
        elif mode == 'delete_roulette':
            try:
                task_num = int(update.message.text.strip())
                success, msg = await delete_roulette_task_from_github(task_num)
                if success:
                    await update.message.reply_text(f"Задача {task_num} удалена из Рулетки ✅")
                else:
                    await update.message.reply_text(f"Ошибка: {msg}")
            except ValueError:
                await update.message.reply_text("П
