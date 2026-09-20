import os
import asyncio
from io import BytesIO
from datetime import datetime

from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from PIL import Image, ImageDraw, ImageFont

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
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
# НАСТРОЙКИ
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


# =========================================================
# BOT
# =========================================================

bot = Bot(TOKEN)

dp = Dispatcher()


# =========================================================
# СОСТОЯНИЯ
# =========================================================

class InspectionForm(StatesGroup):

    master_name = State()
    report_date = State()

    make = State()
    model = State()
    year = State()
    vin = State()
    mileage = State()

    body_type = State()
    body_color = State()
    wheel_radius = State()

    engine_type = State()
    engine_volume = State()
    engine_hp = State()
    gearbox = State()

    lkp = State()

    photos = State()

    manual_equipment = State()


# =========================================================
# КЛАВИАТУРЫ
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
# КЛАВИАТУРА РУЧНОЙ КОМПЛЕКТАЦИИ
# =========================================================

def manual_equipment_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Есть",
                    callback_data="eq_yes"
                ),
                InlineKeyboardButton(
                    text="Нет",
                    callback_data="eq_no"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Пропустить",
                    callback_data="eq_skip"
                )
            ]
        ]
    )


# =========================================================
# ЛКП
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
# КОМПЛЕКТАЦИЯ
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
# СОЗДАНИЕ ПОЛНОГО СПИСКА РУЧНОЙ ПРОВЕРКИ
# =========================================================

def build_manual_equipment_queue():

    queue = []

    direct_fields = {
        "Тип кузова",
        "Цвет кузова",
        "Размер колёс",
    }

    for category, options in EQUIPMENT.items():

        for option in options:

            if option in direct_fields:
                continue

            queue.append({
                "category": category,
                "option": option
            })

    return queue


# =========================================================
# НАЧАЛЬНЫЕ РЕЗУЛЬТАТЫ КОМПЛЕКТАЦИИ
# =========================================================

def create_empty_equipment_results(
    body_type,
    body_color,
    wheel_radius
):

    results = {}

    for category, options in EQUIPMENT.items():

        results[category] = {}

        for option in options:

            results[category][option] = {
                "status": "Не заполнено",
                "value": "—",
                "evidence": ""
            }

    # -----------------------------------------------------
    # Заполняем данные, которые пользователь вводил отдельно
    # -----------------------------------------------------

    results["ЭКСТЕРЬЕР"]["Тип кузова"] = {
        "status": "Ручной ввод",
        "value": body_type,
        "evidence": ""
    }

    results["ЭКСТЕРЬЕР"]["Цвет кузова"] = {
        "status": "Ручной ввод",
        "value": body_color,
        "evidence": ""
    }

    results["ЭКСТЕРЬЕР"]["Размер колёс"] = {
        "status": "Ручной ввод",
        "value": wheel_radius,
        "evidence": ""
    }

    return results


# =========================================================
# СЛЕДУЮЩИЙ ВОПРОС КОМПЛЕКТАЦИИ
# =========================================================

async def ask_next_manual_equipment(
    message,
    state
):

    data = await state.get_data()

    queue = data.get(
        "manual_equipment_queue",
        []
    )

    index = data.get(
        "manual_equipment_index",
        0
    )

    if index >= len(queue):

        return False

    item = queue[index]

    category = item["category"]
    option = item["option"]

    await state.update_data(
        manual_current_category=category,
        manual_current_option=option
    )

    await message.answer(

        f"ПРОВЕРКА КОМПЛЕКТАЦИИ\n\n"
        f"Раздел: {category}\n"
        f"Опция: {option}\n\n"
        f"Укажите результат:",

        reply_markup=manual_equipment_keyboard()
    )

    return True


# =========================================================
# РЕГИСТРАЦИЯ ШРИФТОВ
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

    path = BOLD_FONT if bold else REGULAR_FONT

    return ImageFont.truetype(
        path,
        size
    )


# =========================================================
# СТРЕЛКА ЛКП
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
        x2 - ux * size - uy * size * 0.6,
        y2 - uy * size + ux * size * 0.6
    )

    right = (
        x2 - ux * size + uy * size * 0.6,
        y2 - uy * size - ux * size * 0.6
    )

    draw.polygon(
        [
            (x2, y2),
            left,
            right
        ],
        fill=(70, 190, 130)
    )


