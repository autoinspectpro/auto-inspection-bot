import os
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Добро пожаловать!\n\n"
        "Это бот для создания фотоотчётов осмотра автомобилей.\n\n"
        "Нажмите «Создать акт», чтобы начать."
    )


async def main():
    if not TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN")

    bot = Bot(token=TOKEN)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
