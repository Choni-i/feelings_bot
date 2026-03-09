import sqlite3
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta, time
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from collections import Counter
import json

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = '8678287812:AAEx96Td_0awEokl94E0T_ws_vU28lDaF8E'

# Список эмоций для опроса
EMOTIONS = ["😊 Радость", "😐 Спокойствие", "😢 Грусть", "😠 Злость", "😰 Тревога", "😴 Усталость"]

# Часто встречающиеся причины (для быстрого выбора)
COMMON_REASONS = {
    "😊 Радость": ["🏆 Успех", "👨‍👩‍👧 Семья", "💼 Работа", "❤️ Отношения", "🎮 Хобби", "☀️ Погода", "Другое"],
    "😐 Спокойствие": ["🧘 Медитация", "📚 Отдых", "🚶 Прогулка", "🎵 Музыка", "🍵 Чай/Кофе", "Другое"],
    "😢 Грусть": ["💔 Расставание", "📉 Неудача", "😔 Одиночество", "⛈️ Погода", "😢 Ностальгия", "Другое"],
    "😠 Злость": ["🤬 Конфликт", "🚦 Пробки", "💻 Работа", "👥 Люди", "⚡ Стресс", "Другое"],
    "😰 Тревога": ["📝 Экзамен", "💰 Финансы", "🏥 Здоровье", "📅 Дедлайн", "🌃 Будущее", "Другое"],
    "😴 Усталость": ["💪 Перегрузка", "😴 Недосып", "💻 Работа", "🏃 Спорт", "📚 Учеба", "Другое"]
}

# Цвета для графиков
EMOTION_COLORS = {
    "😊 Радость": "#FFD700",
    "😐 Спокойствие": "#87CEEB",
    "😢 Грусть": "#4169E1",
    "😠 Злость": "#FF4500",
    "😰 Тревога": "#9370DB",
    "😴 Усталость": "#808080"
}

# Варианты времени для напоминаний
REMINDER_TIMES = [
    "🌅 Утро (09:00)",
    "☀️ День (14:00)", 
    "🌆 Вечер (19:00)",
    "🌙 Ночь (22:00)",
    "⏰ Свое время"
]

# Глобальный планировщик
scheduler = AsyncIOScheduler()

# Клавиатура с эмоциями
def get_emotions_keyboard():
    keyboard = [[emotion] for emotion in EMOTIONS]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

# Клавиатура с причинами для конкретной эмоции
def get_reasons_keyboard(emotion):
    reasons = COMMON_REASONS.get(emotion, ["Другое"])
    keyboard = []
    row = []
    for i, reason in enumerate(reasons):
        row.append(InlineKeyboardButton(reason, callback_data=f"reason_{emotion}_{reason}"))
        if (i + 1) % 2 == 0:  # По 2 кнопки в ряд
            keyboard.append(row)
            row = []
    if row:  # Добавляем оставшиеся кнопки
        keyboard.append(row)
    
    # Добавляем кнопку пропуска
    keyboard.append([InlineKeyboardButton("⏭️ Пропустить", callback_data=f"reason_{emotion}_skip")])
    
    return InlineKeyboardMarkup(keyboard)