# =========================================================
# КАРТА ЛКП
# =========================================================

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

    draw = ImageDraw.Draw(img)

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

        "Капот": (
            60,
            250,
            (615, 360)
        ),

        "Крыша": (
            60,
            520,
            (625, 600)
        ),

        "Крышка багажника": (
            60,
            790,
            (615, 930)
        ),

        "Переднее левое крыло": (
            60,
            1010,
            (560, 450)
        ),

        "Передняя левая дверь": (
            60,
            1120,
            (625, 520)
        ),

        "Заднее левое крыло": (
            1140,
            1010,
            (1040, 950)
        ),

        "Задняя левая дверь": (
            1140,
            900,
            (975, 680)
        ),

        "Переднее правое крыло": (
            1140,
            250,
            (1040, 450)
        ),

        "Передняя правая дверь": (
            1140,
            520,
            (975, 520)
        ),

        "Задняя правая дверь": (
            1140,
            650,
            (975, 700)
        ),

        "Заднее правое крыло": (
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
# HEADER / FOOTER PDF
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
# ТАБЛИЦА КОМПЛЕКТАЦИИ
# =========================================================

def make_equipment_table(
    category,
    options,
    equipment_results
):

    header_style = ParagraphStyle(
        "EquipmentHeader",
        fontName="DejaVuBold",
        fontSize=8.5,
        leading=10,
        textColor=colors.white,
    )

    body_style = ParagraphStyle(
        "EquipmentBody",
        fontName="DejaVu",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#202426"),
    )

    value_style = ParagraphStyle(
        "EquipmentValue",
        fontName="DejaVuBold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#278553"),
    )

    no_style = ParagraphStyle(
        "EquipmentNo",
        fontName="DejaVuBold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#A33A3A"),
    )

    unknown_style = ParagraphStyle(
        "EquipmentUnknown",
        fontName="DejaVu",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#777777"),
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
                "status": "Не заполнено",
                "value": "—"
            }
        )

        status = result.get(
            "status",
            "Не заполнено"
        )

        value = result.get(
            "value",
            "—"
        )

        if status in [
            "Ручной ввод",
            "Заполнено"
        ]:

            if value == "Нет":

                result_paragraph = Paragraph(
                    "Нет",
                    no_style
                )

            elif value == "—":

                result_paragraph = Paragraph(
                    "—",
                    unknown_style
                )

            else:

                result_paragraph = Paragraph(
                    str(value),
                    value_style
                )

        else:

            result_paragraph = Paragraph(
                "—",
                unknown_style
            )

        data.append(
            [
                Paragraph(
                    option,
                    body_style
                ),
                result_paragraph
            ]
        )

    table = Table(
        data,
        colWidths=[
            105 * mm,
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
                7
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7
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
# ПОДПИСЬ
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
# СОЗДАНИЕ PDF
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

    story = []

    # =====================================================
    # ПЕРВАЯ СТРАНИЦА
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
            "ТИП КУЗОВА",
            car_data["body_type"]
        ],

        [
            "ЦВЕТ",
            car_data["body_color"]
        ],

        [
            "РАЗМЕР КОЛЁС",
            car_data["wheel_radius"]
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
            10 * mm
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
    # ЛКП
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
    # КОМПЛЕКТАЦИЯ
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
            "Перечень оборудования автомобиля",
            subtitle_style
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
    # ЭНДОСКОПИЯ
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
    # ФОТО
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

        for index in range(
            0,
            len(photo_paths),
            2
        ):

            row_cells = []

            for position in range(2):

                photo_index = index + position

                if photo_index >= len(photo_paths):

                    break

                photo_path = photo_paths[
                    photo_index
                ]

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
                        width=82 * mm,
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

                    row_cells.append(
                        photo_cell
                    )

                except Exception as e:

                    print(
                        "PHOTO ERROR:",
                        repr(e)
                    )

            if row_cells:

                if len(row_cells) == 1:

                    row_cells.append("")

                row = Table(
                    [
                        row_cells
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

    # =====================================================
    # ФИНАЛ
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
# УДАЛЕНИЕ ВРЕМЕННЫХ ФОТО
# =========================================================

def cleanup_photo_paths(
    photo_paths
):

    for path in photo_paths:

        try:

            if os.path.exists(path):

                os.remove(path)

        except Exception:

            pass


# =========================================================
# ФОРМИРОВАНИЕ И ОТПРАВКА PDF
# =========================================================

async def generate_and_send_report(
    message,
    state
):

    data = await state.get_data()

    photo_paths = data.get(
        "photo_paths",
        []
    )

    try:

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

            "body_type":
                data["body_type"],

            "body_color":
                data["body_color"],

            "wheel_radius":
                data["wheel_radius"],

            "engine_type":
                data["engine_type"],

            "engine_volume":
                data["engine_volume"],

            "engine_hp":
                data["engine_hp"],

            "gearbox":
                data["gearbox"],
        }

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

            equipment_results=data.get(
                "equipment_results",
                {}
            )
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
            "PDF-отчёт ЮРМАКС сформирован.",

            reply_markup=main_keyboard
        )

    except Exception as e:

        print(
            "PDF ERROR:",
            repr(e)
        )

        await message.answer(

            "Произошла ошибка при формировании PDF.\n\n"
            "Проверь логи Render."
        )

    finally:

        cleanup_photo_paths(
            photo_paths
        )

        await state.clear()


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
# СОЗДАТЬ АКТ
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
# МАСТЕР
# =========================================================

@dp.message(
    InspectionForm.master_name
)
async def master_handler(
    message: types.Message,
    state: FSMContext
):

    master_name = (
        message.text or ""
    ).strip()

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
# ДАТА
# =========================================================

@dp.message(
    InspectionForm.report_date
)
async def report_date_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

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
# МАРКА
# =========================================================

@dp.message(
    InspectionForm.make
)
async def make_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите марку автомобиля."
        )

        return

    await state.update_data(
        make=value
    )

    await state.set_state(
        InspectionForm.model
    )

    await message.answer(

        "Введите модель автомобиля.\n\n"
        "Например: X5"
    )


# =========================================================
# МОДЕЛЬ
# =========================================================

@dp.message(
    InspectionForm.model
)
async def model_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите модель автомобиля."
        )

        return

    await state.update_data(
        model=value
    )

    await state.set_state(
        InspectionForm.year
    )

    await message.answer(

        "Введите год выпуска.\n\n"
        "Например: 2021"
    )


