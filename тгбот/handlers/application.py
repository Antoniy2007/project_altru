from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
import sqlite3

router = Router()

# States для FSM
class ProblemReport(StatesGroup):
    choosing_problem_type = State()
    choosing_district = State()
    providing_details = State()
    providing_photo = State()

class Feedback(StatesGroup):
    waiting_for_rating = State()
    waiting_for_comment = State()

# Сценарий 1: Подача заявки
@router.message(ProblemReport.choosing_problem_type, F.text)
async def problem_type_chosen(message: types.Message, state: FSMContext):
    await state.update_data(problem_type=message.text)
    
    # Получаем язык пользователя
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user_lang = cur.fetchone()[0]
    conn.close()
    
    # Запрашиваем район
    if user_lang == 'ru':
        text = "Пожалуйста, укажите ваш район Москвы:"
        kb = [
            [types.KeyboardButton(text="Отправить местоположение 📍", request_location=True)],
            [types.KeyboardButton(text="ЦАО"), types.KeyboardButton(text="САО")],
            [types.KeyboardButton(text="СВАО"), types.KeyboardButton(text="ВАО")],
            [types.KeyboardButton(text="ЮВАО"), types.KeyboardButton(text="ЮАО")],
            [types.KeyboardButton(text="ЮЗАО"), types.KeyboardButton(text="ЗАО")],
            [types.KeyboardButton(text="СЗАО"), types.KeyboardButton(text="Троицкий")],
            [types.KeyboardButton(text="Новомосковский"), types.KeyboardButton(text="Другой")]
        ]
    else:
        text = "Please specify your Moscow district:"
        kb = [
            [types.KeyboardButton(text="Send location 📍", request_location=True)],
            [types.KeyboardButton(text="Central"), types.KeyboardButton(text="North")],
            [types.KeyboardButton(text="North-East"), types.KeyboardButton(text="East")],
            [types.KeyboardButton(text="South-East"), types.KeyboardButton(text="South")],
            [types.KeyboardButton(text="South-West"), types.KeyboardButton(text="West")],
            [types.KeyboardButton(text="North-West"), types.KeyboardButton(text="Troitsky")],
            [types.KeyboardButton(text="Novomoskovsky"), types.KeyboardButton(text="Other")]
        ]
    
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(ProblemReport.choosing_district)

@router.message(ProblemReport.choosing_district, F.location)
async def district_from_location(message: types.Message, state: FSMContext):
    # В реальном приложении здесь бы было преобразование координат в район
    # Для прототипа используем приблизительное определение
    district = "Определено по геолокации"
    await state.update_data(district=district)
    await ask_for_details(message, state)

@router.message(ProblemReport.choosing_district, F.text)
async def district_from_text(message: types.Message, state: FSMContext):
    await state.update_data(district=message.text)
    await ask_for_details(message, state)

