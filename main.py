import os
import asyncio
from io import BytesIO

from aiohttp import web
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ==========================================
# СОСТОЯНИЯ
# ==========================================

class InspectionForm(StatesGroup):
    make = State()
    model = State()
    year = State()
    vin = State()
    mileage = State()
    lkp = State()


# ==========================================
# МЕНЮ
# ==========================================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Создать акт")]
    ],
    resize_keyboard=True
)


# ==========================================
# ДЕТАЛИ ДЛЯ ИЗМЕРЕНИЯ ЛКП
# ==========================================

LKP_PARTS = [
    ("Капот", "hood"),
    ("Крыша", "roof"),
    ("Крышка багажника", "trunk"),

    ("Переднее левое крыло", "fl_fender"),
    ("Передняя левая дверь", "fl_door"),
    ("Задняя левая дверь", "rl_door"),
    ("Заднее левое крыло", "rl_fender"),

    ("Переднее правое крыло", "fr_fender"),
    ("Передняя правая дверь", "fr_door"),
    ("Задняя правая дверь", "rr_door"),
    ("Заднее правое крыло", "rr_fender"),
]


# ==========================================
# ШРИФТЫ
# ==========================================

def get_font(size, bold=False):
    possible_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",

        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]

    for path in possible_fonts:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# ==========================================
# ГРАФИКА АВТОМОБИЛЯ
# ==========================================

def draw_arrow(draw, start, end, width=3):
    draw.line(
        [start, end],
        fill=(45, 45, 50),
        width=width
    )

    x1, y1 = start
    x2, y2 = end

    dx = x2 - x1
    dy = y2 - y1

    length = max((dx * dx + dy * dy) ** 0.5, 1)

    ux = dx / length
    uy = dy / length

    size = 10

    p1 = (
        x2 - ux * size - uy * size * 0.5,
        y2 - uy * size + ux * size * 0.5
    )

    p2 = (
        x2 - ux * size + uy * size * 0.5,
        y2 - uy * size - ux * size * 0.5
    )

    draw.polygon(
        [(x2, y2), p1, p2],
        fill=(45, 45, 50)
    )