# =========================================================
# ГОД
# =========================================================

@dp.message(
    InspectionForm.year
)
async def year_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value.isdigit():

        await message.answer(
            "Введите год цифрами.\n"
            "Например: 2021"
        )

        return

    year = int(value)

    if year < 1886 or year > 2100:

        await message.answer(
            "Введите корректный год."
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

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите VIN автомобиля."
        )

        return

    await state.update_data(
        vin=value.upper()
    )

    await state.set_state(
        InspectionForm.mileage
    )

    await message.answer(

        "Введите пробег автомобиля в километрах.\n\n"
        "Например: 124500"
    )


# =========================================================
# ПРОБЕГ
# =========================================================

@dp.message(
    InspectionForm.mileage
)
async def mileage_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

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
        InspectionForm.body_type
    )

    await message.answer(

        "Введите тип кузова.\n\n"
        "Например:\n"
        "Седан\n"
        "Универсал\n"
        "Хэтчбек\n"
        "Кроссовер\n"
        "Внедорожник\n"
        "Купе\n"
        "Кабриолет\n"
        "Минивэн\n"
        "Пикап"
    )


# =========================================================
# ТИП КУЗОВА
# =========================================================

@dp.message(
    InspectionForm.body_type
)
async def body_type_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите тип кузова."
        )

        return

    await state.update_data(
        body_type=value
    )

    await state.set_state(
        InspectionForm.body_color
    )

    await message.answer(

        "Введите цвет автомобиля.\n\n"
        "Например: Чёрный металлик"
    )


# =========================================================
# ЦВЕТ
# =========================================================

@dp.message(
    InspectionForm.body_color
)
async def body_color_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите цвет автомобиля."
        )

        return

    await state.update_data(
        body_color=value
    )

    await state.set_state(
        InspectionForm.wheel_radius
    )

    await message.answer(

        "Введите радиус колёс.\n\n"
        "Например: R18\n"
        "или: 18"
    )


# =========================================================
# РАДИУС КОЛЁС
# =========================================================

@dp.message(
    InspectionForm.wheel_radius
)
async def wheel_radius_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip().upper()

    if not value:

        await message.answer(
            "Введите радиус колёс."
        )

        return

    if value.isdigit():

        value = "R" + value

    await state.update_data(
        wheel_radius=value
    )

    await state.set_state(
        InspectionForm.engine_type
    )

    await message.answer(

        "Выберите тип двигателя.",

        reply_markup=engine_keyboard
    )


# =========================================================
# ДВИГАТЕЛЬ
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

    value = (
        message.text or ""
    ).strip()

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
        "Например: 2.0\n\n"
        "Для электро можно указать 0."
    )


# =========================================================
# ОБЪЁМ
# =========================================================

@dp.message(
    InspectionForm.engine_volume
)
async def engine_volume_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip().replace(
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
# МОЩНОСТЬ
# =========================================================

@dp.message(
    InspectionForm.engine_hp
)
async def engine_hp_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

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
# КОРОБКА
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

    value = (
        message.text or ""
    ).strip()

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

        "Введите толщину ЛКП.\n\n"
        f"Деталь: {LKP_PARTS[0]}\n\n"
        "Например: 145"
    )


# =========================================================
# ЛКП
# =========================================================

