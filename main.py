import os
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))


# -----------------------------
# НАСТРОЙКА БОТА
# -----------------------------

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# -----------------------------
# СОСТОЯНИЯ СОЗДАНИЯ АКТА
# -----------------------------

class InspectionForm(StatesGroup):
    make = State()
    model = State()
    year = State()
    vin = State()
    mileage = State()


# -----------------------------
# ГЛАВНОЕ МЕНЮ
# -----------------------------

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Создать акт")]
    ],
    resize_keyboard=True
)


# -----------------------------
# /START
# -----------------------------

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Добро пожаловать!\n\n"
        "Это бот для создания профессиональных "
        "фотоотчётов осмотра автомобилей.\n\n"
        "Нажмите кнопку «Создать акт», чтобы начать.",
        reply_markup=main_menu
    )


# -----------------------------
# СОЗДАНИЕ АКТА
# -----------------------------

@dp.message(lambda message: message.text == "Создать акт")
async def create_act(message: types.Message, state: FSMContext):
    await state.clear()

    await state.set_state(InspectionForm.make)

    await message.answer(
        "Создаём новый акт осмотра.\n\n"
        "Шаг 1 из 5\n\n"
        "Введите марку автомобиля:"
    )


# -----------------------------
# МАРКА
# -----------------------------

@dp.message(InspectionForm.make)
async def get_make(message: types.Message, state: FSMContext):
    make = message.text.strip()

    if not make:
        await message.answer("Пожалуйста, введите марку автомобиля.")
        return

    await state.update_data(make=make)
    await state.set_state(InspectionForm.model)

    await message.answer(
        "Шаг 2 из 5\n\n"
        "Введите модель автомобиля:"
    )


# -----------------------------
# МОДЕЛЬ
# -----------------------------

@dp.message(InspectionForm.model)
async def get_model(message: types.Message, state: FSMContext):
    model = message.text.strip()

    if not model:
        await message.answer("Пожалуйста, введите модель автомобиля.")
        return

    await state.update_data(model=model)
    await state.set_state(InspectionForm.year)

    await message.answer(
        "Шаг 3 из 5\n\n"
        "Введите год выпуска автомобиля:"
    )


# -----------------------------
# ГОД
# -----------------------------

@dp.message(InspectionForm.year)
async def get_year(message: types.Message, state: FSMContext):
    year_text = message.text.strip()

    if not year_text.isdigit():
        await message.answer(
            "Год должен состоять только из цифр.\n\n"
            "Например: 2021"
        )
        return

    year = int(year_text)

    if year < 1900 or year > 2100:
        await message.answer(
            "Введите корректный год.\n\n"
            "Например: 2021"
        )
        return

    await state.update_data(year=year)
    await state.set_state(InspectionForm.vin)

    await message.answer(
        "Шаг 4 из 5\n\n"
        "Введите VIN автомобиля:\n\n"
        "Например:\n"
        "WVWZZZ3CZWE123456"
    )


# -----------------------------
# VIN
# -----------------------------

@dp.message(InspectionForm.vin)
async def get_vin(message: types.Message, state: FSMContext):
    vin = message.text.strip().upper()

    if not vin:
        await message.answer("Пожалуйста, введите VIN автомобиля.")
        return

    if len(vin) != 17:
        await message.answer(
            "VIN обычно состоит из 17 символов.\n\n"
            "Пожалуйста, проверьте VIN и введите его ещё раз."
        )
        return

    await state.update_data(vin=vin)
    await state.set_state(InspectionForm.mileage)

    await message.answer(
        "Шаг 5 из 5\n\n"
        "Введите пробег автомобиля в километрах.\n\n"
        "Например: 125000"
    )


# -----------------------------
# ПРОБЕГ
# -----------------------------

@dp.message(InspectionForm.mileage)
async def get_mileage(message: types.Message, state: FSMContext):
    mileage_text = message.text.strip().replace(" ", "")

    if not mileage_text.isdigit():
        await message.answer(
            "Пробег должен состоять только из цифр.\n\n"
            "Например: 125000"
        )
        return

    mileage = int(mileage_text)

    if mileage < 0:
        await message.answer("Введите корректный пробег.")
        return

    await state.update_data(mileage=mileage)

    data = await state.get_data()

    await state.clear()

    await message.answer(
        "Данные автомобиля сохранены.\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "АКТ ОСМОТРА АВТОМОБИЛЯ\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"Марка: {data['make']}\n"
        f"Модель: {data['model']}\n"
        f"Год: {data['year']}\n"
        f"VIN: {data['vin']}\n"
        f"Пробег: {data['mileage']:,} км".replace(",", " ")
        + "\n\n"
        "Следующим этапом добавим фотографии автомобиля."
    )

    await message.answer(
        "Нажмите «Создать акт», чтобы создать новый акт.",
        reply_markup=main_menu
    )


# -----------------------------
# WEB-СЕРВЕР ДЛЯ RENDER
# -----------------------------

async def health(request):
    return web.Response(text="OK")


async def run_web_server():
    app = web.Application()

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    print(f"Web server started on port {PORT}")

    return runner


# -----------------------------
# ЗАПУСК
# -----------------------------

async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не найден")

    bot = Bot(token=TOKEN)

    runner = await run_web_server()

    try:
        print("Telegram bot started")

        await dp.start_polling(bot)

    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