def make_lkp_report(car_data, measurements):
    width = 1600
    height = 2200

    image = Image.new(
        "RGB",
        (width, height),
        (247, 247, 245)
    )

    draw = ImageDraw.Draw(image)

    title_font = get_font(58, True)
    subtitle_font = get_font(32, False)
    section_font = get_font(36, True)
    label_font = get_font(25, True)
    value_font = get_font(28, True)
    small_font = get_font(23, False)

    # ======================================
    # ШАПКА
    # ======================================

    draw.rectangle(
        [0, 0, width, 190],
        fill=(22, 24, 27)
    )

    draw.text(
        (70, 38),
        "ЮРМАКС",
        font=title_font,
        fill=(255, 255, 255)
    )

    draw.text(
        (70, 112),
        "АКТ ОСМОТРА АВТОМОБИЛЯ",
        font=subtitle_font,
        fill=(205, 205, 205)
    )

    # ======================================
    # ДАННЫЕ АВТОМОБИЛЯ
    # ======================================

    y = 235

    draw.text(
        (70, y),
        "КАРТА ЛАКОКРАСОЧНОГО ПОКРЫТИЯ",
        font=section_font,
        fill=(25, 25, 28)
    )

    y += 65

    info = [
        f"Автомобиль: {car_data['make']} {car_data['model']}",
        f"Год выпуска: {car_data['year']}",
        f"VIN: {car_data['vin']}",
        f"Пробег: {car_data['mileage']:,} км".replace(",", " "),
    ]

    x_positions = [70, 800]

    for index, text in enumerate(info):
        col = index % 2
        row = index // 2

        x = x_positions[col]
        yy = y + row * 55

        draw.text(
            (x, yy),
            text,
            font=small_font,
            fill=(65, 65, 70)
        )

    # ======================================
    # ОБЛАСТЬ АВТОМОБИЛЯ
    # ======================================

    car_left = 560
    car_right = 1040
    car_top = 570
    car_bottom = 1590

    # тень
    draw.rounded_rectangle(
        [car_left + 12, car_top + 12,
         car_right + 12, car_bottom + 12],
        radius=150,
        fill=(220, 220, 218)
    )

    # кузов
    draw.rounded_rectangle(
        [car_left, car_top, car_right, car_bottom],
        radius=150,
        fill=(225, 227, 230),
        outline=(70, 72, 76),
        width=5
    )

    # капот
    draw.rounded_rectangle(
        [car_left + 45, car_top + 45,
         car_right - 45, car_top + 300],
        radius=70,
        fill=(205, 208, 212),
        outline=(100, 102, 106),
        width=3
    )

    # багажник
    draw.rounded_rectangle(
        [car_left + 45, car_bottom - 300,
         car_right - 45, car_bottom - 45],
        radius=70,
        fill=(205, 208, 212),
        outline=(100, 102, 106),
        width=3
    )

    # салон
    draw.rounded_rectangle(
        [car_left + 75, car_top + 300,
         car_right - 75, car_bottom - 300],
        radius=95,
        fill=(48, 51, 55),
        outline=(80, 82, 85),
        width=4
    )

    # переднее стекло
    draw.polygon(
        [
            (car_left + 105, car_top + 325),
            (car_right - 105, car_top + 325),
            (car_right - 125, car_top + 490),
            (car_left + 125, car_top + 490),
        ],
        fill=(115, 132, 145)
    )

    # заднее стекло
    draw.polygon(
        [
            (car_left + 125, car_bottom - 490),
            (car_right - 125, car_bottom - 490),
            (car_right - 105, car_bottom - 325),
            (car_left + 105, car_bottom - 325),
        ],
        fill=(115, 132, 145)
    )

    # центральная линия
    draw.line(
        [
            ((car_left + car_right) // 2, car_top + 500),
            ((car_left + car_right) // 2, car_bottom - 500)
        ],
        fill=(105, 107, 111),
        width=3
    )

    # колёса
    wheel_positions = [
        (car_left - 25, car_top + 355),
        (car_right - 5, car_top + 355),
        (car_left - 25, car_bottom - 355),
        (car_right - 5, car_bottom - 355),
    ]

    for wx, wy in wheel_positions:
        draw.rounded_rectangle(
            [wx, wy, wx + 30, wy + 155],
            radius=14,
            fill=(30, 31, 33)
        )

    # ======================================
    # ПОДПИСИ ДЕТАЛЕЙ И СТРЕЛКИ
    # ======================================

    label_positions = {
        "hood": (80, 640),
        "roof": (80, 880),
        "trunk": (80, 1270),

        "fl_fender": (80, 730),
        "fl_door": (80, 1030),
        "rl_door": (80, 1150),
        "rl_fender": (80, 1370),

        "fr_fender": (1110, 730),
        "fr_door": (1110, 1030),
        "rr_door": (1110, 1150),
        "rr_fender": (1110, 1370),
    }

    arrow_targets = {
        "hood": (650, 680),
        "roof": (800, 900),
        "trunk": (650, 1490),

        "fl_fender": (570, 780),
        "fl_door": (590, 1050),
        "rl_door": (590, 1180),
        "rl_fender": (570, 1350),

        "fr_fender": (1030, 780),
        "fr_door": (1010, 1050),
        "rr_door": (1010, 1180),
        "rr_fender": (1030, 1350),
    }

    part_names = {key: name for name, key in LKP_PARTS}

    for key, (x, yy) in label_positions.items():

        value = measurements.get(key, "—")

        box_w = 390
        box_h = 82

        draw.rounded_rectangle(
            [x, yy, x + box_w, yy + box_h],
            radius=14,
            fill=(255, 255, 255),
            outline=(195, 196, 198),
            width=2
        )

        draw.text(
            (x + 18, yy + 12),
            part_names[key],
            font=label_font,
            fill=(35, 35, 38)
        )

        draw.text(
            (x + box_w - 105, yy + 13),
            f"{value} мкм",
            font=value_font,
            fill=(25, 25, 28)
        )

        target = arrow_targets[key]

        if x < car_left:
            start = (x + box_w, yy + box_h // 2)
        else:
            start = (x, yy + box_h // 2)

        draw_arrow(draw, start, target)

    # ======================================
    # ЛЕГЕНДА
    # ======================================

    legend_y = 1690

    draw.line(
        [(70, legend_y), (1530, legend_y)],
        fill=(205, 205, 205),
        width=2
    )

    draw.text(
        (70, legend_y + 35),
        "ЛКП измеряется в микрометрах (мкм)",
        font=small_font,
        fill=(70, 70, 75)
    )

    draw.text(
        (70, legend_y + 85),
        "Значения указаны по результатам фактических измерений.",
        font=small_font,
        fill=(100, 100, 105)
    )

    draw.text(
        (70, 1990),
        "ЮРМАКС",
        font=section_font,
        fill=(35, 36, 39)
    )

    draw.text(
        (70, 2045),
        "Карта ЛКП • Акт осмотра автомобиля",
        font=small_font,
        fill=(100, 100, 105)
    )

    output = BytesIO()

    image.save(
        output,
        format="PNG",
        optimize=True
    )

    output.seek(0)

    return output


# ==========================================
# START
# ==========================================

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Добро пожаловать!\n\n"
        "ЮРМАКС — создание фотоотчётов осмотра автомобилей.\n\n"
        "Нажмите «Создать акт», чтобы начать.",
        reply_markup=main_menu
    )


# ==========================================
# СОЗДАТЬ АКТ
# ==========================================

@dp.message(lambda message: message.text == "Создать акт")
async def create_act(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(InspectionForm.make)

    await message.answer(
        "Создаём новый акт осмотра.\n\n"
        "Шаг 1 из 5\n\n"
        "Введите марку автомобиля:"
    )


# ==========================================
# МАРКА
# ==========================================

@dp.message(InspectionForm.make)
async def get_make(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()

    if not text:
        await message.answer("Введите марку автомобиля.")
        return

    await state.update_data(make=text)
    await state.set_state(InspectionForm.model)

    await message.answer(
        "Шаг 2 из 5\n\n"
        "Введите модель автомобиля:"
    )


# ==========================================
# МОДЕЛЬ
# ==========================================

@dp.message(InspectionForm.model)
async def get_model(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()

    if not text:
        await message.answer("Введите модель автомобиля.")
        return

    await state.update_data(model=text)
    await state.set_state(InspectionForm.year)

    await message.answer(
        "Шаг 3 из 5\n\n"
        "Введите год выпуска:"
    )


# ==========================================
# ГОД
# ==========================================

@dp.message(InspectionForm.year)
async def get_year(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()

    if not text.isdigit():
        await message.answer("Введите год цифрами, например: 2021")
        return

    year = int(text)

    if year < 1900 or year > 2100:
        await message.answer("Введите корректный год.")
        return

    await state.update_data(year=year)
    await state.set_state(InspectionForm.vin)

    await message.answer(
        "Шаг 4 из 5\n\n"
        "Введите VIN автомобиля:"
    )


# ==========================================
# VIN
# ==========================================

@dp.message(InspectionForm.vin)
async def get_vin(message: types.Message, state: FSMContext):
    vin = (message.text or "").strip().upper()

    if len(vin) != 17:
        await message.answer(
            "VIN должен содержать 17 символов.\n"
            "Проверьте VIN и отправьте его ещё раз."
        )
        return

    await state.update_data(vin=vin)
    await state.set_state(InspectionForm.mileage)

    await message.answer(
        "Шаг 5 из 5\n\n"
        "Введите пробег в километрах.\n\n"
        "Например: 125000"
    )


# ==========================================
# ПРОБЕГ
# ==========================================

@dp.message(InspectionForm.mileage)
async def get_mileage(message: types.Message, state: FSMContext):
    text = (message.text or "").strip().replace(" ", "")

    if not text.isdigit():
        await message.answer(
            "Введите пробег цифрами.\n"
            "Например: 125000"
        )
        return

    mileage = int(text)

    await state.update_data(mileage=mileage)

    data = await state.get_data()

    await state.set_state(InspectionForm.lkp)

    await state.update_data(
        lkp_index=0,
        measurements={}
    )

    first_part = LKP_PARTS[0][0]

    await message.answer(
        "Данные автомобиля сохранены.\n\n"
        "Теперь заполним карту ЛКП.\n\n"
        f"Измерьте деталь:\n"
        f"{first_part}\n\n"
        "Введите значение в мкм.\n"
        "Например: 145"
    )


# ==========================================
# ЛКП
# ==========================================

@dp.message(InspectionForm.lkp)
async def get_lkp(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()

    if not text.isdigit():
        await message.answer(
            "Введите значение ЛКП только цифрами.\n\n"
            "Например: 145"
        )
        return

    value = int(text)

    if value < 1 or value > 5000:
        await message.answer(
            "Введите значение от 1 до 5000 мкм."
        )
        return

    data = await state.get_data()

    index = data.get("lkp_index", 0)
    measurements = data.get("measurements", {})

    part_name, part_key = LKP_PARTS[index]

    measurements[part_key] = value

    next_index = index + 1

    if next_index < len(LKP_PARTS):
        await state.update_data(
            lkp_index=next_index,
            measurements=measurements
        )

        next_part = LKP_PARTS[next_index][0]

        await message.answer(
            f"Сохранено: {part_name} — {value} мкм\n\n"
            f"Следующая деталь:\n"
            f"{next_part}\n\n"
            "Введите значение в мкм:"
        )

        return

    # ======================================
    # ВСЕ ИЗМЕРЕНИЯ ГОТОВЫ
    # ======================================

    car_data = {
        "make": data["make"],
        "model": data["model"],
        "year": data["year"],
        "vin": data["vin"],
        "mileage": data["mileage"],
    }

    await message.answer(
        "Все значения ЛКП получены.\n\n"
        "Формирую графическую карту ЮРМАКС..."
    )

    report = make_lkp_report(
        car_data,
        measurements
    )

    await message.answer_photo(
        types.BufferedInputFile(
            report.read(),
            filename="yurmax_lkp_map.png"
        ),
        caption=(
            "ЮРМАКС\n"
            "Карта лакокрасочного покрытия\n\n"
            "Значения нанесены по введённым результатам измерений."
        )
    )

    await state.clear()

    await message.answer(
        "Карта ЛКП готова.\n\n"
        "Следующим этапом можем добавить загрузку фотографий автомобиля "
        "и собрать из карты ЛКП + фотографий полноценный многостраничный "
        "фотоотчёт.",
        reply_markup=main_menu
    )


# ==========================================
# WEB-СЕРВЕР RENDER
# ==========================================

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


# ==========================================
# ЗАПУСК
# ==========================================

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
    
