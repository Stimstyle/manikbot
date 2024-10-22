import sqlite3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import datetime

# Токен бота и ID мастера
BOT_TOKEN = "7756042108:AAFfkWXQ26xsX4Gu4BPsswkcvt3GupdNfig"
MASTER_CHAT_ID = 902898850

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('manicure.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS records
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, date TEXT, time TEXT, chat_id INTEGER, services TEXT)''')
    conn.commit()
    conn.close()

# Стартовая команда с кнопками внизу экрана
async def start(update: Update, context):
    keyboard = [
        [KeyboardButton("Связаться с мастером"), KeyboardButton("Услуги и цены")],
        [KeyboardButton("Записаться на маникюр")],
        # Добавляем кнопку "Все записи (для мастера)" только для мастера
    ]

    if update.message.from_user.id == MASTER_CHAT_ID:
        keyboard.append([KeyboardButton("Все записи (для мастера)")])

    keyboard.append([KeyboardButton("Начать сначала")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('Добро пожаловать! Выберите опцию:', reply_markup=reply_markup)

# Обработчик сообщений (для ReplyKeyboardMarkup)
async def handle_message(update: Update, context):
    text = update.message.text

    if text == "Связаться с мастером":
        master_chat_link = f"tg://user?id={MASTER_CHAT_ID}"
        await update.message.reply_text(f"Вы можете связаться с мастером, по телефону: +7 (921) 396-67-74 или написать в Телеграм нажав на [эту ссылку]({master_chat_link}).", parse_mode='Markdown')
    elif text == "Услуги и цены":
        services_text = "Посмотреть примеры моих работ и актуальные расценки можно по ссылке на авито: https://www.avito.ru/sankt-peterburg/predlozheniya_uslug/manikyur_1825030335?utm_campaign=native&utm_medium=item_page_ios&utm_source=soc_sharing_seller"
        await update.message.reply_text(services_text)
    elif text == "Записаться на маникюр":
        await show_dates(update, context)
    elif text == "Все записи (для мастера)" and update.message.from_user.id == MASTER_CHAT_ID:
        await show_master_records(update, context)  # Показать записи мастера
    elif text == "Все записи (для мастера)":
        await update.message.reply_text("Эта функция доступна только мастеру.")
    elif text == "Начать сначала":
        await start(update, context)  # Возврат в главное меню
    elif text == "Вернуться в начало":
        await start(update, context)  # Возврат в главное меню
    elif text in context.user_data.get('available_dates', []):
        context.user_data['selected_date'] = text
        await show_times(update, context, text)  # Показать доступное время
    elif text in context.user_data.get('available_times', []):
        selected_date = context.user_data['selected_date']
        selected_time = text
        context.user_data['selected_time'] = selected_time
        await save_record(update, context, selected_date, selected_time)  # Запрос на выбор услуг
    elif text == "Вернуться к выбору даты":
        await show_dates(update, context)  # Показать доступные даты
    elif text == "Управление записями":
        await show_master_records(update, context)  # Показать записи мастера для удаления
    elif text.isdigit() and 'delete_record_id' in context.user_data:
        await delete_record(update, context, int(text))  # Удалить запись по ID
    else:
        await handle_services(update, context)  # Обработка выбора услуг
        
# Показать доступные даты для записи (на 14 дней вперед)
async def show_dates(update, context):
    today = datetime.date.today()
    
    # Русские названия месяцев
    russian_months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]

    dates = [(today + datetime.timedelta(days=i)).strftime("%d {}").format(russian_months[today.month - 1]) for i in range(14)]
    
    # Сохраняем доступные даты в context.user_data для последующей проверки
    context.user_data['available_dates'] = dates

    # Создаем меню с датами в виде списка
    keyboard = [[KeyboardButton(date)] for date in dates]
    keyboard.append([KeyboardButton("Вернуться в начало")])  # Добавляем кнопку возврата
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text("Выберите дату:", reply_markup=reply_markup)

# Показать доступное время для записи
async def show_times(update, context, selected_date):
    now = datetime.datetime.now()
    current_time = now.strftime('%H:%M')
    
    # Список всех доступных временных слотов
    all_times = ["10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", 
                 "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00"]
    
    conn = sqlite3.connect('manicure.db')
    cursor = conn.cursor()
    cursor.execute("SELECT time FROM records WHERE date=?", (selected_date,))
    booked_times = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Убираем забронированное время и блокируем время на 2.5 часа вперед и 2 часа назад
    available_times = []
    for time in all_times:
        time_obj = datetime.datetime.strptime(time, '%H:%M')
        # Блокируем время на 2.5 часа вперед
        block_time_forward = time_obj + datetime.timedelta(hours=2)
        # Блокируем время на 2 часа назад
        block_time_backward = time_obj - datetime.timedelta(hours=2)

        # Проверяем, не нужно ли блокировать 2.5 часа вперед и 2 часа назад
        if time not in booked_times:
            if not any(block_time_backward <= datetime.datetime.strptime(booked, '%H:%M') <= block_time_forward for booked in booked_times):
                available_times.append(time)

    # Убираем времена из прошлого
    available_times = [time for time in available_times if time >= current_time]

    # Сохраняем доступное время в context.user_data
    context.user_data['available_times'] = available_times

    keyboard = [[KeyboardButton(time)] for time in available_times]
    keyboard.append([KeyboardButton("Вернуться к выбору даты")])  # Добавляем кнопку возврата
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(f"Выберите время на {selected_date}:", reply_markup=reply_markup)

# Запись клиента с описанием услуг
async def save_record(update, context, selected_date, selected_time):
    context.user_data['selected_date'] = selected_date
    context.user_data['selected_time'] = selected_time
    
    # Предлагаем выбрать или описать услуги
    services_keyboard = [
        [KeyboardButton("Маникюр"), KeyboardButton("Снятие покрытия")],
        [KeyboardButton("Покрытие гель-лаком"), KeyboardButton("Ремонт ногтя")],
        [KeyboardButton("Наращивание ногтей"), KeyboardButton("Дизайн")],
        [KeyboardButton("Завершить выбор")]
    ]
    reply_markup = ReplyKeyboardMarkup(services_keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите процедуры или напишите ваши пожелания:", reply_markup=reply_markup)

# Обработка выбора услуг
async def handle_services(update, context):
    text = update.message.text
    if 'services' not in context.user_data:
        context.user_data['services'] = []

    if text == "Завершить выбор":
        selected_date = context.user_data['selected_date']
        selected_time = context.user_data['selected_time']
        services = ', '.join(context.user_data['services']) if context.user_data['services'] else 'Не указаны'

        # Сохраняем запись с услугами
        conn = sqlite3.connect('manicure.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO records (name, date, time, chat_id, services) VALUES (?, ?, ?, ?, ?)", 
                       (update.message.from_user.first_name, selected_date, selected_time, update.message.from_user.id, services))
        conn.commit()
        conn.close()
        master_chat_link = f"tg://user?id={MASTER_CHAT_ID}"
        # Уведомляем клиента и мастера
        await update.message.reply_text (f"Вы успешно записаны на {selected_date} в {selected_time}. Услуги: {services}. Вы можете отправить референс дизайна или обсудить детали с мастером нажав на [эту ссылку]({master_chat_link})", parse_mode='Markdown')
        await context.bot.send_message(MASTER_CHAT_ID, f"Запись: {update.message.from_user.first_name}, {selected_date} в {selected_time}. Услуги: {services}.")

        await start(update, context)  # Возврат в главное меню
    else:
        context.user_data['services'].append(text)
        await update.message.reply_text(f"Добавлено: {text}. Выберите ещё или нажмите 'Завершить выбор'.")

# Показать записи мастера
async def show_master_records(update, context):
    conn = sqlite3.connect('manicure.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, date, time, chat_id, services FROM records")
    records = cursor.fetchall()
    conn.close()

    if records:
        message = "Все записи:\n"
        for record in records:
            record_id, name, date, time, chat_id, services = record
            chat_link = f"tg://user?id={chat_id}"
            message += f"ID: {record_id}, Клиент: {name}, Дата: {date}, Время: {time}, Услуги: {services}, Чат: [ссылка]({chat_link})\n"
        message += "Введите ID записи для удаления или нажмите 'Назад'."
        context.user_data['delete_record_id'] = True  # Указываем, что мы в режиме удаления записи
        await update.message.reply_text(message, parse_mode='Markdown')
    else:
        await update.message.reply_text("Нет записей.")

# Удаление записи мастера
async def delete_record(update, context, record_id):
    conn = sqlite3.connect('manicure.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Запись с ID {record_id} успешно удалена.")
    await show_master_records(update, context)  # Показать обновленный список записей
    
# Команда для удаления записи
async def handle_delete_command(update, context):
    record_id = int(context.args[0])
    context.user_data['delete_record_id'] = record_id
    await delete_record(update, context, record_id)

# Основная функция запуска бота
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("delete", handle_delete_command))  # Команда для удаления записи
    
    application.run_polling()

if __name__ == '__main__':
    main()
