import os
import asyncio
import base64
import json
from io import BytesIO
from datetime import datetime

from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from PIL import Image, ImageDraw, ImageFont

from openai import AsyncOpenAI

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image as RLImage,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# =========================================================
# SETTINGS
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Можно поменять модель через Render Environment.
# По умолчанию используется экономичная vision-модель.
OPENAI_MODEL = os.getenv(
    "OPENAI_VISION_MODEL",
    "gpt-5.6-luna"
)

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")


# =========================================================
# BOT / OPENAI
# =========================================================

bot = Bot(TOKEN)

dp = Dispatcher()

openai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY
)


# =========================================================
# STATES
# =========================================================

class InspectionForm(StatesGroup):

    # Master
    master_name = State()
    report_date = State()

    # Car
    make = State()
    model = State()
    year = State()
    vin = State()
    mileage = State()

    # Engine
    engine_type = State()
    engine_volume = State()
    engine_hp = State()
    gearbox = State()

    # LKP
    lkp = State()

    # Photos
    photos = State()


# =========================================================
# KEYBOARDS
# =========================================================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Создать акт")
        ]
    ],
    resize_keyboard=True
)


engine_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Бензин"),
            KeyboardButton(text="Дизель")
        ],
        [
            KeyboardButton(text="Гибрид"),
            KeyboardButton(text="Электро")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


gearbox_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="МКПП"),
            KeyboardButton(text="АКПП")
        ],
        [
            KeyboardButton(text="Робот"),
            KeyboardButton(text="Вариатор")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


finish_photos_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Готово")
        ]
    ],
    resize_keyboard=True
)


# =========================================================
# LKP PARTS
# =========================================================

LKP_PARTS = [
    "Капот",
    "Крыша",
    "Крышка багажника",
    "Переднее левое крыло",
    "Передняя левая дверь",
    "Задняя левая дверь",
    "Заднее левое крыло",
    "Переднее правое крыло",
    "Передняя правая дверь",
    "Задняя правая дверь",
    "Заднее правое крыло",
]


# =========================================================
# EQUIPMENT
# =========================================================

EQUIPMENT = {

    "ЭКСТЕРЬЕР": [

        "Тип кузова",
        "Цвет кузова",
        "Тип лакокрасочного покрытия",

        "LED-фары",
        "Ксеноновые фары",
        "Галогенные фары",
        "Матричные фары",
        "Дневные ходовые огни",
        "Автоматический дальний свет",
        "Противотуманные фары",
        "Омыватели фар",
        "Датчик света",
        "Датчик дождя",

        "Электрорегулировка зеркал",
        "Обогрев зеркал",
        "Электроскладывание зеркал",
        "Автозатемнение зеркала",
        "Повторители поворотов в зеркалах",

        "Панорамная крыша",
        "Люк",
        "Рейлинги",
        "Спойлер",
        "Хромированные элементы",
        "Спортивный обвес",

        "Размер колёс",
        "Тип дисков",
        "Электропривод крышки багажника",
    ],

    "ИНТЕРЬЕР": [

        "Материал сидений",
        "Цвет салона",
        "Кожаный салон",
        "Комбинированный салон",
        "Тканевый салон",

        "Спортивные сиденья",
        "Электрорегулировка сидений",
        "Память сиденья",
        "Подогрев передних сидений",
        "Подогрев задних сидений",
        "Вентиляция сидений",
        "Массаж сидений",

        "Электрорегулировка руля",
        "Подогрев руля",
        "Мультируль",
        "Подрулевые лепестки",

        "Цифровая приборная панель",
        "HUD",
        "Амбиентная подсветка",
        "Электрохромное зеркало",
        "Солнцезащитные шторки",
        "Центральный подлокотник",
        "Декоративные вставки",
        "Количество мест",
    ],

    "КОМФОРТ": [

        "Кондиционер",
        "Климат-контроль",
        "Двухзонный климат",
        "Трёхзонный климат",
        "Автономный отопитель",

        "Бесключевой доступ",
        "Запуск двигателя кнопкой",
        "Дистанционный запуск",

        "Круиз-контроль",
        "Адаптивный круиз-контроль",

        "Электропривод окон",
        "Электропривод багажника",
        "Доводчики дверей",
        "Центральный замок",
        "Автоматическое запирание дверей",

        "Подогрев лобового стекла",
        "Подогрев форсунок омывателя",
        "Обогрев заднего стекла",

        "Беспроводная зарядка",
        "USB-разъёмы",
        "12V-разъём",

        "Бесконтактное открытие багажника",
        "Автоматическая парковка",
        "Режимы движения",
        "Электрический ручник",
        "Auto Hold",
    ],

    "МУЛЬТИМЕДИА": [

        "Центральный дисплей",
        "Размер дисплея",
        "Сенсорный экран",
        "Цифровая приборная панель",

        "Навигация",
        "Bluetooth",
        "Apple CarPlay",
        "Android Auto",
        "Беспроводной CarPlay",

        "USB / USB-C",
        "Голосовое управление",
        "Интернет-сервисы",

        "Радио",
        "DAB",

        "Штатная аудиосистема",
        "Премиальная аудиосистема",
        "Название аудиосистемы",
        "Количество динамиков",
        "Сабвуфер",
        "Усилитель",

        "Мультимедиа для задних пассажиров",
        "Дополнительные экраны",
    ],

    "БЕЗОПАСНОСТЬ": [

        "Передние подушки безопасности",
        "Боковые подушки безопасности",
        "Шторки безопасности",
        "Коленная подушка безопасности",

        "ABS",
        "ESP / ESC",
        "Traction Control",

        "Камера заднего вида",
        "Камеры 360°",

        "Передние парктроники",
        "Задние парктроники",

        "Контроль слепых зон",
        "Предупреждение о столкновении",
        "Автоматическое экстренное торможение",

        "Контроль полосы движения",
        "Удержание в полосе",
        "Распознавание дорожных знаков",
        "Адаптивный дальний свет",

        "Мониторинг усталости водителя",
        "Контроль давления в шинах",
        "Ассистент парковки",
        "Ассистент движения в пробке",
        "Адаптивный круиз",
        "Предупреждение при выезде с парковки",

        "ISOFIX",
        "Иммобилайзер",
        "Сигнализация",
    ],

    "ДОПОЛНИТЕЛЬНЫЕ ОПЦИИ": [

        "Webasto / автономный отопитель",
        "Фаркоп",
        "Электрический фаркоп",
        "Розетка 220V",

        "Дополнительная шумоизоляция",
        "Спортивный пакет",
        "M / AMG / S-line / RS-пакет",

        "Заводской декоративный пакет",
        "Дополнительное освещение",
        "Защитные элементы кузова",

        "Оригинальные аксессуары",
        "Дополнительные камеры",
        "Дополнительные датчики",

        "Доработанная аудиосистема",
        "Другое оборудование",
    ],
}