# Создание базы данных
def init_db():
    conn = sqlite3.connect('mood_tracker.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS moods
                 (user_id INTEGER, date TEXT, emotion TEXT, reason TEXT, timestamp TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (user_id INTEGER PRIMARY KEY, 
                  reminder_time TEXT,
                  reminder_hour INTEGER,
                  reminder_minute INTEGER,
                  is_active INTEGER DEFAULT 1,
                  job_id TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS reminder_history
                 (user_id INTEGER, date TEXT, sent INTEGER)''')
    
    conn.commit()
    conn.close()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для отслеживания настроения с анализом причин!\n\n"
        "📝 Каждый день отмечай свои эмоции и указывай причины,\n"
        "а я буду строить графики и показывать статистику!\n\n"
        "📋 Доступные команды:\n"
        "/checkin - Отметить сегодняшнее настроение\n"
        "/report - Показать радар эмоций за неделю\n"
        "/reasons - Анализ причин эмоций\n"
        "/reminder - Настроить напоминания\n"
        "/stats - Общая статистика\n"
        "/help - Показать все команды"
    )

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Полный список команд:\n\n"
        "/start - Начать работу\n"
        "/checkin - Отметить настроение (с указанием причины)\n"
        "/report - Показать радар эмоций за неделю\n"
        "/reasons - Анализ причин по каждой эмоции\n"
        "/reminder - Настроить напоминания\n"
        "/off - Отключить напоминания\n"
        "/status - Статус напоминаний\n"
        "/stats - Общая статистика\n"
        "/export - Выгрузить данные в CSV\n"
        "/help - Это сообщение"
    )

# Команда /checkin - начать опрос
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect('mood_tracker.db')
    c = conn.cursor()
    c.execute("SELECT * FROM moods WHERE user_id=? AND date=?", (user_id, today))
    existing = c.fetchone()
    conn.close()
    
    if existing:
        await update.message.reply_text(
            "✅ Ты уже отмечал настроение сегодня!\n"
            "Посмотри статистику: /reasons"
        )
    else:
        await update.message.reply_text(
            "📝 Как ты себя чувствуешь сегодня?",
            reply_markup=get_emotions_keyboard()
        )

# Обработка ответа с эмоцией
async def handle_emotion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_emotion = update.message.text
    user_id = update.effective_user.id
    
    if user_emotion in EMOTIONS:
        # Сохраняем выбранную эмоцию в контексте
        context.user_data['current_emotion'] = user_emotion
        context.user_data['waiting_for_reason'] = True
        
        # Показываем клавиатуру с причинами
        await update.message.reply_text(
            f"Ты выбрал: {user_emotion}\n\n"
            f"📌 Укажи причину (или пропусти):",
            reply_markup=get_reasons_keyboard(user_emotion)
        )
    else:
        await update.message.reply_text(
            "👆 Выбери эмоцию из списка",
            reply_markup=get_emotions_keyboard()
        )

# Обработка выбора причины
async def reason_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Парсим callback_data
    data = query.data.split('_')
    emotion = data[1]
    reason = data[2] if len(data) > 2 else "Не указана"
    
    user_id = query.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Сохраняем в базу данных
    conn = sqlite3.connect('mood_tracker.db')
    c = conn.cursor()
    
    # Проверяем, не записано ли уже за сегодня
    c.execute("SELECT * FROM moods WHERE user_id=? AND date=?", (user_id, today))
    existing = c.fetchone()
    
    if not existing:
        c.execute("INSERT INTO moods VALUES (?, ?, ?, ?, ?)",
                  (user_id, today, emotion, reason, timestamp))
        conn.commit()
        
        # Отправляем подтверждение
        if reason == "skip":
            await query.edit_message_text(
                f"✅ Записал: {emotion}\n"
                f"Причина не указана"
            )
        else:
            # Эмодзи для разных причин
            reason_emojis = {
                "🏆 Успех": "Поздравляю с успехом! 🎉",
                "👨‍👩‍👧 Семья": "Семья - это важно! ❤️",
                "💔 Расставание": "Держись! Всё наладится 🌈",
                "📉 Неудача": "Неудачи делают нас сильнее! 💪",
                "💰 Финансы": "Финансы - дело наживное 📈",
                "🏥 Здоровье": "Береги себя! 🌿",
                "😴 Недосып": "Отдых - это важно! 😴"
            }
            
            extra_message = reason_emojis.get(reason, "Спасибо за честность! 🌟")
            
            await query.edit_message_text(
                f"✅ Записал: {emotion}\n"
                f"📌 Причина: {reason}\n\n"
                f"{extra_message}\n\n"
                f"Посмотреть статистику: /reasons"
            )
    else:
        await query.edit_message_text(
            "❌ Ты уже отмечал настроение сегодня!\n"
            "Посмотри статистику: /reasons"
        )
    
    conn.close()
    
    # Очищаем контекст
    context.user_data.pop('current_emotion', None)
    context.user_data.pop('waiting_for_reason', None)

# Функция для анализа причин по эмоциям
async def analyze_reasons(user_id, emotion=None):
    conn = sqlite3.connect('mood_tracker.db')
    c = conn.cursor()
    
    if emotion:
        # Анализ причин для конкретной эмоции
        c.execute("""
            SELECT reason, COUNT(*) as count 
            FROM moods 
            WHERE user_id=? AND emotion=? AND reason != 'skip' AND reason != 'Не указана'
            GROUP BY reason
            ORDER BY count DESC
            LIMIT 10
        """, (user_id, emotion))
    else:
        # Общий анализ всех причин
        c.execute("""
            SELECT emotion, reason, COUNT(*) as count 
            FROM moods 
            WHERE user_id=? AND reason != 'skip' AND reason != 'Не указана'
            GROUP BY emotion, reason
            ORDER BY emotion, count DESC
        """, (user_id,))
    
    data = c.fetchall()
    conn.close()
    
    return data

# Команда /reasons - анализ причин
async def show_reasons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Создаем клавиатуру для выбора эмоции
    keyboard = []
    for emotion in EMOTIONS:
        keyboard.append([InlineKeyboardButton(emotion, callback_data=f"reasons_{emotion}")])
    keyboard.append([InlineKeyboardButton("📊 Общая статистика", callback_data="reasons_all")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 Анализ причин настроения\n\n"
        "Выбери эмоцию для детального анализа:",
        reply_markup=reply_markup
    )

# Обработка выбора для анализа причин
async def reasons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data.replace("reasons_", "")
    
    if data == "all":
        # Общая статистика
        data = await analyze_reasons(user_id)
        
        if not data:
            await query.edit_message_text(
                "📊 Пока нет данных с указанными причинами.\n"
                "Отмечай настроение с причинами командой /checkin"
            )
            return
        
        # Группируем по эмоциям
        message = "📊 Общая статистика причин:\n\n"
        current_emotion = None
        
        for emotion, reason, count in data:
            if emotion != current_emotion:
                current_emotion = emotion
                message += f"\n{emotion}:\n"
            message += f"  • {reason}: {count} раз\n"
        
        await query.edit_message_text(message)
        
    else:
        # Статистика по конкретной эмоции
        data = await analyze_reasons(user_id, data)
        
        if not data:
            await query.edit_message_text(
                f"📊 Для эмоции {data} пока нет данных с причинами.\n"
                f"Отмечай эту эмоцию с причинами командой /checkin"
            )
            return
        
        # Создаем график для этой эмоции
        reasons = [row[0] for row in data]
        counts = [row[1] for row in data]
        
        plt.figure(figsize=(10, 6))
        colors = plt.cm.viridis(np.linspace(0, 1, len(reasons)))
        plt.barh(reasons, counts, color=colors)
        plt.xlabel('Количество раз')
        plt.title(f'Причины для {data}')
        plt.tight_layout()
        
        filename = f'reasons_{user_id}_{data}.png'
        plt.savefig(filename, dpi=100, bbox_inches='tight')
        plt.close()
        
        with open(filename, 'rb') as photo:
            await query.message.reply_photo(
                photo,
                caption=f"📊 Топ причин для {data}"
            )
        
        await query.message.delete()

# Команда /stats - общая статистика
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('mood_tracker.db')
    c = conn.cursor()
    
    # Общая статистика по эмоциям
    c.execute("""
        SELECT emotion, COUNT(*) as count 
        FROM moods 
        WHERE user_id=?
        GROUP BY emotion
        ORDER BY count DESC
    """, (user_id,))
    
    emotion_stats = c.fetchall()
    
    # Статистика по причинам
    c.execute("""
        SELECT COUNT(*) FROM moods 
        WHERE user_id=? AND reason != 'skip' AND reason != 'Не указана'
    """, (user_id,))
    
    reasons_count = c.fetchone()[0] or 0
    
    # Общее количество дней
    c.execute("SELECT COUNT(DISTINCT date) FROM moods WHERE user_id=?", (user_id,))
    total_days = c.fetchone()[0] or 0
    
    conn.close()
    
    if not emotion_stats:
        await update.message.reply_text(
            "📊 У тебя пока нет записей. Начни с /checkin"
        )
        return
    
    message = f"📈 Статистика за {total_days} дней:\n\n"
    
    for emotion, count in emotion_stats:
        percentage = (count / total_days) * 100
        message += f"{emotion}: {count} раз ({percentage:.1f}%)\n"
    
    message += f"\n📌 Причины указаны в {reasons_count} из {total_days} записей"
    message += f" ({reasons_count/total_days*100:.1f}%)"
    
    # Самая частая эмоция
    top_emotion = max(emotion_stats, key=lambda x: x[1])[0]
    message += f"\n\n🌟 Самая частая эмоция: {top_emotion}"
    
    await update.message.reply_text(message)

# Команда /export - выгрузить данные
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('mood_tracker.db')
    c = conn.cursor()
    c.execute("""
        SELECT date, emotion, reason, timestamp 
        FROM moods 
        WHERE user_id=?
        ORDER BY date DESC
    """, (user_id,))
    
    data = c.fetchall()
    conn.close()
    
    if not data:
        await update.message.reply_text("📊 Нет данных для экспорта")
        return
    
    # Создаем CSV файл
    filename = f'mood_data_{user_id}.csv'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("Дата,Эмоция,Причина,Время записи\n")
        for row in data:
            reason = row[2] if row[2] != "skip" else "Не указана"
            f.write(f"{row[0]},{row[1]},{reason},{row[3]}\n")
    
    with open(filename, 'rb') as file:
        await update.message.reply_document(
            file,
            filename=filename,
            caption="📊 Твои данные по настроению"
        )

# Функции для напоминаний (те же, что и в предыдущем ответе)
async def send_reminder_func(user_id: int, bot):
    """Функция отправки напоминания"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect('mood_tracker.db')
        c = conn.cursor()
        c.execute("SELECT * FROM moods WHERE user_id=? AND date=?", (user_id, today))
        existing = c.fetchone()
        
        c.execute("SELECT * FROM reminder_history WHERE user_id=? AND date=?", (user_id, today))
        reminder_sent = c.fetchone()
        
        if not existing and not reminder_sent:
            await bot.send_message(
                chat_id=user_id,
                text="🌅 Привет! Как ты себя чувствуешь сегодня?\n\n"
                     "Не забудь отметить настроение и указать причину командой /checkin"
            )
            
            c.execute("INSERT INTO reminder_history VALUES (?, ?, 1)", (user_id, today))
            conn.commit()
            logger.info(f"✅ Напоминание отправлено пользователю {user_id}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке напоминания: {e}")

# Команда /reminder - настройка напоминаний
async def reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for time_option in REMINDER_TIMES:
        keyboard.append([InlineKeyboardButton(time_option, callback_data=f"remind_{time_option}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⏰ Выбери время для ежедневных напоминаний:",
        reply_markup=reply_markup
    )

# Обработка выбора времени
async def reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    time_option = query.data.replace("remind_", "")
    
    if time_option == "⏰ Свое время":
        context.user_data['waiting_for_custom_time'] = True
        await query.edit_message_text(
            "⌨️ Напиши время в формате ЧЧ:ММ (например, 15:30)"
        )
    else:
        hour, minute = parse_time_string(time_option)
        if hour is not None:
            job_id = f"reminder_{user_id}"
            
            conn = sqlite3.connect('mood_tracker.db')
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO reminders 
                         (user_id, reminder_time, reminder_hour, reminder_minute, is_active, job_id) 
                         VALUES (?, ?, ?, ?, 1, ?)''',
                      (user_id, time_option, hour, minute, job_id))
            conn.commit()
            conn.close()
            
            # Планируем задачу
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
            
            scheduler.add_job(
                send_reminder_func,
                CronTrigger(hour=hour, minute=minute),
                args=[user_id, context.bot],
                id=job_id,
                replace_existing=True
            )
            
            await query.edit_message_text(
                f"✅ Буду напоминать {time_option.lower()}"
            )

def parse_time_string(time_str):
    if time_str == "🌅 Утро (09:00)":
        return 9, 0
    elif time_str == "☀️ День (14:00)":
        return 14, 0
    elif time_str == "🌆 Вечер (19:00)":
        return 19, 0
    elif time_str == "🌙 Ночь (22:00)":
        return 22, 0
    return None, None

# Обработка пользовательского времени
async def handle_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_custom_time'):
        try:
            time_str = update.message.text.strip()
            hour, minute = map(int, time_str.split(':'))
            
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                user_id = update.effective_user.id
                job_id = f"reminder_{user_id}"
                
                # Сохраняем настройки
                conn = sqlite3.connect('mood_tracker.db')
                c = conn.cursor()
                c.execute('''INSERT OR REPLACE INTO reminders 
                             (user_id, reminder_time, reminder_hour, reminder_minute, is_active, job_id) 
                             VALUES (?, ?, ?, ?, 1, ?)''',
                          (user_id, f"⏰ {time_str}", hour, minute, job_id))
                conn.commit()
                conn.close()
                
                # Планируем задачу
                try:
                    # Удаляем старую задачу если есть
                    if scheduler.get_job(job_id):
                        scheduler.remove_job(job_id)
                    
                    # Добавляем новую задачу
                    scheduler.add_job(
                        send_reminder_func,
                        CronTrigger(hour=hour, minute=minute),
                        args=[user_id, context.bot],
                        id=job_id,
                        replace_existing=True
                    )
                    
                    context.user_data['waiting_for_custom_time'] = False
                    
                    await update.message.reply_text(
                        f"✅ Отлично! Я буду напоминать тебе в {hour:02d}:{minute:02d} каждый день!"
                    )
                    logger.info(f"✅ Напоминание установлено для пользователя {user_id} на {hour:02d}:{minute:02d}")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при установке напоминания: {e}")
                    await update.message.reply_text(
                        "❌ Произошла ошибка при установке напоминания."
                    )
            else:
                await update.message.reply_text(
                    "❌ Неправильный формат! Часы: 0-23, минуты: 0-59.\n"
                    "Пример: 15:30"
                )
        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Неправильный формат! Напиши время в формате ЧЧ:ММ\n"
                "Пример: 15:30"
            )
    else:
        # Если не ждем кастомное время, обрабатываем как обычную эмоцию
        await handle_emotion(update, context)

# Команда /off - отключить напоминания
async def turn_off_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    job_id = f"reminder_{user_id}"
    
    conn = sqlite3.connect('mood_tracker.db')
    c = conn.cursor()
    c.execute("UPDATE reminders SET is_active=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    
    await update.message.reply_text("🔕 Напоминания отключены")

# Команда /status
async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    job_id = f"reminder_{user_id}"
    
    conn = sqlite3.connect('mood_tracker.db')
    c = conn.cursor()
    c.execute("SELECT reminder_time, reminder_hour, reminder_minute FROM reminders WHERE user_id=? AND is_active=1", (user_id,))
    reminder = c.fetchone()
    conn.close()
    
    if reminder and scheduler.get_job(job_id):
        await update.message.reply_text(
            f"✅ Напоминания активны\n"
            f"⏰ Время: {reminder[0]}"
        )
    else:
        await update.message.reply_text("🔕 Нет активных напоминаний")

# Восстановление напоминаний при запуске
async def restore_reminders(bot):
    try:
        conn = sqlite3.connect('mood_tracker.db')
        c = conn.cursor()
        c.execute("SELECT user_id, reminder_hour, reminder_minute, job_id FROM reminders WHERE is_active=1")
        active = c.fetchall()
        conn.close()
        
        for user_id, hour, minute, job_id in active:
            scheduler.add_job(
                send_reminder_func,
                CronTrigger(hour=hour, minute=minute),
                args=[user_id, bot],
                id=job_id,
                replace_existing=True
            )
            logger.info(f"🔄 Восстановлено напоминание для {user_id}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка восстановления: {e}")

# Создание радар-чарта для эмоций
async def create_emotion_radar(user_id, weeks_offset=0):
    try:
        conn = sqlite3.connect('mood_tracker.db')
        c = conn.cursor()
        
        # Определяем даты для графика
        end_date = datetime.now() - timedelta(weeks=weeks_offset)
        start_date = end_date - timedelta(days=6)
        
        end_date_str = end_date.strftime("%Y-%m-%d")
        start_date_str = start_date.strftime("%Y-%m-%d")
        
        # Получаем все эмоции за неделю
        c.execute("""
            SELECT emotion 
            FROM moods 
            WHERE user_id=? AND date BETWEEN ? AND ?
        """, (user_id, start_date_str, end_date_str))
        
        data = c.fetchall()
        conn.close()
        
        if len(data) < 3:  # Нужно минимум 3 записи для графика
            return None
        
        # Подсчитываем частоту каждой эмоции
        emotion_counts = Counter([row[0] for row in data])
        
        # Подготавливаем данные для радара
        emotions = []
        counts = []
        
        for emotion in EMOTIONS:
            emotions.append(emotion)
            counts.append(emotion_counts.get(emotion, 0))
        
        # Нормализуем значения (преобразуем в проценты от максимального)
        max_count = max(counts) if max(counts) > 0 else 1
        normalized_counts = [count / max_count * 10 for count in counts]  # Шкала 0-10
        
        # Создаем радар-чарт
        N = len(emotions)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]  # Замыкаем круг
        
        # Данные должны быть замкнуты
        radar_data = normalized_counts + normalized_counts[:1]
        
        # Создаем фигуру с двумя подграфиками
        fig = plt.figure(figsize=(15, 7))
        
        # 1. Радар-чарт
        ax1 = fig.add_subplot(121, projection='polar')
        
        # Рисуем основную линию и заливку
        ax1.plot(angles, radar_data, 'o-', linewidth=3, color='#4CAF50', markersize=8)
        ax1.fill(angles, radar_data, alpha=0.3, color='#4CAF50')
        
        # Устанавливаем метки для осей
        ax1.set_xticks(angles[:-1])
        ax1.set_xticklabels([e.split()[0] for e in emotions], fontsize=12, fontweight='bold')
        
        # Устанавливаем границы для радиальной оси
        ax1.set_ylim(0, 10)
        ax1.set_yticks([2, 4, 6, 8, 10])
        ax1.set_yticklabels(['20%', '40%', '60%', '80%', '100%'], fontsize=8)
        ax1.set_rlabel_position(0)
        
        # Добавляем сетку
        ax1.grid(True, alpha=0.3)
        
        # Добавляем заголовок для радара
        week_label = "Текущая неделя" if weeks_offset == 0 else f"Неделя {weeks_offset} назад"
        ax1.set_title(f'Эмоциональный радар\n{week_label}', fontsize=14, pad=20, fontweight='bold')
        
        # Добавляем значения
        for i, (angle, count, norm_count) in enumerate(zip(angles[:-1], counts, normalized_counts)):
            percentage = (count / len(data)) * 100
            ax1.annotate(f'{count} ({percentage:.0f}%)', 
                       xy=(angle, norm_count), 
                       xytext=(angle, norm_count + 0.8),
                       ha='center', va='bottom',
                       fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))
        
        # 2. Круговая диаграмма (для наглядности)
        ax2 = fig.add_subplot(122)
        
        # Фильтруем эмоции с ненулевыми значениями
        non_zero_emotions = []
        non_zero_counts = []
        colors = []
        
        for emotion, count in zip(emotions, counts):
            if count > 0:
                non_zero_emotions.append(emotion.split()[0])  # Только эмодзи
                non_zero_counts.append(count)
                colors.append(EMOTION_COLORS[emotion])
        
        if non_zero_counts:
            wedges, texts, autotexts = ax2.pie(non_zero_counts, 
                                               labels=non_zero_emotions,
                                               colors=colors,
                                               autopct='%1.0f%%',
                                               startangle=90,
                                               textprops={'fontsize': 12, 'fontweight': 'bold'})
            
            # Добавляем легенду
            legend_labels = [f"{emotion.split()[1]}: {count} раз" 
                           for emotion, count in zip(emotions, counts) if count > 0]
            ax2.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
            
            ax2.set_title('Распределение эмоций', fontsize=14, pad=20, fontweight='bold')
        
        # Общий заголовок
        fig.suptitle(f'📊 Анализ эмоционального состояния\n{start_date_str} - {end_date_str}', 
                    fontsize=16, fontweight='bold', y=1.05)
        
        plt.tight_layout()
        
        # Сохраняем
        filename = f'emotion_radar_{user_id}_{weeks_offset}.png'
        plt.savefig(filename, dpi=100, bbox_inches='tight', facecolor='white')
        plt.close()
        
        return filename
        
    except Exception as e:
        print(f"Ошибка при создании графика: {e}")
        return None

