```python
import os
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart


TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Добро пожаловать!\n\n"
        "Это бот для создания фотоотчётов осмотра автомобилей.\n\n"
        "Скоро здесь можно будет создать профессиональный фотоотчёт "
        "по автомобилю."
    )


async def health(request):
    return web.Response(text="OK")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print(f"Web server started on port {PORT}")

    return runner


async def main():
    if not TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN")

    bot = Bot(token=TOKEN)

    runner = await start_web_server()

    try:
        print("Telegram bot started")
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
```