# =========================================================
# OPENAI STRUCTURED OUTPUT SCHEMA
# =========================================================

EQUIPMENT_AI_SCHEMA = {

    "type": "object",

    "additionalProperties": False,

    "properties": {

        "confirmed": {

            "type": "array",

            "items": {

                "type": "object",

                "additionalProperties": False,

                "properties": {

                    "category": {
                        "type": "string"
                    },

                    "option": {
                        "type": "string"
                    },

                    "value": {
                        "type": "string"
                    },

                    "evidence": {
                        "type": "string"
                    }
                },

                "required": [
                    "category",
                    "option",
                    "value",
                    "evidence"
                ]
            }
        }
    },

    "required": [
        "confirmed"
    ]
}


# =========================================================
# AI HELPERS
# =========================================================

def prepare_ai_image(path):

    """
    Уменьшаем фотографию перед отправкой в AI,
    чтобы не отправлять огромные оригиналы.
    """

    img = Image.open(path)

    img = img.convert("RGB")

    max_size = 1600

    img.thumbnail(
        (max_size, max_size),
        Image.Resampling.LANCZOS
    )

    output = BytesIO()

    img.save(
        output,
        format="JPEG",
        quality=82,
        optimize=True
    )

    output.seek(0)

    encoded = base64.b64encode(
        output.read()
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


def build_equipment_prompt(car_data):

    equipment_lines = []

    for category, options in EQUIPMENT.items():

        equipment_lines.append(
            f"\n{category}:"
        )

        for option in options:

            equipment_lines.append(
                f"- {option}"
            )

    equipment_text = "\n".join(
        equipment_lines
    )

    return f"""
Ты являешься AI-модулем визуального анализа
для профессионального отчёта осмотра автомобиля
системы ЮРМАКС.

Твоя задача — анализировать предоставленные фотографии
автомобиля и определять ТОЛЬКО оборудование,
которое действительно можно подтвердить визуально.

Данные автомобиля:

Марка: {car_data["make"]}
Модель: {car_data["model"]}
Год: {car_data["year"]}
Тип двигателя: {car_data["engine_type"]}
Объём: {car_data["engine_volume"]} л
Коробка: {car_data["gearbox"]}

СПИСОК ДОСТУПНЫХ ПУНКТОВ:

{equipment_text}

КРИТИЧЕСКИЕ ПРАВИЛА:

1. Никогда не угадывай комплектацию по марке,
   модели, году или типичной комплектации.

2. Не используй интернет-знания о конкретной модели
   для утверждения наличия оборудования.

3. Возвращай пункт только тогда, когда оборудование
   реально видно на предоставленной фотографии.

4. Если оборудование можно предположить,
   но оно не видно достаточно хорошо — НЕ возвращай его.

5. Если невозможно определить пункт по фотографиям —
   НЕ возвращай его.

6. Отсутствие пункта в результате НЕ означает,
   что его нет на автомобиле.

7. Для пункта "Цвет кузова" можно указать
   визуально определяемый цвет.

8. Для "Тип кузова" можно указать визуально
   определяемый тип кузова.

9. Для "Материал сидений" можно указать материал,
   если он хорошо виден.

10. Для "Размер дисплея", "Количество динамиков",
    "Название аудиосистемы" и подобных параметров
    не придумывай цифры или названия.
    Возвращай их только если они явно видны
    на фото или непосредственно указаны на элементе.

11. Для бинарного оборудования используй value:
    "Есть".

12. Для описательного оборудования используй
    конкретное визуальное значение.

13. evidence должно кратко объяснять,
    что именно видно на фотографии.

14. Если на фотографии видна только часть автомобиля,
    анализируй только эту часть.

15. Не определяй технические характеристики,
    которые невозможно установить визуально.

16. Не определяй ABS, ESP, подушки, иммобилайзер,
    сигнализацию и другие скрытые системы только
    по внешнему виду. Их можно подтверждать только
    если есть явный визуальный признак,
    например соответствующая кнопка, экран,
    маркировка или элемент системы.

17. Не возвращай одинаковые пункты несколько раз.

Верни только подтверждённые пункты.
"""


async def analyze_equipment_batch(
    image_data_urls,
    car_data
):

    content = [

        {
            "type": "input_text",
            "text": build_equipment_prompt(
                car_data
            )
        }
    ]

    for image_url in image_data_urls:

        content.append(
            {
                "type": "input_image",
                "image_url": image_url
            }
        )

    response = await openai_client.responses.create(

        model=OPENAI_MODEL,

        input=[
            {
                "role": "user",
                "content": content
            }
        ],

        text={
            "format": {
                "type": "json_schema",
                "name": "yurmax_equipment_analysis",
                "schema": EQUIPMENT_AI_SCHEMA,
                "strict": True
            }
        }
    )

    text = response.output_text

    if not text:
        return {
            "confirmed": []
        }

    return json.loads(text)


async def analyze_equipment_from_photos(
    photo_paths,
    car_data,
    progress_callback=None
):

    """
    Анализируем фотографии пачками.
    """

    # =====================================================
    # Базовый результат:
    # ВСЁ неизвестно до тех пор, пока AI не подтвердит.
    # =====================================================

    results = {}

    for category, options in EQUIPMENT.items():

        results[category] = {}

        for option in options:

            results[category][option] = {

                "status":
                    "Не подтверждено по фото",

                "value":
                    "—",

                "evidence":
                    "Оборудование не удалось достоверно подтвердить по предоставленным фотографиям."
            }


    if not photo_paths:

        return results


    # =====================================================
    # Подготавливаем фотографии
    # =====================================================

    image_urls = []

    for path in photo_paths:

        try:

            image_url = prepare_ai_image(
                path
            )

            image_urls.append(
                image_url
            )

        except Exception as e:

            print(
                "AI IMAGE PREP ERROR:",
                repr(e)
            )


    if not image_urls:

        return results


    # =====================================================
    # Разбиваем фотографии на небольшие пачки
    # =====================================================

    batch_size = 6

    all_confirmed = []


    for start in range(
        0,
        len(image_urls),
        batch_size
    ):

        batch = image_urls[
            start:start + batch_size
        ]

        if progress_callback:

            await progress_callback(
                min(
                    start + len(batch),
                    len(image_urls)
                ),
                len(image_urls)
            )


        try:

            result = await analyze_equipment_batch(
                batch,
                car_data
            )

            confirmed = result.get(
                "confirmed",
                []
            )

            if isinstance(
                confirmed,
                list
            ):

                all_confirmed.extend(
                    confirmed
                )

        except Exception as e:

            print(
                "OPENAI ANALYSIS ERROR:",
                repr(e)
            )

            # Не ломаем весь отчёт,
            # если одна пачка фотографий
            # не обработалась.
            continue


    # =====================================================
    # Проверяем ответы AI
    # =====================================================

    valid_categories = set(
        EQUIPMENT.keys()
    )


    valid_options = {

        category: set(options)

        for category, options
        in EQUIPMENT.items()
    }


    for item in all_confirmed:

        if not isinstance(
            item,
            dict
        ):
            continue


        category = str(
            item.get(
                "category",
                ""
            )
        ).strip()


        option = str(
            item.get(
                "option",
                ""
            )
        ).strip()


        value = str(
            item.get(
                "value",
                ""
            )
        ).strip()


        evidence = str(
            item.get(
                "evidence",
                ""
            )
        ).strip()


        if category not in valid_categories:
            continue


        if option not in valid_options[category]:
            continue


        if not value:
            value = "Есть"


        if not evidence:
            evidence = (
                "Визуально подтверждено "
                "на предоставленной фотографии."
            )


        results[category][option] = {

            "status":
                "Подтверждено по фото",

            "value":
                value,

            "evidence":
                evidence
        }


    return results


# =========================================================
# FONTS
# =========================================================

def register_fonts():

    regular_candidates = [

        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",

        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]


    bold_candidates = [

        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",

        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]


    regular = None

    bold = None


    for path in regular_candidates:

        if os.path.exists(path):

            regular = path

            break


    for path in bold_candidates:

        if os.path.exists(path):

            bold = path

            break


    if not regular or not bold:

        raise RuntimeError(
            "DejaVu fonts not found"
        )


    pdfmetrics.registerFont(
        TTFont(
            "DejaVu",
            regular
        )
    )


    pdfmetrics.registerFont(
        TTFont(
            "DejaVuBold",
            bold
        )
    )


    return regular, bold


REGULAR_FONT, BOLD_FONT = register_fonts()


def get_pil_font(
    size,
    bold=False
):

    path = (
        BOLD_FONT
        if bold
        else REGULAR_FONT
    )

    return ImageFont.truetype(
        path,
        size
    )


# =========================================================
# LKP MAP
# =========================================================

def draw_arrow(
    draw,
    start,
    end
):

    draw.line(
        [start, end],
        fill=(70, 190, 130),
        width=5
    )


    x1, y1 = start

    x2, y2 = end


    dx = x2 - x1

    dy = y2 - y1


    length = max(
        (dx * dx + dy * dy) ** 0.5,
        1
    )


    ux = dx / length

    uy = dy / length


    size = 18


    left = (

        x2
        - ux * size
        - uy * size * 0.6,

        y2
        - uy * size
        + ux * size * 0.6
    )


    right = (

        x2
        - ux * size
        + uy * size * 0.6,

        y2
        - uy * size
        - ux * size * 0.6
    )


    draw.polygon(
        [
            (x2, y2),
            left,
            right
        ],
        fill=(70, 190, 130)
    )


def make_lkp_map(
    measurements
):

    width = 1600

    height = 1350


    img = Image.new(
        "RGB",
        (
            width,
            height
        ),
        (12, 15, 17)
    )


    draw = ImageDraw.Draw(
        img
    )


    title_font = get_pil_font(
        48,
        True
    )


    subtitle_font = get_pil_font(
        30
    )


    label_font = get_pil_font(
        25,
        True
    )


    value_font = get_pil_font(
        26,
        True
    )


    draw.text(
        (60, 45),
        "КАРТА ЛАКОКРАСОЧНОГО ПОКРЫТИЯ",
        font=title_font,
        fill=(255, 255, 255)
    )


    draw.text(
        (60, 110),
        "ЮРМАКС",
        font=subtitle_font,
        fill=(70, 190, 130)
    )


    car_x1 = 560

    car_x2 = 1040

    car_y1 = 230

    car_y2 = 1100


    draw.rounded_rectangle(
        [
            car_x1,
            car_y1,
            car_x2,
            car_y2
        ],
        radius=130,
        fill=(48, 53, 57),
        outline=(170, 175, 180),
        width=6
    )


    draw.rounded_rectangle(
        [
            615,
            270,
            985,
            455
        ],
        radius=65,
        fill=(58, 63, 67),
        outline=(120, 125, 130),
        width=4
    )


    draw.rounded_rectangle(
        [
            625,
            420,
            975,
            780
        ],
        radius=75,
        fill=(32, 38, 43),
        outline=(105, 110, 115),
        width=4
    )


    draw.polygon(
        [
            (650, 440),
            (950, 440),
            (915, 555),
            (685, 555)
        ],
        fill=(28, 45, 52),
        outline=(100, 110, 115)
    )


    draw.polygon(
        [
            (685, 650),
            (915, 650),
            (950, 755),
            (650, 755)
        ],
        fill=(28, 45, 52),
        outline=(100, 110, 115)
    )


    draw.rounded_rectangle(
        [
            615,
            780,
            985,
            1050
        ],
        radius=65,
        fill=(58, 63, 67),
        outline=(120, 125, 130),
        width=4
    )


    for y in [380, 875]:

        draw.rounded_rectangle(
            [
                520,
                y,
                590,
                y + 160
            ],
            radius=30,
            fill=(8, 9, 10)
        )


        draw.rounded_rectangle(
            [
                1010,
                y,
                1080,
                y + 160
            ],
            radius=30,
            fill=(8, 9, 10)
        )


    draw.line(
        [
            (800, 250),
            (800, 1050)
        ],
        fill=(100, 105, 110),
        width=3
    )


    def label_box(
        x,
        y,
        text,
        value
    ):

        box_w = 390

        box_h = 92


        draw.rounded_rectangle(
            [
                x,
                y,
                x + box_w,
                y + box_h
            ],
            radius=18,
            fill=(22, 26, 29),
            outline=(70, 190, 130),
            width=3
        )


        draw.text(
            (
                x + 18,
                y + 12
            ),
            text,
            font=label_font,
            fill=(245, 245, 245)
        )


        draw.text(
            (
                x + 18,
                y + 51
            ),
            f"{value} µm",
            font=value_font,
            fill=(70, 190, 130)
        )


    positions = {

        "Капот":
            (
                60,
                250,
                (615, 360)
            ),

        "Крыша":
            (
                60,
                520,
                (625, 600)
            ),

        "Крышка багажника":
            (
                60,
                790,
                (615, 930)
            ),

        "Переднее левое крыло":
            (
                60,
                1010,
                (560, 450)
            ),

        "Передняя левая дверь":
            (
                60,
                1120,
                (625, 520)
            ),

        "Заднее левое крыло":
            (
                1140,
                1010,
                (1040, 950)
            ),

        "Задняя левая дверь":
            (
                1140,
                900,
                (975, 680)
            ),

        "Переднее правое крыло":
            (
                1140,
                250,
                (1040, 450)
            ),

        "Передняя правая дверь":
            (
                1140,
                520,
                (975, 520)
            ),

        "Задняя правая дверь":
            (
                1140,
                650,
                (975, 700)
            ),

        "Заднее правое крыло":
            (
                1140,
                790,
                (1040, 930)
            ),
    }


    for part, value in measurements.items():

        if part not in positions:

            continue


        x, y, target = positions[part]


        label_box(
            x,
            y,
            part,
            value
        )


        if x < width // 2:

            start = (
                x + 390,
                y + 46
            )

        else:

            start = (
                x,
                y + 46
            )


        draw_arrow(
            draw,
            start,
            target
        )


    draw.text(
        (60, 1270),
        "Измерения указаны в микрометрах (µm)",
        font=subtitle_font,
        fill=(180, 185, 190)
    )


    output = BytesIO()


    img.save(
        output,
        format="PNG"
    )


    output.seek(0)


    return output


# =========================================================
# PDF HEADER / FOOTER
# =========================================================

def pdf_header_footer(
    canvas,
    doc
):

    canvas.saveState()


    width, height = A4


    canvas.setFillColor(
        colors.HexColor("#101416")
    )


    canvas.rect(
        0,
        height - 20 * mm,
        width,
        20 * mm,
        fill=1,
        stroke=0
    )


    canvas.setFont(
        "DejaVuBold",
        15
    )


    canvas.setFillColor(
        colors.white
    )


    canvas.drawString(
        15 * mm,
        height - 13 * mm,
        "ЮРМАКС"
    )


    canvas.setFont(
        "DejaVu",
        8
    )


    canvas.setFillColor(
        colors.HexColor("#46BE82")
    )


    canvas.drawRightString(
        width - 15 * mm,
        height - 13 * mm,
        "АКТ ОСМОТРА АВТОМОБИЛЯ"
    )


    canvas.setFillColor(
        colors.HexColor("#777777")
    )


    canvas.setFont(
        "DejaVu",
        8
    )


    canvas.drawString(
        15 * mm,
        10 * mm,
        "ЮРМАКС"
    )


    canvas.drawRightString(
        width - 15 * mm,
        10 * mm,
        f"Страница {doc.page}"
    )


    canvas.restoreState()


# =========================================================
# EQUIPMENT TABLE
# =========================================================

def make_equipment_table(
    category,
    options,
    equipment_results
):

    header_style = ParagraphStyle(
        "EquipmentHeader",
        fontName="DejaVuBold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )


    body_style = ParagraphStyle(
        "EquipmentBody",
        fontName="DejaVu",
        fontSize=7.6,
        leading=9.5,
        textColor=colors.HexColor("#202426"),
    )


    confirmed_style = ParagraphStyle(
        "EquipmentConfirmed",
        fontName="DejaVuBold",
        fontSize=7.6,
        leading=9.5,
        textColor=colors.HexColor("#278553"),
    )


    unknown_style = ParagraphStyle(
        "EquipmentUnknown",
        fontName="DejaVu",
        fontSize=7.4,
        leading=9.2,
        textColor=colors.HexColor("#777777"),
    )


    evidence_style = ParagraphStyle(
        "EquipmentEvidence",
        fontName="DejaVu",
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor("#555B60"),
    )


    data = [

        [
            Paragraph(
                "ОПЦИЯ",
                header_style
            ),

            Paragraph(
                "РЕЗУЛЬТАТ",
                header_style
            ),

            Paragraph(
                "ОСНОВАНИЕ",
                header_style
            )
        ]
    ]


    category_results = (
        equipment_results.get(
            category,
            {}
        )
        if equipment_results
        else {}
    )


    for option in options:

        result = category_results.get(
            option,
            {
                "status":
                    "Не подтверждено по фото",

                "value":
                    "—",

                "evidence":
                    "Нет достоверного визуального подтверждения."
            }
        )


        status = result.get(
            "status",
            "Не подтверждено по фото"
        )


        value = result.get(
            "value",
            "—"
        )


        evidence = result.get(
            "evidence",
            "—"
        )


        if status == "Подтверждено по фото":

            result_text = (
                "Подтверждено по фото"
            )

            if value and value != "Есть":

                result_text += (
                    f"<br/><b>{value}</b>"
                )

            result_paragraph = Paragraph(
                result_text,
                confirmed_style
            )

        else:

            result_paragraph = Paragraph(
                "Не подтверждено по фото",
                unknown_style
            )


        data.append(
            [

                Paragraph(
                    option,
                    body_style
                ),

                result_paragraph,

                Paragraph(
                    evidence,
                    evidence_style
                )
            ]
        )


    table = Table(
        data,
        colWidths=[
            63 * mm,
            42 * mm,
            65 * mm
        ],
        repeatRows=1
    )


    table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#15191B")
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.35,
                colors.HexColor("#D7DADD")
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#F8F9F9")
                ]
            ),
        ])
    )


    return table