@dp.message(
    InspectionForm.lkp
)
async def lkp_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

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

    measurements[
        current_part
    ] = measurement

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
            "Теперь введите значение для:\n"
            f"{LKP_PARTS[next_index]}"
        )

        return

    # -----------------------------------------------------
    # После ЛКП
    # -----------------------------------------------------

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
# ФОТО
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
# ГОТОВО
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
        "Загружаю фотографии..."
    )

    photo_paths = []

    try:

        # -------------------------------------------------
        # Скачиваем фотографии
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Создаём пустую комплектацию
        # -------------------------------------------------

        equipment_results = (
            create_empty_equipment_results(

                body_type=data[
                    "body_type"
                ],

                body_color=data[
                    "body_color"
                ],

                wheel_radius=data[
                    "wheel_radius"
                ]
            )
        )

        # -------------------------------------------------
        # Все остальные пункты идут вручную
        # -------------------------------------------------

        manual_queue = (
            build_manual_equipment_queue()
        )

        # -------------------------------------------------
        # Сохраняем всё
        # -------------------------------------------------

        await state.update_data(

            equipment_results=
                equipment_results,

            manual_equipment_queue=
                manual_queue,

            manual_equipment_index=
                0,

            photo_paths=
                photo_paths
        )

        await message.answer(

            "Фотографии загружены.\n\n"
            "Теперь заполним комплектацию вручную.\n"
            "Для каждого пункта выберите:\n"
            "Есть / Нет / Пропустить."
        )

        await state.set_state(
            InspectionForm.manual_equipment
        )

        await ask_next_manual_equipment(
            message,
            state
        )

    except Exception as e:

        print(
            "PHOTO / REPORT ERROR:",
            repr(e)
        )

        cleanup_photo_paths(
            photo_paths
        )

        await state.clear()

        await message.answer(

            "Произошла ошибка при загрузке фотографий.\n\n"
            "Проверь логи Render."
        )


# =========================================================
# РУЧНАЯ КОМПЛЕКТАЦИЯ
# =========================================================

@dp.callback_query(
    InspectionForm.manual_equipment,
    F.data.in_([
        "eq_yes",
        "eq_no",
        "eq_skip"
    ])
)
async def manual_equipment_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    equipment_results = data.get(
        "equipment_results",
        {}
    )

    category = data.get(
        "manual_current_category"
    )

    option = data.get(
        "manual_current_option"
    )

    queue = data.get(
        "manual_equipment_queue",
        []
    )

    index = data.get(
        "manual_equipment_index",
        0
    )

    if (
        not category
        or not option
        or index >= len(queue)
    ):

        await callback.answer(
            "Проверка уже завершена.",
            show_alert=True
        )

        return

    # -----------------------------------------------------
    # Ответ пользователя
    # -----------------------------------------------------

    if callback.data == "eq_yes":

        value = "Есть"

    elif callback.data == "eq_no":

        value = "Нет"

    else:

        value = "—"

    # -----------------------------------------------------
    # Сохраняем
    # -----------------------------------------------------

    if category not in equipment_results:

        equipment_results[category] = {}

    equipment_results[
        category
    ][
        option
    ] = {

        "status":
            "Ручной ввод",

        "value":
            value,

        "evidence":
            ""
    }

    next_index = index + 1

    await state.update_data(

        equipment_results=
            equipment_results,

        manual_equipment_index=
            next_index
    )

    await callback.answer()

    # -----------------------------------------------------
    # Если ещё есть вопросы
    # -----------------------------------------------------

    if next_index < len(queue):

        next_item = queue[
            next_index
        ]

        next_category = next_item[
            "category"
        ]

        next_option = next_item[
            "option"
        ]

        await state.update_data(

            manual_current_category=
                next_category,

            manual_current_option=
                next_option
        )

        try:

            await callback.message.edit_reply_markup(
                reply_markup=None
            )

        except Exception:

            pass

        await callback.message.answer(

            f"ПРОВЕРКА КОМПЛЕКТАЦИИ\n\n"
            f"Раздел: {next_category}\n"
            f"Опция: {next_option}\n\n"
            f"Укажите результат:",

            reply_markup=
                manual_equipment_keyboard()
        )

        return

    # -----------------------------------------------------
    # Все пункты закончены
    # -----------------------------------------------------

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:

        pass

    await callback.message.answer(

        "Комплектация полностью заполнена.\n\n"
        "Формирую PDF-отчёт..."
    )

    await generate_and_send_report(
        callback.message,
        state
    )


# =========================================================
# ЕСЛИ ПРИ РУЧНОЙ ПРОВЕРКЕ ПРИШЁЛ ТЕКСТ
# =========================================================

@dp.message(
    InspectionForm.manual_equipment
)
async def manual_equipment_text_handler(
    message: types.Message
):

    await message.answer(

        "Используй кнопки под текущим пунктом:\n\n"
        "Есть / Нет / Пропустить."
    )


# =========================================================
# ЕСЛИ ВМЕСТО ФОТО ПРИШЁЛ ТЕКСТ
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
# RENDER HEALTH
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
        "MODE: MANUAL INSPECTION"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
