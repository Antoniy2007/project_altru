from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import sqlite3

router = Router()

class LanguageChoose(StatesGroup):
    choosing_language = State()

# Команда /start
@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    # Проверяем, есть ли пользователь в БД
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user = cur.fetchone()
    
    if not user:
        # Новый пользователь - предлагаем выбрать язык
        kb = [
            [types.KeyboardButton(text="Русский 🇷🇺"), types.KeyboardButton(text="English 🇺🇸")]
        ]
        keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer(
            "Добро пожаловать! Пожалуйста, выберите язык / Welcome! Please choose your language:",
            reply_markup=keyboard
        )
        await state.set_state(LanguageChoose.choosing_language)
    else:
        # Существующий пользователь
        from handlers.application import ProblemReport
        await state.set_state(ProblemReport.choosing_problem_type)
        await show_problem_types(message, user[2])  # user[2] - язык
    
    conn.close()

@router.message(LanguageChoose.choosing_language, F.text.in_(["Русский 🇷🇺", "English 🇺🇸"]))
async def language_chosen(message: types.Message, state: FSMContext):
    lang = "ru" if message.text == "Русский 🇷🇺" else "en"
    
    # Сохраняем пользователя в БД
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO users (telegram_id, language) VALUES (?, ?)",
        (message.from_user.id, lang)
    )
    conn.commit()
    conn.close()
    
    # Переходим к выбору типа проблемы
    from handlers.application import ProblemReport
    await state.set_state(ProblemReport.choosing_problem_type)
    await show_problem_types(message, lang)

async def show_problem_types(message: types.Message, lang: str):
    if lang == 'ru':
        text = "Пожалуйста, выберите тип проблемы:"
        problem_types = [
            "Настройка звука",
            "Установка приложений", 
            "Проблемы с интернетом",
            "Синхронизация устройств",
            "Другое"
        ]
    else:
        text = "Please choose the problem type:"
        problem_types = [
            "Audio Setup",
            "App Installation",
            "Internet Issues", 
            "Device Sync",
            "Other"
        ]
    
    kb = [[types.KeyboardButton(text=pt)] for pt in problem_types]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(text, reply_markup=keyboard)