# =========================================================
# SIGNATURE BLOCK
# =========================================================

def signature_table(
    master_name
):

    data = [

        [

            Paragraph(
                "<b>МАСТЕР ОСМОТРА</b><br/><br/>"
                + master_name
                + "<br/><br/>"
                "________________________",

                ParagraphStyle(
                    "Master",
                    fontName="DejaVu",
                    fontSize=9,
                    leading=14,
                    textColor=colors.HexColor("#202426"),
                )
            ),

            Paragraph(
                "<b>ПОДПИСЬ / ПЕЧАТЬ</b><br/><br/><br/>"
                "________________________",

                ParagraphStyle(
                    "Signature",
                    fontName="DejaVu",
                    fontSize=9,
                    leading=14,
                    textColor=colors.HexColor("#202426"),
                )
            )
        ]
    ]


    table = Table(
        data,
        colWidths=[
            85 * mm,
            85 * mm
        ],
        rowHeights=[
            35 * mm
        ]
    )


    table.setStyle(
        TableStyle([

            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.7,
                colors.HexColor("#BFC4C7")
            ),

            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#BFC4C7")
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                10
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                10
            ),
        ])
    )


    return table


# =========================================================
# CREATE PDF
# =========================================================

def create_pdf(
    car_data,
    measurements,
    master_name,
    report_date,
    photo_paths=None,
    equipment_results=None
):

    if photo_paths is None:

        photo_paths = []


    if equipment_results is None:

        equipment_results = {}


    output = BytesIO()


    doc = SimpleDocTemplate(

        output,

        pagesize=A4,

        rightMargin=15 * mm,

        leftMargin=15 * mm,

        topMargin=27 * mm,

        bottomMargin=18 * mm,

        title="ЮРМАКС — Акт осмотра автомобиля",

        author="ЮРМАКС",
    )


    title_style = ParagraphStyle(

        "TitleCustom",

        fontName="DejaVuBold",

        fontSize=24,

        leading=29,

        alignment=TA_CENTER,

        textColor=colors.HexColor("#15191B"),

        spaceAfter=8,
    )


    subtitle_style = ParagraphStyle(

        "SubtitleCustom",

        fontName="DejaVu",

        fontSize=11,

        leading=15,

        alignment=TA_CENTER,

        textColor=colors.HexColor("#555B60"),

        spaceAfter=20,
    )


    section_style = ParagraphStyle(

        "SectionCustom",

        fontName="DejaVuBold",

        fontSize=15,

        leading=19,

        textColor=colors.HexColor("#15191B"),

        spaceBefore=5,

        spaceAfter=10,
    )


    normal_style = ParagraphStyle(

        "NormalCustom",

        fontName="DejaVu",

        fontSize=10,

        leading=14,

        textColor=colors.HexColor("#25292B"),
    )


    small_style = ParagraphStyle(

        "SmallCustom",

        fontName="DejaVu",

        fontSize=8,

        leading=11,

        textColor=colors.HexColor("#666C70"),
    )


    story = []


    # =====================================================
    # FIRST PAGE
    # =====================================================

    story.append(
        Spacer(
            1,
            12 * mm
        )
    )


    story.append(

        Paragraph(
            "ЮРМАКС",

            ParagraphStyle(
                "Brand",
                fontName="DejaVuBold",
                fontSize=34,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#46BE82"),
                spaceAfter=7,
            )
        )
    )


    story.append(

        Paragraph(
            "ОТЧЁТ ОБ ОСМОТРЕ<br/>АВТОМОБИЛЯ",
            title_style
        )
    )


    story.append(

        Paragraph(
            "Профессиональный отчёт осмотра",
            subtitle_style
        )
    )


    info_data = [

        [
            "МАРКА",
            car_data["make"]
        ],

        [
            "МОДЕЛЬ",
            car_data["model"]
        ],

        [
            "ГОД ВЫПУСКА",
            car_data["year"]
        ],

        [
            "VIN",
            car_data["vin"]
        ],

        [
            "ПРОБЕГ",
            f'{car_data["mileage"]} км'
        ],

        [
            "ТИП ДВИГАТЕЛЯ",
            car_data["engine_type"]
        ],

        [
            "ОБЪЁМ ДВИГАТЕЛЯ",
            f'{car_data["engine_volume"]} л'
        ],

        [
            "МОЩНОСТЬ",
            f'{car_data["engine_hp"]} л.с.'
        ],

        [
            "КОРОБКА ПЕРЕДАЧ",
            car_data["gearbox"]
        ],
    ]


    info_table = Table(

        info_data,

        colWidths=[
            62 * mm,
            108 * mm
        ]
    )


    info_table.setStyle(

        TableStyle([

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.6,
                colors.HexColor("#D4D8DA")
            ),

            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#F0F2F3")
            ),

            (
                "FONTNAME",
                (0, 0),
                (0, -1),
                "DejaVuBold"
            ),

            (
                "FONTNAME",
                (1, 0),
                (1, -1),
                "DejaVu"
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                9
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                8
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7
            ),
        ])
    )


    story.append(
        info_table
    )


    story.append(
        Spacer(
            1,
            12 * mm
        )
    )


    report_info = Table(

        [
            [
                "Дата формирования отчёта",
                report_date
            ],

            [
                "Мастер осмотра",
                master_name
            ],
        ],

        colWidths=[
            62 * mm,
            108 * mm
        ]
    )


    report_info.setStyle(

        TableStyle([

            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.6,
                colors.HexColor("#D4D8DA")
            ),

            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#D4D8DA")
            ),

            (
                "FONTNAME",
                (0, 0),
                (0, -1),
                "DejaVuBold"
            ),

            (
                "FONTNAME",
                (1, 0),
                (1, -1),
                "DejaVu"
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                9
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                8
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7
            ),
        ])
    )


    story.append(
        report_info
    )


    story.append(
        Spacer(
            1,
            12 * mm
        )
    )


    story.append(
        signature_table(
            master_name
        )
    )


    # =====================================================
    # LKP
    # =====================================================

    story.append(
        PageBreak()
    )


    story.append(

        Paragraph(
            "КАРТА ЛАКОКРАСОЧНОГО ПОКРЫТИЯ",
            section_style
        )
    )


    lkp_image = make_lkp_map(
        measurements
    )


    story.append(

        RLImage(
            lkp_image,
            width=180 * mm,
            height=151.8 * mm
        )
    )


    story.append(
        Spacer(
            1,
            5 * mm
        )
    )


    story.append(

        Paragraph(
            "Все значения указаны в микрометрах (µm).",
            normal_style
        )
    )


    # =====================================================
    # EQUIPMENT
    # =====================================================

    story.append(
        PageBreak()
    )


    story.append(

        Paragraph(
            "КОМПЛЕКТАЦИЯ И ОСНАЩЕНИЕ",
            title_style
        )
    )


    story.append(

        Paragraph(
            "Автоматический анализ предоставленных фотографий",
            subtitle_style
        )
    )


    story.append(

        Paragraph(
            "<b>Важно:</b> отметка «Не подтверждено по фото» "
            "не означает отсутствие оборудования. "
            "Она означает, что данный пункт невозможно "
            "достоверно подтвердить по предоставленным фотографиям.",
            small_style
        )
    )


    story.append(
        Spacer(
            1,
            5 * mm
        )
    )


    for category, options in EQUIPMENT.items():

        story.append(

            Paragraph(
                category,
                section_style
            )
        )


        story.append(

            make_equipment_table(
                category,
                options,
                equipment_results
            )
        )


        story.append(
            Spacer(
                1,
                7 * mm
            )
        )


    # =====================================================
    # ENGINE ENDOSCOPY
    # =====================================================

    if car_data["engine_type"] in [

        "Бензин",
        "Дизель"
    ]:

        story.append(
            PageBreak()
        )


        story.append(

            Paragraph(
                "ЭНДОСКОПИЯ ДВИГАТЕЛЯ",
                title_style
            )
        )


        story.append(

            Paragraph(
                "Раздел эндоскопического осмотра",
                subtitle_style
            )
        )


        endoscopy_data = [

            [
                "Параметр",
                "Результат"
            ],

            [
                "Тип двигателя",
                car_data["engine_type"]
            ],

            [
                "Объём",
                f'{car_data["engine_volume"]} л'
            ],

            [
                "Цилиндры",
                "Не заполнено"
            ],

            [
                "Стенки цилиндров",
                "Не заполнено"
            ],

            [
                "Поршни",
                "Не заполнено"
            ],

            [
                "Следы задиров",
                "Не заполнено"
            ],

            [
                "Следы нагара",
                "Не заполнено"
            ],

            [
                "Следы масла",
                "Не заполнено"
            ],

            [
                "Общее состояние",
                "Не заполнено"
            ],
        ]


        endoscopy_table = Table(

            endoscopy_data,

            colWidths=[
                80 * mm,
                90 * mm
            ]
        )


        endoscopy_table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#15191B")
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "DejaVuBold"
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D4D8DA")
                ),

                (
                    "FONTNAME",
                    (0, 1),
                    (-1, -1),
                    "DejaVu"
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    9
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),
            ])
        )


        story.append(
            endoscopy_table
        )


    # =====================================================
    # PHOTOS
    # =====================================================

    if photo_paths:

        story.append(
            PageBreak()
        )


        story.append(

            Paragraph(
                "ФОТОГРАФИИ АВТОМОБИЛЯ",
                title_style
            )
        )


        story.append(

            Paragraph(
                "Фотоматериалы осмотра",
                subtitle_style
            )
        )


        for index, photo_path in enumerate(
            photo_paths
        ):

            if index > 0 and index % 4 == 0:

                story.append(
                    PageBreak()
                )


                story.append(

                    Paragraph(
                        "ФОТОГРАФИИ АВТОМОБИЛЯ",
                        section_style
                    )
                )


            try:

                img = Image.open(
                    photo_path
                )


                img.thumbnail(
                    (760, 520)
                )


                temp = BytesIO()


                img.convert(
                    "RGB"
                ).save(
                    temp,
                    format="JPEG",
                    quality=90
                )


                temp.seek(0)


                rl_img = RLImage(

                    temp,

                    width=85 * mm,

                    height=58 * mm
                )


                photo_cell = Table(

                    [
                        [
                            rl_img
                        ]
                    ],

                    colWidths=[
                        85 * mm
                    ],

                    rowHeights=[
                        62 * mm
                    ]
                )


                photo_cell.setStyle(

                    TableStyle([

                        (
                            "BOX",
                            (0, 0),
                            (-1, -1),
                            0.5,
                            colors.HexColor("#D4D8DA")
                        ),

                        (
                            "VALIGN",
                            (0, 0),
                            (-1, -1),
                            "MIDDLE"
                        ),

                        (
                            "ALIGN",
                            (0, 0),
                            (-1, -1),
                            "CENTER"
                        ),
                    ])
                )


                if index % 2 == 0:

                    if index + 1 < len(
                        photo_paths
                    ):

                        next_path = photo_paths[
                            index + 1
                        ]


                        try:

                            img2 = Image.open(
                                next_path
                            )


                            img2.thumbnail(
                                (760, 520)
                            )


                            temp2 = BytesIO()


                            img2.convert(
                                "RGB"
                            ).save(
                                temp2,
                                format="JPEG",
                                quality=90
                            )


                            temp2.seek(0)


                            rl_img2 = RLImage(

                                temp2,

                                width=85 * mm,

                                height=58 * mm
                            )


                            photo_cell2 = Table(

                                [
                                    [
                                        rl_img2
                                    ]
                                ],

                                colWidths=[
                                    85 * mm
                                ],

                                rowHeights=[
                                    62 * mm
                                ]
                            )


                            photo_cell2.setStyle(

                                TableStyle([

                                    (
                                        "BOX",
                                        (0, 0),
                                        (-1, -1),
                                        0.5,
                                        colors.HexColor("#D4D8DA")
                                    ),

                                    (
                                        "VALIGN",
                                        (0, 0),
                                        (-1, -1),
                                        "MIDDLE"
                                    ),

                                    (
                                        "ALIGN",
                                        (0, 0),
                                        (-1, -1),
                                        "CENTER"
                                    ),
                                ])
                            )


                            row = Table(

                                [
                                    [
                                        photo_cell,
                                        photo_cell2
                                    ]
                                ],

                                colWidths=[
                                    88 * mm,
                                    88 * mm
                                ]
                            )


                            row.setStyle(

                                TableStyle([
                                    (
                                        "VALIGN",
                                        (0, 0),
                                        (-1, -1),
                                        "MIDDLE"
                                    )
                                ])
                            )


                            story.append(
                                row
                            )


                            story.append(
                                Spacer(
                                    1,
                                    5 * mm
                                )
                            )


                        except Exception as e:

                            print(
                                "PHOTO ERROR:",
                                repr(e)
                            )

                    else:

                        story.append(
                            photo_cell
                        )


                        story.append(
                            Spacer(
                                1,
                                5 * mm
                            )
                        )


            except Exception as e:

                print(
                    "PHOTO ERROR:",
                    repr(e)
                )


    # =====================================================
    # FINAL PAGE
    # =====================================================

    story.append(
        PageBreak()
    )


    story.append(

        Paragraph(
            "ЗАВЕРШЕНИЕ ОТЧЁТА",
            title_style
        )
    )


    story.append(
        Spacer(
            1,
            8 * mm
        )
    )


    story.append(

        Paragraph(
            "Мастер осмотра подтверждает проведение "
            "осмотра автомобиля и формирование настоящего отчёта.",
            normal_style
        )
    )


    story.append(
        Spacer(
            1,
            15 * mm
        )
    )


    story.append(
        signature_table(
            master_name
        )
    )


    story.append(
        Spacer(
            1,
            20 * mm
        )
    )


    story.append(

        Paragraph(
            f"Дата формирования отчёта: {report_date}",
            normal_style
        )
    )


    doc.build(

        story,

        onFirstPage=pdf_header_footer,

        onLaterPages=pdf_header_footer
    )


    output.seek(0)


    return output