# Команда /report - показать радар эмоций
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wait_message = await update.message.reply_text("⏳ Создаю радар эмоций...")
    
    filename = await create_emotion_radar(user_id)
    
    if filename:
        with open(filename, 'rb') as photo:
            await update.message.reply_photo(
                photo,
                caption="✨ Твой эмоциональный радар за неделю!\n\n"
                        "📊 Лепестковая диаграмма показывает интенсивность каждой эмоции\n"
                        "🥧 Круговая диаграмма показывает распределение\n\n"
                        "Чем больше лепесток, тем чаще была эта эмоция!"
            )
        await wait_message.delete()
    else:
        await wait_message.edit_text(
            "😕 Недостаточно данных для графика.\n"
            "Отмечай настроение хотя бы 3 дня в неделю командой /checkin"
        )

def main():
    init_db()
    
    application = Application.builder().token(TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("report", report))  # Добавь из предыдущего кода
    application.add_handler(CommandHandler("reasons", show_reasons))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("export", export_data))
    application.add_handler(CommandHandler("reminder", reminder))
    application.add_handler(CommandHandler("off", turn_off_reminders))
    application.add_handler(CommandHandler("status", check_status))
    
    # Callback-обработчики
    application.add_handler(CallbackQueryHandler(reason_callback, pattern="^reason_"))
    application.add_handler(CallbackQueryHandler(reasons_callback, pattern="^reasons_"))
    application.add_handler(CallbackQueryHandler(reminder_callback, pattern="^remind_"))
    
    # Текстовые сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_time))
    
    # Запуск планировщика
    scheduler.start()
    
    # Восстановление напоминаний
    async def post_init(application):
        await restore_reminders(application.bot)
    
    application.post_init = post_init
    
    print("=" * 50)
    print("🤖 Бот с анализом причин запущен!")
    print("📝 Новые команды: /reasons, /export, /stats")
    print("=" * 50)
    
    application.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
        scheduler.shutdown()