async def ask_for_details(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    problem_type = user_data['problem_type']
    
    # Получаем язык пользователя
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user_lang = cur.fetchone()[0]
    conn.close()
    
    # Формируем вопрос в зависимости от типа проблемы
    details_questions = {
        "Настройка звука": "Опишите проблему со звуком подробнее:",
        "Установка приложений": "Какое приложение необходимо установить?",
        "Проблемы с интернетом": "Опишите проблему с интернетом:",
        "Синхронизация устройств": "Какие устройства нужно синхронизировать?",
        "Другое": "Опишите вашу проблему:",
        "Audio Setup": "Please describe the audio issue in detail:",
        "App Installation": "Which application needs to be installed?",
        "Internet Issues": "Please describe the internet issue:",
        "Device Sync": "Which devices need to be synchronized?",
        "Other": "Please describe your problem:"
    }
    
    question = details_questions.get(problem_type, details_questions["Другое" if user_lang == 'ru' else "Other"])
    
    if user_lang == 'ru':
        skip_text = "Пропустить"
    else:
        skip_text = "Skip"
    
    kb = [[types.KeyboardButton(text=skip_text)]]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer(question, reply_markup=keyboard)
    await state.set_state(ProblemReport.providing_details)

# Сценарий 2: Уточнение деталей
@router.message(ProblemReport.providing_details, F.text)
async def details_provided(message: types.Message, state: FSMContext):
    # Получаем язык пользователя
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user_lang = cur.fetchone()[0]
    conn.close()
    
    skip_text = "Пропустить" if user_lang == 'ru' else "Skip"
    
    if message.text != skip_text:
        await state.update_data(details=message.text)
    
    if user_lang == 'ru':
        text = "Вы можете прикрепить скриншот проблемы или продолжить без него:"
        kb = [[types.KeyboardButton(text="Продолжить без фото")]]
    else:
        text = "You can attach a screenshot of the problem or continue without it:"
        kb = [[types.KeyboardButton(text="Continue without photo")]]
    
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(ProblemReport.providing_photo)

@router.message(ProblemReport.providing_photo, F.photo)
async def photo_provided(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await save_application(message, state)

@router.message(ProblemReport.providing_photo, F.text)
async def no_photo_provided(message: types.Message, state: FSMContext):
    # Получаем язык пользователя
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user_lang = cur.fetchone()[0]
    conn.close()
    
    continue_text = "Продолжить без фото" if user_lang == 'ru' else "Continue without photo"
    
    if message.text == continue_text:
        await save_application(message, state)

async def save_application(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    
    # Получаем язык пользователя
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT id, language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user_id, user_lang = cur.fetchone()
    
    # Сохраняем заявку в БД
    cur.execute('''
        INSERT INTO requests 
        (user_id, problem_type, district, details, photo_id, status) 
        VALUES (?, ?, ?, ?, ?, 'new')
    ''', (
        user_id,
        user_data.get('problem_type'),
        user_data.get('district'),
        user_data.get('details'),
        user_data.get('photo_id')
    ))
    conn.commit()
    conn.close()
    
    # Подтверждение пользователю
    if user_lang == 'ru':
        text = "✅ Ваша заявка принята! Ожидайте связи волонтера."
    else:
        text = "✅ Your application has been submitted! Please wait for a volunteer to contact you."
    
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.clear()

    # Здесь бы отправлялось уведомление волонтерам
    # notify_volunteers(user_data)

# Сценарий 3: Подтверждение выполнения (имитация)
@router.message(Command("complete"))
async def cmd_complete(message: types.Message, state: FSMContext):
    # В реальном приложении эта команда была бы доступна только волонтерам
    # и принимала бы ID заявки. Здесь имитируем завершение.
    
    # Получаем язык пользователя
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user_lang = cur.fetchone()[0]
    conn.close()
    
    if user_lang == 'ru':
        text = "Пожалуйста, оцените помощь волонтера по шкале от 1 до 5:"
        kb = [
            [types.KeyboardButton(text="1"), types.KeyboardButton(text="2"), types.KeyboardButton(text="3")],
            [types.KeyboardButton(text="4"), types.KeyboardButton(text="5")]
        ]
    else:
        text = "Please rate the volunteer's help on a scale from 1 to 5:"
        kb = [
            [types.KeyboardButton(text="1"), types.KeyboardButton(text="2"), types.KeyboardButton(text="3")],
            [types.KeyboardButton(text="4"), types.KeyboardButton(text="5")]
        ]
    
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(Feedback.waiting_for_rating)

@router.message(Feedback.waiting_for_rating, F.text.in_(["1", "2", "3", "4", "5"]))
async def rating_received(message: types.Message, state: FSMContext):
    await state.update_data(rating=int(message.text))
    
    # Получаем язык пользователя
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user_lang = cur.fetchone()[0]
    conn.close()
    
    if user_lang == 'ru':
        text = "Спасибо! Хотите оставить комментарий?"
        kb = [[types.KeyboardButton(text="Пропустить")]]
    else:
        text = "Thank you! Would you like to leave a comment?"
        kb = [[types.KeyboardButton(text="Skip")]]
    
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(Feedback.waiting_for_comment)

@router.message(Feedback.waiting_for_comment, F.text)
async def comment_received(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    rating = user_data['rating']
    
    # Получаем язык пользователя
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT language FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user_lang = cur.fetchone()[0]
    conn.close()
    
    skip_text = "Пропустить" if user_lang == 'ru' else "Skip"
    
    if message.text != skip_text:
        await state.update_data(comment=message.text)
        user_data = await state.get_data()
    
    # Здесь бы обновлялась заявка в БД и фиксировались волонтерские часы
    # update_application_in_db(message.from_user.id, rating, user_data.get('comment'))
    
    if user_lang == 'ru':
        text = "✅ Спасибо за вашу обратную связь! Волонтерские часы зафиксированы."
    else:
        text = "✅ Thank you for your feedback! Volunteer hours have been recorded."
    
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.clear()