# =========================================================
# START
# =========================================================

@dp.message(
    CommandStart()
)
async def start_handler(
    message: types.Message,
    state: FSMContext
):

    await state.clear()


    await message.answer(

        "Добро пожаловать в ЮРМАКС.\n\n"
        "Здесь можно сформировать "
        "профессиональный отчёт осмотра автомобиля.",

        reply_markup=main_keyboard
    )


# =========================================================
# CREATE
# =========================================================

@dp.message(
    F.text == "Создать акт"
)
async def create_handler(
    message: types.Message,
    state: FSMContext
):

    await state.clear()


    await state.set_state(
        InspectionForm.master_name
    )


    await message.answer(

        "Введите имя мастера осмотра.\n\n"
        "Например: Ян Ковальский"
    )


# =========================================================
# MASTER
# =========================================================

@dp.message(
    InspectionForm.master_name
)
async def master_handler(
    message: types.Message,
    state: FSMContext
):

    master_name = message.text.strip()


    if not master_name:

        await message.answer(
            "Введите имя мастера."
        )

        return


    await state.update_data(
        master_name=master_name
    )


    await state.set_state(
        InspectionForm.report_date
    )


    await message.answer(

        "Введите дату формирования отчёта.\n\n"
        "Формат: ДД.ММ.ГГГГ\n"
        "Например: 20.09.2026"
    )


# =========================================================
# REPORT DATE
# =========================================================

@dp.message(
    InspectionForm.report_date
)
async def report_date_handler(
    message: types.Message,
    state: FSMContext
):

    value = message.text.strip()


    try:

        parsed_date = datetime.strptime(
            value,
            "%d.%m.%Y"
        )


        report_date = parsed_date.strftime(
            "%d.%m.%Y"
        )


    except ValueError:

        await message.answer(

            "Неверный формат даты.\n\n"
            "Введите дату в формате:\n"
            "ДД.ММ.ГГГГ\n\n"
            "Например: 20.09.2026"
        )

        return


    await state.update_data(
        report_date=report_date
    )


    await state.set_state(
        InspectionForm.make
    )


    await message.answer(

        "Введите марку автомобиля.\n\n"
        "Например: BMW"
    )


# =========================================================
# MAKE
# =========================================================

@dp.message(
    InspectionForm.make
)
async def make_handler(
    message: types.Message,
    state: FSMContext
):

    await state.update_data(
        make=message.text.strip()
    )


    await state.set_state(
        InspectionForm.model
    )


    await message.answer(

        "Введите модель автомобиля.\n\n"
        "Например: X5"
    )


# =========================================================
# MODEL
# =========================================================

@dp.message(
    InspectionForm.model
)
async def model_handler(
    message: types.Message,
    state: FSMContext
):

    await state.update_data(
        model=message.text.strip()
    )


    await state.set_state(
        InspectionForm.year
    )


    await message.answer(

        "Введите год выпуска.\n\n"
        "Например: 2021"
    )


# =========================================================
# YEAR
# =========================================================

@dp.message(
    InspectionForm.year
)
async def year_handler(
    message: types.Message,
    state: FSMContext
):

    value = message.text.strip()


    if not value.isdigit():

        await message.answer(
            "Введите год цифрами.\n"
            "Например: 2021"
        )

        return


    await state.update_data(
        year=value
    )


    await state.set_state(
        InspectionForm.vin
    )


    await message.answer(
        "Введите VIN автомобиля."
    )


# =========================================================
# VIN
# =========================================================

@dp.message(
    InspectionForm.vin
)
async def vin_handler(
    message: types.Message,
    state: FSMContext
):

    await state.update_data(
        vin=message.text.strip()
    )


    await state.set_state(
        InspectionForm.mileage
    )


    await message.answer(

        "Введите пробег автомобиля в километрах.\n\n"
        "Например: 124500"
    )


# =========================================================
# MILEAGE
# =========================================================

@dp.message(
    InspectionForm.mileage
)
async def mileage_handler(
    message: types.Message,
    state: FSMContext
):

    value = message.text.strip()


    if not value.isdigit():

        await message.answer(

            "Введите пробег только цифрами.\n"
            "Например: 124500"
        )

        return


    await state.update_data(
        mileage=value
    )


    await state.set_state(
        InspectionForm.engine_type
    )


    await message.answer(

        "Выберите тип двигателя.",

        reply_markup=engine_keyboard
    )


# =========================================================
# ENGINE TYPE
# =========================================================

@dp.message(
    InspectionForm.engine_type
)
async def engine_type_handler(
    message: types.Message,
    state: FSMContext
):

    allowed = [

        "Бензин",
        "Дизель",
        "Гибрид",
        "Электро"
    ]


    value = message.text.strip()


    if value not in allowed:

        await message.answer(

            "Выберите тип двигателя кнопкой.",

            reply_markup=engine_keyboard
        )

        return


    await state.update_data(
        engine_type=value
    )


    await state.set_state(
        InspectionForm.engine_volume
    )


    await message.answer(

        "Введите объём двигателя в литрах.\n\n"
        "Например: 2.0"
    )


# =========================================================
# ENGINE VOLUME
# =========================================================

@dp.message(
    InspectionForm.engine_volume
)
async def engine_volume_handler(
    message: types.Message,
    state: FSMContext
):

    value = message.text.strip().replace(
        ",",
        "."
    )


    try:

        float(value)

    except ValueError:

        await message.answer(

            "Введите объём цифрами.\n\n"
            "Например: 2.0"
        )

        return


    await state.update_data(
        engine_volume=value
    )


    await state.set_state(
        InspectionForm.engine_hp
    )


    await message.answer(

        "Введите мощность двигателя в л.с.\n\n"
        "Например: 249"
    )


# =========================================================
# ENGINE HP
# =========================================================

@dp.message(
    InspectionForm.engine_hp
)
async def engine_hp_handler(
    message: types.Message,
    state: FSMContext
):

    value = message.text.strip()


    if not value.isdigit():

        await message.answer(

            "Введите мощность только цифрами.\n"
            "Например: 249"
        )

        return


    await state.update_data(
        engine_hp=value
    )


    await state.set_state(
        InspectionForm.gearbox
    )


    await message.answer(

        "Выберите коробку передач.",

        reply_markup=gearbox_keyboard
    )


# =========================================================
# GEARBOX
# =========================================================

@dp.message(
    InspectionForm.gearbox
)
async def gearbox_handler(
    message: types.Message,
    state: FSMContext
):

    allowed = [

        "МКПП",
        "АКПП",
        "Робот",
        "Вариатор"
    ]


    value = message.text.strip()


    if value not in allowed:

        await message.answer(

            "Выберите коробку кнопкой.",

            reply_markup=gearbox_keyboard
        )

        return


    await state.update_data(
        gearbox=value
    )


    await state.update_data(

        lkp_index=0,

        measurements={}
    )


    await state.set_state(
        InspectionForm.lkp
    )


    await message.answer(

        f"Введите толщину ЛКП.\n\n"
        f"Деталь: {LKP_PARTS[0]}\n\n"
        f"Например: 145"
    )


# =========================================================
# LKP
# =========================================================

@dp.message(
    InspectionForm.lkp
)
async def lkp_handler(
    message: types.Message,
    state: FSMContext
):

    value = message.text.strip()


    if not value.isdigit():

        await message.answer(

            "Введите значение цифрами.\n"
            "Например: 145"
        )

        return


    measurement = int(value)


    if measurement < 1 or measurement > 5000:

        await message.answer(
            "Введите значение от 1 до 5000 µm."
        )

        return


    data = await state.get_data()


    index = data["lkp_index"]


    measurements = data["measurements"]


    current_part = LKP_PARTS[index]


    measurements[current_part] = measurement


    next_index = index + 1


    if next_index < len(
        LKP_PARTS
    ):

        await state.update_data(

            lkp_index=next_index,

            measurements=measurements
        )


        await message.answer(

            f"Принято: {current_part} — "
            f"{measurement} µm\n\n"
            f"Теперь введите значение для:\n"
            f"{LKP_PARTS[next_index]}"
        )


        return


    await state.update_data(

        measurements=measurements,

        photos=[]
    )


    await state.set_state(
        InspectionForm.photos
    )


    await message.answer(

        "Все замеры ЛКП получены.\n\n"
        "Теперь отправьте фотографии автомобиля.\n\n"
        "Можно отправлять несколько фотографий подряд.\n"
        "Когда закончите — нажмите «Готово».",

        reply_markup=finish_photos_keyboard
    )


# =========================================================
# PHOTOS
# =========================================================

@dp.message(
    InspectionForm.photos,
    F.photo
)
async def photo_handler(
    message: types.Message,
    state: FSMContext
):

    data = await state.get_data()


    photos = data.get(
        "photos",
        []
    )


    largest = message.photo[-1]


    photos.append(
        largest.file_id
    )


    await state.update_data(
        photos=photos
    )


    await message.answer(

        f"Фото №{len(photos)} получено.\n"
        "Можешь отправить следующее или нажать «Готово»."
    )


# =========================================================
# FINISH PHOTOS
# =========================================================

@dp.message(
    InspectionForm.photos,
    F.text == "Готово"
)
async def finish_photos_handler(
    message: types.Message,
    state: FSMContext
):

    data = await state.get_data()


    photo_ids = data.get(
        "photos",
        []
    )


    if not photo_ids:

        await message.answer(

            "Пока нет ни одной фотографии.\n\n"
            "Отправь хотя бы одну фотографию "
            "автомобиля."
        )

        return


    await message.answer(

        f"Получено фотографий: {len(photo_ids)}.\n\n"
        "Шаг 1/3 — загружаю фотографии..."
    )


    photo_paths = []


    try:

        # =================================================
        # DOWNLOAD PHOTOS
        # =================================================

        for number, file_id in enumerate(

            photo_ids,

            start=1
        ):

            file = await bot.get_file(
                file_id
            )


            path = (
                f"/tmp/"
                f"yurmax_photo_{number}.jpg"
            )


            await bot.download_file(

                file.file_path,

                path
            )


            photo_paths.append(
                path
            )


        # =================================================
        # CAR DATA
        # =================================================

        car_data = {

            "make":
                data["make"],

            "model":
                data["model"],

            "year":
                data["year"],

            "vin":
                data["vin"],

            "mileage":
                data["mileage"],

            "engine_type":
                data["engine_type"],

            "engine_volume":
                data["engine_volume"],

            "engine_hp":
                data["engine_hp"],

            "gearbox":
                data["gearbox"],
        }


        # =================================================
        # AI ANALYSIS
        # =================================================

        await message.answer(

            "Шаг 2/3 — AI анализирует фотографии "
            "и определяет видимую комплектацию..."
        )


        async def ai_progress(
            current,
            total
        ):

            # Небольшая функция прогресса.
            # Не отправляем сообщение на каждый кадр,
            # чтобы не засорять Telegram.
            print(
                f"AI PHOTO BATCH: "
                f"{current}/{total}"
            )


        equipment_results = (

            await analyze_equipment_from_photos(

                photo_paths,

                car_data,

                progress_callback=ai_progress
            )
        )


        confirmed_count = 0


        for category in equipment_results:

            for option in equipment_results[
                category
            ]:

                result = equipment_results[
                    category
                ][option]


                if result.get(
                    "status"
                ) == "Подтверждено по фото":

                    confirmed_count += 1


        # =================================================
        # PDF
        # =================================================

        await message.answer(

            "Шаг 3/3 — формирую профессиональный PDF...\n\n"
            f"AI подтвердил по фотографиям: "
            f"{confirmed_count} пунктов."
        )


        pdf = create_pdf(

            car_data=car_data,

            measurements=data[
                "measurements"
            ],

            master_name=data[
                "master_name"
            ],

            report_date=data[
                "report_date"
            ],

            photo_paths=photo_paths,

            equipment_results=equipment_results
        )


        await message.answer_document(

            types.BufferedInputFile(

                pdf.read(),

                filename=
                    "YURMAX_AKT_OSMOTRA.pdf"
            )
        )


        await message.answer(

            "Готово.\n\n"
            "PDF-отчёт ЮРМАКС сформирован.\n\n"
            f"AI визуально подтвердил "
            f"{confirmed_count} пунктов комплектации.",

            reply_markup=main_keyboard
        )


    except Exception as e:

        print(
            "REPORT ERROR:",
            repr(e)
        )


        await message.answer(

            "Произошла ошибка при формировании отчёта.\n\n"
            "Проверь логи Render.\n\n"
            f"Ошибка: {str(e)[:500]}"
        )


    finally:

        for path in photo_paths:

            try:

                if os.path.exists(path):

                    os.remove(path)

            except Exception:

                pass


        await state.clear()


# =========================================================
# PHOTOS TEXT
# =========================================================

@dp.message(
    InspectionForm.photos,
    F.text
)
async def photos_text_handler(
    message: types.Message
):

    await message.answer(

        "Отправляй фотографии автомобиля.\n\n"
        "Когда закончишь — нажми «Готово»."
    )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

async def health(
    request
):

    return web.Response(
        text="YURMAX BOT OK"
    )


async def start_web_server():

    app = web.Application()


    app.router.add_get(
        "/",
        health
    )


    runner = web.AppRunner(
        app
    )


    await runner.setup()


    site = web.TCPSite(

        runner,

        "0.0.0.0",

        PORT
    )


    await site.start()


    print(
        f"Web server started on port {PORT}"
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    await start_web_server()


    print(
        "YURMAX BOT STARTED"
    )


    print(
        f"OPENAI MODEL: {OPENAI_MODEL}"
    )


    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
