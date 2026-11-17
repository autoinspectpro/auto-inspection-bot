import os
import asyncio
import json
import sqlite3
import uuid
from io import BytesIO
from datetime import datetime
from typing import Any, Mapping

from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType
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

# Язык формируемого PDF: русский по умолчанию, немецкий для второго документа.
PDF_LANGUAGE = "ru"

PDF_DE_TRANSLATIONS = {
    "ЛИПГУС-ГРУП": "LIPGUS-GRUP",
    "АКТ ОСМОТРА АВТОМОБИЛЯ": "FAHRZEUGPRÜFBERICHT",
    "ОТЧЁТ ОБ ОСМОТРЕ": "FAHRZEUGPRÜFBERICHT",
    "АВТОМОБИЛЯ": "",
    "Профессиональный отчёт осмотра": "Professioneller Fahrzeugprüfbericht",
    "МАРКА": "MARKE", "МОДЕЛЬ": "MODELL", "ГОД ВЫПУСКА": "BAUJAHR",
    "ПРОБЕГ": "KILOMETERSTAND", "ТИП КУЗОВА": "KAROSSERIEFORM",
    "ЦВЕТ": "FARBE", "РАЗМЕР КОЛЁС": "RADGRÖSSE", "ПРИВОД": "ANTRIEB",
    "ТИП ДВИГАТЕЛЯ": "MOTORTYP", "ОБЪЁМ ДВИГАТЕЛЯ": "HUBRAUM",
    "МОЩНОСТЬ": "LEISTUNG", "КОРОБКА ПЕРЕДАЧ": "GETRIEBE",
    "Дата формирования отчёта": "Berichtsdatum", "Мастер осмотра": "Prüfer",
    "МАСТЕР ОСМОТРА": "FAHRZEUGPRÜFER", "ПОДПИСЬ / ПЕЧАТЬ": "UNTERSCHRIFT / STEMPEL",
    "КАРТА ЛАКОКРАСОЧНОГО ПОКРЫТИЯ": "LACKSCHICHTMESSUNG",
    "Измерения указаны в микрометрах (µm)": "Messwerte in Mikrometern (µm)",
    "Капот": "Motorhaube", "Крыша": "Dach", "Крышка багажника": "Kofferraumdeckel",
    "Переднее левое крыло": "Vorderer linker Kotflügel", "Передняя левая дверь": "Vordere linke Tür",
    "Задняя левая дверь": "Hintere linke Tür", "Заднее левое крыло": "Hinterer linker Kotflügel",
    "Переднее правое крыло": "Vorderer rechter Kotflügel", "Передняя правая дверь": "Vordere rechte Tür",
    "Задняя правая дверь": "Hintere rechte Tür", "Заднее правое крыло": "Hinterer rechter Kotflügel",
    "Все значения указаны в микрометрах (µm).": "Alle Werte sind in Mikrometern (µm) angegeben.",
    "КОМПЛЕКТАЦИЯ И ОСНАЩЕНИЕ": "AUSSTATTUNG",
    "Перечень оборудования автомобиля": "Fahrzeugausstattung",
    "ЭНДОСКОПИЯ ДВИГАТЕЛЯ": "MOTOR-ENDOSKOPIE",
    "Поршни": "Kolben", "Масляные следы": "Ölspuren", "Общее состояние": "Gesamtzustand",
    "Состояние цилиндров": "Zylinderzustand", "Состояние поршней": "Kolbenzustand",
    "Состояние стенок цилиндров": "Zustand der Zylinderwände",
    "Раздел эндоскопического осмотра": "Abschnitt zur endoskopischen Prüfung",
    "Параметр": "Parameter", "Результат": "Ergebnis", "Цилиндры": "Zylinder",
    "Стенки цилиндров": "Zylinderwände", "Поршни": "Kolben",
    "Задиры": "Riefen", "Нагар": "Kohlenstoffablagerungen", "Масло": "Öl",
    "ОПЦИЯ": "AUSSTATTUNG", "РЕЗУЛЬТАТ": "ERGEBNIS",
    "ЭКСТЕРЬЕР": "EXTERIEUR", "ИНТЕРЬЕР": "INTERIEUR", "КОМФОРТ": "KOMFORT",
    "МУЛЬТИМЕДИА": "MULTIMEDIA", "БЕЗОПАСНОСТЬ": "SICHERHEIT",
    "ДОПОЛНИТЕЛЬНЫЕ ОПЦИИ": "ZUSATZAUSSTATTUNG",
    "Тип кузова": "Karosserieform", "Цвет кузова": "Karosseriefarbe",
    "Тип лакокрасочного покрытия": "Lackart", "LED-фары": "LED-Scheinwerfer",
    "Ксеноновые фары": "Xenon-Scheinwerfer", "Галогенные фары": "Halogenscheinwerfer",
    "Матричные фары": "Matrix-Scheinwerfer", "Дневные ходовые огни": "Tagfahrlicht",
    "Автоматический дальний свет": "Fernlichtassistent", "Противотуманные фары": "Nebelscheinwerfer",
    "Омыватели фар": "Scheinwerferreinigungsanlage", "Датчик света": "Lichtsensor",
    "Датчик дождя": "Regensensor", "Электрорегулировка зеркал": "Elektrische Spiegelverstellung",
    "Обогрев зеркал": "Beheizbare Außenspiegel", "Электроскладывание зеркал": "Elektrisch anklappbare Spiegel",
    "Автозатемнение зеркала": "Automatisch abblendender Spiegel", "Панорамная крыша": "Panoramadach",
    "Люк": "Schiebedach", "Рейлинги": "Dachreling", "Спойлер": "Spoiler",
    "Размер колёс": "Radgröße", "Размер дисплея": "Displaygröße", "Тип дисков": "Felgentyp",
    "Материал сидений": "Sitzmaterial", "Цвет салона": "Innenraumfarbe", "Количество мест": "Sitzplätze",
    "Кожаный салон": "Lederausstattung", "Тканевый салон": "Stoffausstattung",
    "Спортивные сиденья": "Sportsitze", "Электрорегулировка сидений": "Elektrische Sitzverstellung",
    "Подогрев передних сидений": "Sitzheizung vorne", "Подогрев задних сидений": "Sitzheizung hinten",
    "Вентиляция сидений": "Sitzbelüftung", "Массаж сидений": "Massagefunktion der Sitze",
    "Подогрев руля": "Lenkradheizung", "Мультируль": "Multifunktionslenkrad",
    "Цифровая приборная панель": "Digitales Kombiinstrument", "Амбиентная подсветка": "Ambientebeleuchtung",
    "Кондиционер": "Klimaanlage", "Климат-контроль": "Klimaautomatik", "Двухзонный климат": "2-Zonen-Klimaautomatik",
    "Трёхзонный климат": "3-Zonen-Klimaautomatik", "Бесключевой доступ": "Keyless Entry",
    "Запуск двигателя кнопкой": "Motorstart per Knopfdruck", "Круиз-контроль": "Tempomat",
    "Адаптивный круиз-контроль": "Adaptiver Tempomat", "Электропривод окон": "Elektrische Fensterheber",
    "Центральный замок": "Zentralverriegelung", "Подогрев лобового стекла": "Beheizbare Windschutzscheibe",
    "Беспроводная зарядка": "Kabelloses Laden", "Камера заднего вида": "Rückfahrkamera",
    "Камеры 360°": "360°-Kameras", "Передние парктроники": "Einparkhilfe vorne",
    "Задние парктроники": "Einparkhilfe hinten", "Контроль слепых зон": "Totwinkelassistent",
    "Предупреждение о столкновении": "Kollisionswarnung", "Автоматическое экстренное торможение": "Notbremsassistent",
    "Контроль полосы движения": "Spurüberwachung", "Удержание в полосе": "Spurhalteassistent",
    "Распознавание дорожных знаков": "Verkehrszeichenerkennung", "Контроль давления в шинах": "Reifendruckkontrolle",
    "Есть": "Vorhanden", "Нет": "Nein", "Не заполнено": "Nicht ausgefüllt",
    "Ручной ввод": "Manuelle Eingabe", "Заполнено": "Ausgefüllt",
    "Бензин": "Benzin", "Дизель": "Diesel", "Гибрид": "Hybrid", "Электро": "Elektro",
    "МКПП": "Schaltgetriebe", "АКПП": "Automatik", "Робот": "Doppelkupplungsgetriebe", "Вариатор": "CVT",
    " л.с.": " PS", " л": " l", " км": " km", "Страница ": "Seite ",
}

def pdf_translate(value):
    if PDF_LANGUAGE != "de" or not isinstance(value, str):
        return value
    result = value
    for ru, de in sorted(PDF_DE_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(ru, de)
    return result

_original_Paragraph = Paragraph
_original_Table = Table
def Paragraph(*args, **kwargs):
    args = list(args)
    if args and isinstance(args[0], str):
        args[0] = pdf_translate(args[0])
    return _original_Paragraph(*args, **kwargs)

def _translate_table_data(value):
    if isinstance(value, str):
        return pdf_translate(value)
    if isinstance(value, list):
        return [_translate_table_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_translate_table_data(item) for item in value)
    return value

def Table(*args, **kwargs):
    args = list(args)
    if args:
        args[0] = _translate_table_data(args[0])
    return _original_Table(*args, **kwargs)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# =========================================================
# НАСТРОЙКИ
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

# Для Render рекомендуется задать:
# YURMAX_DB_PATH=/var/data/yurmax_bot.db
#
# Если переменная не задана — база будет создана рядом с main.py.
DB_PATH = os.getenv(
    "YURMAX_DB_PATH",
    "yurmax_bot.db"
)

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


# =========================================================
# SQLITE PERSISTENT FSM
# =========================================================

class SQLiteStorage(BaseStorage):

    def __init__(self, db_path: str):
        self.db_path = db_path

        directory = os.path.dirname(
            os.path.abspath(db_path)
        )

        os.makedirs(
            directory,
            exist_ok=True
        )

        self._init_db()

    def _connect(self):
        connection = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False
        )

        connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        connection.execute(
            "PRAGMA busy_timeout=30000"
        )

        return connection

    def _init_db(self):

        connection = self._connect()

        try:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS fsm_storage (
                    storage_key TEXT PRIMARY KEY,
                    state TEXT,
                    data TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.commit()

        finally:

            connection.close()

    @staticmethod
    def _make_key(
        key: StorageKey
    ) -> str:

        return json.dumps(
            {
                "bot_id": key.bot_id,
                "chat_id": key.chat_id,
                "user_id": key.user_id,
                "thread_id": key.thread_id,
                "business_connection_id":
                    key.business_connection_id,
                "destiny": key.destiny,
            },
            sort_keys=True,
            ensure_ascii=False
        )

    @staticmethod
    def _resolve_state(
        state: StateType
    ):

        if state is None:
            return None

        if isinstance(state, State):
            return state.state

        return str(state)

    async def set_state(
        self,
        key: StorageKey,
        state: StateType = None
    ) -> None:

        storage_key = self._make_key(key)
        resolved_state = self._resolve_state(state)

        connection = self._connect()

        try:

            cursor = connection.execute(
                """
                SELECT data
                FROM fsm_storage
                WHERE storage_key = ?
                """,
                (storage_key,)
            )

            row = cursor.fetchone()

            now = datetime.utcnow().isoformat()

            if row:

                connection.execute(
                    """
                    UPDATE fsm_storage
                    SET state = ?,
                        updated_at = ?
                    WHERE storage_key = ?
                    """,
                    (
                        resolved_state,
                        now,
                        storage_key
                    )
                )

            else:

                connection.execute(
                    """
                    INSERT INTO fsm_storage
                    (
                        storage_key,
                        state,
                        data,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        storage_key,
                        resolved_state,
                        "{}",
                        now
                    )
                )

            connection.commit()

        finally:

            connection.close()

    async def get_state(
        self,
        key: StorageKey
    ):

        storage_key = self._make_key(key)

        connection = self._connect()

        try:

            cursor = connection.execute(
                """
                SELECT state
                FROM fsm_storage
                WHERE storage_key = ?
                """,
                (storage_key,)
            )

            row = cursor.fetchone()

            if not row:
                return None

            return row[0]

        finally:

            connection.close()

    async def set_data(
        self,
        key: StorageKey,
        data: Mapping[str, Any]
    ) -> None:

        if not isinstance(data, Mapping):
            raise TypeError(
                "FSM data must be a mapping"
            )

        storage_key = self._make_key(key)

        serialized = json.dumps(
            dict(data),
            ensure_ascii=False
        )

        connection = self._connect()

        try:

            cursor = connection.execute(
                """
                SELECT state
                FROM fsm_storage
                WHERE storage_key = ?
                """,
                (storage_key,)
            )

            row = cursor.fetchone()

            now = datetime.utcnow().isoformat()

            if row:

                connection.execute(
                    """
                    UPDATE fsm_storage
                    SET data = ?,
                        updated_at = ?
                    WHERE storage_key = ?
                    """,
                    (
                        serialized,
                        now,
                        storage_key
                    )
                )

            else:

                connection.execute(
                    """
                    INSERT INTO fsm_storage
                    (
                        storage_key,
                        state,
                        data,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        storage_key,
                        None,
                        serialized,
                        now
                    )
                )

            connection.commit()

        finally:

            connection.close()

    async def get_data(
        self,
        key: StorageKey
    ) -> dict:

        storage_key = self._make_key(key)

        connection = self._connect()

        try:

            cursor = connection.execute(
                """
                SELECT data
                FROM fsm_storage
                WHERE storage_key = ?
                """,
                (storage_key,)
            )

            row = cursor.fetchone()

            if not row or not row[0]:
                return {}

            try:

                data = json.loads(
                    row[0]
                )

                if isinstance(data, dict):
                    return data

            except Exception:

                pass

            return {}

        finally:

            connection.close()

    async def update_data(
        self,
        key: StorageKey,
        data: Mapping[str, Any]
    ) -> dict:

        current = await self.get_data(key)

        current.update(
            dict(data)
        )

        await self.set_data(
            key,
            current
        )

        return current.copy()

    async def close(self) -> None:
        pass


# =========================================================
# BOT
# =========================================================

bot = Bot(TOKEN)

dp = Dispatcher(
    storage=SQLiteStorage(
        DB_PATH
    )
)


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
    drive = State()
    paint_type = State()
    display_size = State()

    seat_material = State()
    wheel_type = State()
    interior_color = State()
    seat_count = State()
    audio_system_name = State()
    speaker_count = State()

    engine_type = State()
    engine_volume = State()
    engine_hp = State()
    gearbox = State()

    lkp = State()

    photos = State()

    manual_equipment = State()

    endoscopy_cylinders = State()
    endoscopy_cylinder_walls = State()
    endoscopy_pistons = State()
    endoscopy_scoring = State()
    endoscopy_carbon = State()
    endoscopy_oil = State()
    endoscopy_overall = State()

    review = State()
    edit_menu = State()


# =========================================================
# ТЕКСТЫ КНОПОК
# =========================================================

BACK_TEXT = "⬅️ Назад"
MENU_TEXT = "🏠 Меню"
CREATE_TEXT = "Создать акт"
CONTINUE_TEXT = "▶️ Продолжить акт"
NEW_TEXT = "🆕 Новый акт"


# =========================================================
# КЛАВИАТУРЫ
# =========================================================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text=CREATE_TEXT
            )
        ],
        [
            KeyboardButton(
                text=CONTINUE_TEXT
            )
        ]
    ],
    resize_keyboard=True
)


back_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text=BACK_TEXT
            ),
            KeyboardButton(
                text=MENU_TEXT
            )
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
        ],
        [
            KeyboardButton(text=BACK_TEXT),
            KeyboardButton(text=MENU_TEXT)
        ]
    ],
    resize_keyboard=True
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
        ],
        [
            KeyboardButton(text=BACK_TEXT),
            KeyboardButton(text=MENU_TEXT)
        ]
    ],
    resize_keyboard=True
)


finish_photos_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="Готово"
            )
        ],
        [
            KeyboardButton(
                text=BACK_TEXT
            ),
            KeyboardButton(
                text=MENU_TEXT
            )
        ]
    ],
    resize_keyboard=True
)


endoscopy_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text=BACK_TEXT
            ),
            KeyboardButton(
                text=MENU_TEXT
            )
        ]
    ],
    resize_keyboard=True
)


# =========================================================
# INLINE — РУЧНАЯ КОМПЛЕКТАЦИЯ
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
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="eq_back"
                )
            ]
        ]
    )


# =========================================================
# INLINE — ПОДТВЕРЖДЕНИЕ НОВОГО АКТА
# =========================================================

def new_report_confirm_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆕 Начать новый",
                    callback_data="new_confirm"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="new_cancel"
                )
            ]
        ]
    )


# =========================================================
# INLINE — ФИНАЛЬНЫЙ ПРОСМОТР
# =========================================================

def review_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data="review_edit"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📄 Создать PDF",
                    callback_data="review_pdf"
                )
            ]
        ]
    )


def edit_menu_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚗 Данные автомобиля",
                    callback_data="edit_car"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎨 ЛКП",
                    callback_data="edit_lkp"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📷 Фотографии",
                    callback_data="edit_photos"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧰 Комплектация",
                    callback_data="edit_equipment"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔬 Эндоскопия",
                    callback_data="edit_endoscopy"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="edit_back"
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
        "Тип лакокрасочного покрытия",
        "Размер дисплея",
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
# РУЧНАЯ ПРОВЕРКА КОМПЛЕКТАЦИИ
# =========================================================

def build_manual_equipment_queue():

    queue = []

    direct_fields = {
        "Тип кузова",
        "Цвет кузова",
        "Размер колёс",
        "Тип лакокрасочного покрытия",
        "Размер дисплея",
        "Тип дисков",
        "Материал сидений",
        "Цвет салона",
        "Количество мест",
        "Название аудиосистемы",
        "Количество динамиков",
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


def create_empty_equipment_results(
    body_type,
    body_color,
    wheel_radius,
    paint_type,
    display_size,
    seat_material,
    wheel_type,
    interior_color,
    seat_count,
    audio_system_name,
    speaker_count
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

    direct_values = {
        (
            "ЭКСТЕРЬЕР",
            "Тип лакокрасочного покрытия"
        ): paint_type,

        (
            "МУЛЬТИМЕДИА",
            "Размер дисплея"
        ): display_size,

        (
            "ЭКСТЕРЬЕР",
            "Тип дисков"
        ): wheel_type,

        (
            "ИНТЕРЬЕР",
            "Материал сидений"
        ): seat_material,

        (
            "ИНТЕРЬЕР",
            "Цвет салона"
        ): interior_color,

        (
            "ИНТЕРЬЕР",
            "Количество мест"
        ): seat_count,

        (
            "МУЛЬТИМЕДИА",
            "Название аудиосистемы"
        ): audio_system_name,

        (
            "МУЛЬТИМЕДИА",
            "Количество динамиков"
        ): speaker_count,
    }

    for (
        category,
        option
    ), value in direct_values.items():

        results[category][option] = {
            "status": "Ручной ввод",
            "value": value,
            "evidence": ""
        }

    return results


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

    total = len(queue)

    await message.answer(

        f"🧰 ПРОВЕРКА КОМПЛЕКТАЦИИ\n\n"
        f"Позиция: {index + 1} из {total}\n"
        f"Раздел: {category}\n"
        f"Опция: {option}\n\n"
        f"Укажите результат:",

        reply_markup=manual_equipment_keyboard()
    )

    return True


# =========================================================
# ПРОГРЕСС
# =========================================================

FORM_STATES = [
    InspectionForm.master_name.state,
    InspectionForm.report_date.state,
    InspectionForm.make.state,
    InspectionForm.model.state,
    InspectionForm.year.state,
    InspectionForm.vin.state,
    InspectionForm.mileage.state,
    InspectionForm.body_type.state,
    InspectionForm.body_color.state,
    InspectionForm.wheel_radius.state,
    InspectionForm.drive.state,
    InspectionForm.paint_type.state,
    InspectionForm.display_size.state,
    InspectionForm.seat_material.state,
    InspectionForm.wheel_type.state,
    InspectionForm.interior_color.state,
    InspectionForm.seat_count.state,
    InspectionForm.audio_system_name.state,
    InspectionForm.speaker_count.state,
    InspectionForm.engine_type.state,
    InspectionForm.engine_volume.state,
    InspectionForm.engine_hp.state,
    InspectionForm.gearbox.state,
    InspectionForm.lkp.state,
    InspectionForm.photos.state,
    InspectionForm.manual_equipment.state,
    InspectionForm.endoscopy_cylinders.state,
    InspectionForm.endoscopy_cylinder_walls.state,
    InspectionForm.endoscopy_pistons.state,
    InspectionForm.endoscopy_scoring.state,
    InspectionForm.endoscopy_carbon.state,
    InspectionForm.endoscopy_oil.state,
    InspectionForm.endoscopy_overall.state,
]


def progress_text(
    current_state: str
):

    if current_state not in FORM_STATES:
        return ""

    index = FORM_STATES.index(
        current_state
    )

    current = index + 1
    total = len(FORM_STATES)

    width = 12

    filled = int(
        width * current / total
    )

    filled = max(
        1,
        min(
            filled,
            width
        )
    )

    bar = (
        "█" * filled
        + "░" * (width - filled)
    )

    return (
        f"{bar}\n"
        f"Шаг {current} из {total}"
    )


# =========================================================
# ШРИФТЫ
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
        pdf_translate("КАРТА ЛАКОКРАСОЧНОГО ПОКРЫТИЯ"),
        font=title_font,
        fill=(255, 255, 255)
    )

    draw.text(
        (60, 110),
        pdf_translate("ЛИПГУС-ГРУП"),
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
            pdf_translate(text),
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
        pdf_translate("Измерения указаны в микрометрах (µm)"),
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
        pdf_translate("ЛИПГУС-ГРУП")
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
        pdf_translate("АКТ ОСМОТРА АВТОМОБИЛЯ")
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
        pdf_translate("ЛИПГУС-ГРУП")
    )

    canvas.drawRightString(
        width - 15 * mm,
        10 * mm,
        pdf_translate(f"Страница {doc.page}")
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
    equipment_results=None,
    endoscopy_data=None,
    language="ru"
):

    global PDF_LANGUAGE
    PDF_LANGUAGE = language

    if photo_paths is None:
        photo_paths = []

    if equipment_results is None:
        equipment_results = {}

    if endoscopy_data is None:
        endoscopy_data = {}

    output = BytesIO()

    doc = SimpleDocTemplate(

        output,

        pagesize=A4,

        rightMargin=15 * mm,

        leftMargin=15 * mm,

        topMargin=27 * mm,

        bottomMargin=18 * mm,

        title="ЛИПГУС-ГРУП — Акт осмотра автомобиля",

        author="ЛИПГУС-ГРУП",
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

            "ЛИПГУС-ГРУП",

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
            "ПРИВОД",
            car_data["drive"]
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
        "Дизель",
        "Гибрид",
        "Электро"
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

        endoscopy_rows = [

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
                endoscopy_data.get(
                    "cylinders",
                    "—"
                )
            ],

            [
                "Стенки цилиндров",
                endoscopy_data.get(
                    "cylinder_walls",
                    "—"
                )
            ],

            [
                "Поршни",
                endoscopy_data.get(
                    "pistons",
                    "—"
                )
            ],

            [
                "Следы задиров",
                endoscopy_data.get(
                    "scoring",
                    "—"
                )
            ],

            [
                "Следы нагара",
                endoscopy_data.get(
                    "carbon",
                    "—"
                )
            ],

            [
                "Следы масла",
                endoscopy_data.get(
                    "oil",
                    "—"
                )
            ],

            [
                "Общее состояние",
                endoscopy_data.get(
                    "overall",
                    "—"
                )
            ],
        ]

        endoscopy_table = Table(

            endoscopy_rows,

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

                if photo_index >= len(
                    photo_paths
                ):
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
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
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


async def send_prompt(
    message,
    state,
    text,
    reply_markup=back_keyboard
):

    current_state = await state.get_state()

    progress = progress_text(
        current_state
    )

    if progress:

        text = (
            f"{progress}\n\n"
            f"{text}"
        )

    await message.answer(
        text,
        reply_markup=reply_markup
    )


async def finish_or_continue_edit(
    message,
    state,
    next_state,
    prompt,
    reply_markup=back_keyboard
):

    data = await state.get_data()

    if data.get(
        "edit_return_to_review"
    ):

        await state.update_data(
            edit_return_to_review=False
        )

        await state.set_state(
            InspectionForm.review
        )

        await show_review(
            message,
            state
        )

        return True

    await state.set_state(
        next_state
    )

    await send_prompt(
        message,
        state,
        prompt,
        reply_markup
    )

    return False


async def show_review(
    message,
    state
):

    data = await state.get_data()

    make = data.get(
        "make",
        "—"
    )

    model = data.get(
        "model",
        "—"
    )

    year = data.get(
        "year",
        "—"
    )

    vin = data.get(
        "vin",
        "—"
    )

    mileage = data.get(
        "mileage",
        "—"
    )

    measurements = data.get(
        "measurements",
        {}
    )

    photos = data.get(
        "photos",
        []
    )

    queue = data.get(
        "manual_equipment_queue",
        []
    )

    equipment_results = data.get(
        "equipment_results",
        {}
    )

    endoscopy = data.get(
        "endoscopy_data",
        {}
    )

    completed_equipment = 0

    for category in equipment_results.values():

        if not isinstance(
            category,
            dict
        ):
            continue

        for item in category.values():

            if item.get(
                "status"
            ) == "Ручной ввод":

                completed_equipment += 1

    review_text = (

        "📋 <b>ПРОВЕРКА АКТА</b>\n\n"

        f"🚗 <b>{make} {model}</b>\n"
        f"Год: {year}\n"
        f"VIN: {vin}\n"
        f"Пробег: {mileage} км\n\n"

        f"🎨 ЛКП: "
        f"{len(measurements)}/{len(LKP_PARTS)} замеров\n"

        f"📷 Фотографии: "
        f"{len(photos)}\n"

        f"🧰 Комплектация: "
        f"{completed_equipment}/{len(queue)}\n"

        f"🔬 Эндоскопия: "
        f"{len(endoscopy)}/7\n\n"

        "Перед созданием PDF можно изменить любой раздел."
    )

    await state.set_state(
        InspectionForm.review
    )

    await message.answer(
        review_text,
        parse_mode="HTML",
        reply_markup=review_keyboard()
    )


async def download_report_photos(
    photo_ids
):

    paths = []

    for number, file_id in enumerate(
        photo_ids,
        start=1
    ):

        file = await bot.get_file(
            file_id
        )

        unique_name = (
            f"lipgus_grup_"
            f"{uuid.uuid4().hex}_"
            f"{number}.jpg"
        )

        path = os.path.join(
            "/tmp",
            unique_name
        )

        await bot.download_file(
            file.file_path,
            path
        )

        paths.append(
            path
        )

    return paths


async def generate_and_send_report(
    message,
    state
):

    data = await state.get_data()

    photo_ids = data.get(
        "photos",
        []
    )

    photo_paths = []

    try:

        await message.answer(
            "⏳ Формирую PDF-отчёт..."
        )

        photo_paths = await download_report_photos(
            photo_ids
        )

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

            "drive":
                data["drive"],

            "engine_type":
                data["engine_type"],

            "engine_volume":
                data["engine_volume"],

            "engine_hp":
                data["engine_hp"],

            "gearbox":
                data["gearbox"],
        }

        report_args = dict(
            car_data=car_data,
            measurements=data["measurements"],
            master_name=data["master_name"],
            report_date=data["report_date"],
            photo_paths=photo_paths,
            equipment_results=data.get("equipment_results", {}),
            endoscopy_data=data.get("endoscopy_data", {})
        )

        for language, language_suffix in (("ru", "RU"), ("de", "DE")):
            pdf = create_pdf(**report_args, language=language)
            filename = (
                f"LIPGUS_GRUP_{language_suffix}_"
                f"{data['make']}_{data['model']}_AKT_OSMOTRA.pdf"
            )
            filename = filename.replace("/", "_").replace("\\", "_")
            await message.answer_document(
                types.BufferedInputFile(pdf.getvalue(), filename=filename)
            )

        PDF_LANGUAGE = "ru"

        await message.answer(

            "✅ <b>Готово!</b>\n\n"
            "PDF-отчёты ЛИПГУС-ГРУП сформированы.",

            parse_mode="HTML",

            reply_markup=main_keyboard
        )

        # Очищаем FSM ТОЛЬКО после успешного создания
        # и отправки PDF.
        await state.clear()

    except Exception as e:

        PDF_LANGUAGE = "ru"
        print(
            "PDF ERROR:",
            repr(e)
        )

        await message.answer(

            "❌ Произошла ошибка при формировании PDF.\n\n"
            "Данные акта сохранены.\n"
            "Можно повторить попытку — ничего вводить заново не нужно.",

            reply_markup=main_keyboard
        )

    finally:

        cleanup_photo_paths(
            photo_paths
        )


# =========================================================
# PROMPT ПО ТЕКУЩЕМУ STATE
# =========================================================

async def show_current_state_prompt(
    message,
    state
):

    current = await state.get_state()

    data = await state.get_data()

    if current is None:

        paused = data.get(
            "paused_state"
        )

        if paused:

            await state.set_state(
                paused
            )

            current = paused

        else:

            await message.answer(
                "Активного шага нет.",
                reply_markup=main_keyboard
            )

            return

    if current == InspectionForm.master_name.state:

        await send_prompt(
            message,
            state,
            "Введите имя мастера осмотра."
        )

    elif current == InspectionForm.report_date.state:

        await send_prompt(
            message,
            state,
            "Введите дату формирования отчёта.\n\n"
            "Формат: ДД.ММ.ГГГГ"
        )

    elif current == InspectionForm.make.state:

        await send_prompt(
            message,
            state,
            "Введите марку автомобиля."
        )

    elif current == InspectionForm.model.state:

        await send_prompt(
            message,
            state,
            "Введите модель автомобиля."
        )

    elif current == InspectionForm.year.state:

        await send_prompt(
            message,
            state,
            "Введите год выпуска."
        )

    elif current == InspectionForm.vin.state:

        await send_prompt(
            message,
            state,
            "Введите VIN автомобиля."
        )

    elif current == InspectionForm.mileage.state:

        await send_prompt(
            message,
            state,
            "Введите пробег автомобиля в километрах."
        )

    elif current == InspectionForm.body_type.state:

        await send_prompt(
            message,
            state,
            "Введите тип кузова."
        )

    elif current == InspectionForm.body_color.state:

        await send_prompt(
            message,
            state,
            "Введите цвет автомобиля."
        )

    elif current == InspectionForm.wheel_radius.state:

        await send_prompt(
            message,
            state,
            "Введите радиус колёс.\n\n"
            "Например: R18"
        )

    elif current == InspectionForm.drive.state:

        await send_prompt(
            message,
            state,
            "Введите привод автомобиля.\n\n"
            "Например: Передний / Задний / 4х4"
        )

    elif current == InspectionForm.paint_type.state:

        await send_prompt(
            message,
            state,
            "Введите тип лакокрасочного покрытия."
        )

    elif current == InspectionForm.display_size.state:

        await send_prompt(
            message,
            state,
            "Введите размер дисплея."
        )

    elif current == InspectionForm.seat_material.state:

        await send_prompt(
            message,
            state,
            "Введите материал сидений."
        )

    elif current == InspectionForm.wheel_type.state:

        await send_prompt(
            message,
            state,
            "Введите тип дисков."
        )

    elif current == InspectionForm.interior_color.state:

        await send_prompt(
            message,
            state,
            "Введите цвет салона."
        )

    elif current == InspectionForm.seat_count.state:

        await send_prompt(
            message,
            state,
            "Введите количество мест."
        )

    elif current == InspectionForm.audio_system_name.state:

        await send_prompt(
            message,
            state,
            "Введите название аудиосистемы."
        )

    elif current == InspectionForm.speaker_count.state:

        await send_prompt(
            message,
            state,
            "Введите количество динамиков."
        )

    elif current == InspectionForm.engine_type.state:

        await send_prompt(
            message,
            state,
            "Выберите тип двигателя.",
            engine_keyboard
        )

    elif current == InspectionForm.engine_volume.state:

        await send_prompt(
            message,
            state,
            "Введите объём двигателя в литрах."
        )

    elif current == InspectionForm.engine_hp.state:

        await send_prompt(
            message,
            state,
            "Введите мощность двигателя в л.с."
        )

    elif current == InspectionForm.gearbox.state:

        await send_prompt(
            message,
            state,
            "Выберите коробку передач.",
            gearbox_keyboard
        )

    elif current == InspectionForm.lkp.state:

        index = data.get(
            "lkp_index",
            0
        )

        index = max(
            0,
            min(
                index,
                len(LKP_PARTS) - 1
            )
        )

        await send_prompt(
            message,
            state,
            f"Введите толщину ЛКП.\n\n"
            f"Деталь: {LKP_PARTS[index]}\n\n"
            f"Например: 145"
        )

    elif current == InspectionForm.photos.state:

        await send_prompt(
            message,
            state,
            f"📷 Фотографии\n\n"
            f"Сейчас сохранено: "
            f"{len(data.get('photos', []))}\n\n"
            f"Отправляйте фотографии.\n"
            f"После этого нажмите «Готово».",
            finish_photos_keyboard
        )

    elif current == InspectionForm.manual_equipment.state:

        await ask_next_manual_equipment(
            message,
            state
        )

    elif current == InspectionForm.endoscopy_cylinders.state:

        await send_prompt(
            message,
            state,
            "1/7. Введите результат по цилиндрам.",
            endoscopy_keyboard
        )

    elif current == InspectionForm.endoscopy_cylinder_walls.state:

        await send_prompt(
            message,
            state,
            "2/7. Опишите стенки цилиндров.",
            endoscopy_keyboard
        )

    elif current == InspectionForm.endoscopy_pistons.state:

        await send_prompt(
            message,
            state,
            "3/7. Опишите состояние поршней.",
            endoscopy_keyboard
        )

    elif current == InspectionForm.endoscopy_scoring.state:

        await send_prompt(
            message,
            state,
            "4/7. Опишите наличие или отсутствие задиров.",
            endoscopy_keyboard
        )

    elif current == InspectionForm.endoscopy_carbon.state:

        await send_prompt(
            message,
            state,
            "5/7. Опишите наличие или отсутствие нагара.",
            endoscopy_keyboard
        )

    elif current == InspectionForm.endoscopy_oil.state:

        await send_prompt(
            message,
            state,
            "6/7. Опишите наличие или отсутствие масла.",
            endoscopy_keyboard
        )

    elif current == InspectionForm.endoscopy_overall.state:

        await send_prompt(
            message,
            state,
            "7/7. Введите общее состояние двигателя.",
            endoscopy_keyboard
        )

    elif current == InspectionForm.review.state:

        await show_review(
            message,
            state
        )


# =========================================================
# НАЗАД — КАРТА ПРЕДЫДУЩИХ СОСТОЯНИЙ
# =========================================================

PREVIOUS_STATES = {

    InspectionForm.report_date.state:
        InspectionForm.master_name.state,

    InspectionForm.make.state:
        InspectionForm.report_date.state,

    InspectionForm.model.state:
        InspectionForm.make.state,

    InspectionForm.year.state:
        InspectionForm.model.state,

    InspectionForm.vin.state:
        InspectionForm.year.state,

    InspectionForm.mileage.state:
        InspectionForm.vin.state,

    InspectionForm.body_type.state:
        InspectionForm.mileage.state,

    InspectionForm.body_color.state:
        InspectionForm.body_type.state,

    InspectionForm.wheel_radius.state:
        InspectionForm.body_color.state,

    InspectionForm.drive.state:
        InspectionForm.wheel_radius.state,

    InspectionForm.paint_type.state:
        InspectionForm.drive.state,

    InspectionForm.display_size.state:
        InspectionForm.paint_type.state,

    InspectionForm.seat_material.state:
        InspectionForm.display_size.state,

    InspectionForm.wheel_type.state:
        InspectionForm.seat_material.state,

    InspectionForm.interior_color.state:
        InspectionForm.wheel_type.state,

    InspectionForm.seat_count.state:
        InspectionForm.interior_color.state,

    InspectionForm.audio_system_name.state:
        InspectionForm.seat_count.state,

    InspectionForm.speaker_count.state:
        InspectionForm.audio_system_name.state,

    InspectionForm.engine_type.state:
        InspectionForm.speaker_count.state,

    InspectionForm.engine_volume.state:
        InspectionForm.engine_type.state,

    InspectionForm.engine_hp.state:
        InspectionForm.engine_volume.state,

    InspectionForm.gearbox.state:
        InspectionForm.engine_hp.state,
}


# =========================================================
# МЕНЮ
# =========================================================

@dp.message(
    F.text == MENU_TEXT
)
async def menu_handler(
    message: types.Message,
    state: FSMContext
):

    current = await state.get_state()

    if current:

        await state.update_data(
            paused_state=current,
            draft_active=True
        )

        await state.set_state(
            None
        )

    data = await state.get_data()

    if data.get(
        "draft_active"
    ):

        await message.answer(

            "🏠 <b>Меню ЛИПГУС-ГРУП</b>\n\n"
            "У тебя есть незавершённый акт.\n"
            "Данные сохранены.",

            parse_mode="HTML",

            reply_markup=main_keyboard
        )

    else:

        await message.answer(

            "🏠 <b>Меню ЛИПГУС-ГРУП</b>\n\n"
            "Можно создать новый акт.",

            parse_mode="HTML",

            reply_markup=main_keyboard
        )


# =========================================================
# НАЗАД
# =========================================================

@dp.message(
    F.text == BACK_TEXT
)
async def back_handler(
    message: types.Message,
    state: FSMContext
):

    current = await state.get_state()

    data = await state.get_data()

    if not current:

        paused = data.get(
            "paused_state"
        )

        if paused:

            await state.set_state(
                paused
            )

            await show_current_state_prompt(
                message,
                state
            )

        else:

            await message.answer(
                "Ты находишься в главном меню.",
                reply_markup=main_keyboard
            )

        return

    # -----------------------------------------------------
    # Если редактируем готовый акт
    # -----------------------------------------------------

    if data.get(
        "edit_return_to_review"
    ):

        await state.update_data(
            edit_return_to_review=False
        )

        await state.set_state(
            InspectionForm.review
        )

        await show_review(
            message,
            state
        )

        return

    # -----------------------------------------------------
    # ЛКП
    # -----------------------------------------------------

    if current == InspectionForm.lkp.state:

        index = data.get(
            "lkp_index",
            0
        )

        if index > 0:

            index -= 1

            await state.update_data(
                lkp_index=index
            )

            await message.answer(

                f"Возвращаемся.\n\n"
                f"Деталь: {LKP_PARTS[index]}\n\n"
                f"Введите значение ЛКП:",

                reply_markup=back_keyboard
            )

        else:

            await state.set_state(
                InspectionForm.gearbox
            )

            await message.answer(
                "Возвращаемся к коробке передач.",
                reply_markup=gearbox_keyboard
            )

        return

    # -----------------------------------------------------
    # ФОТО
    # -----------------------------------------------------

    if current == InspectionForm.photos.state:

        await state.set_state(
            InspectionForm.lkp.state
        )

        await state.update_data(
            lkp_index=len(LKP_PARTS) - 1
        )

        await message.answer(

            f"Возвращаемся к ЛКП.\n\n"
            f"Деталь: {LKP_PARTS[-1]}\n\n"
            f"Введите значение:",

            reply_markup=back_keyboard
        )

        return

    # -----------------------------------------------------
    # РУЧНАЯ КОМПЛЕКТАЦИЯ
    # -----------------------------------------------------

    if current == InspectionForm.manual_equipment.state:

        index = data.get(
            "manual_equipment_index",
            0
        )

        if index > 0:

            index -= 1

            queue = data.get(
                "manual_equipment_queue",
                []
            )

            await state.update_data(
                manual_equipment_index=index
            )

            if index < len(queue):

                item = queue[index]

                await state.update_data(
                    manual_current_category=
                        item["category"],
                    manual_current_option=
                        item["option"]
                )

                await ask_next_manual_equipment(
                    message,
                    state
                )

        else:

            await state.set_state(
                InspectionForm.photos.state
            )

            await message.answer(
                "Возвращаемся к фотографиям.",
                reply_markup=finish_photos_keyboard
            )

        return

    # -----------------------------------------------------
    # ЭНДОСКОПИЯ
    # -----------------------------------------------------

    endoscopy_states = [
        InspectionForm.endoscopy_cylinders.state,
        InspectionForm.endoscopy_cylinder_walls.state,
        InspectionForm.endoscopy_pistons.state,
        InspectionForm.endoscopy_scoring.state,
        InspectionForm.endoscopy_carbon.state,
        InspectionForm.endoscopy_oil.state,
        InspectionForm.endoscopy_overall.state,
    ]

    if current in endoscopy_states:

        index = endoscopy_states.index(
            current
        )

        if index > 0:

            previous = endoscopy_states[
                index - 1
            ]

            await state.set_state(
                previous
            )

            await show_current_state_prompt(
                message,
                state
            )

        else:

            queue = data.get(
                "manual_equipment_queue",
                []
            )

            await state.update_data(
                manual_equipment_index=max(
                    0,
                    len(queue) - 1
                ),
                endoscopy_resume_state=
                    InspectionForm.endoscopy_cylinders.state
            )

            await state.set_state(
                InspectionForm.manual_equipment
            )

            await ask_next_manual_equipment(
                message,
                state
            )

        return

    # -----------------------------------------------------
    # REVIEW
    # -----------------------------------------------------

    if current == InspectionForm.review.state:

        await message.answer(
            "Выберите действие ниже.",
            reply_markup=review_keyboard()
        )

        return

    # -----------------------------------------------------
    # EDIT MENU
    # -----------------------------------------------------

    if current == InspectionForm.edit_menu.state:

        await state.set_state(
            InspectionForm.review
        )

        await show_review(
            message,
            state
        )

        return

    # -----------------------------------------------------
    # ОБЫЧНЫЕ ПОЛЯ
    # -----------------------------------------------------

    previous = PREVIOUS_STATES.get(
        current
    )

    if previous:

        await state.set_state(
            previous
        )

        await show_current_state_prompt(
            message,
            state
        )

        return

    await message.answer(
        "Назад на этом шаге недоступно.",
        reply_markup=back_keyboard
    )


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

    current = await state.get_state()
    data = await state.get_data()

    if current:

        await message.answer(

            "🔄 <b>Продолжаем незавершённый акт.</b>\n\n"
            "Все ранее введённые данные сохранены.",

            parse_mode="HTML"
        )

        await show_current_state_prompt(
            message,
            state
        )

        return

    paused = data.get(
        "paused_state"
    )

    if data.get(
        "draft_active"
    ) and paused:

        await state.set_state(
            paused
        )

        await message.answer(

            "🔄 <b>Найден незавершённый акт.</b>\n\n"
            "Продолжаем с того места, где остановились.",

            parse_mode="HTML"
        )

        await show_current_state_prompt(
            message,
            state
        )

        return

    await message.answer(

        "Добро пожаловать в ЛИПГУС-ГРУП.\n\n"
        "Здесь можно сформировать "
        "профессиональный отчёт осмотра автомобиля.\n\n"
        "Все данные сохраняются автоматически.",

        reply_markup=main_keyboard
    )


# =========================================================
# ПРОДОЛЖИТЬ
# =========================================================

@dp.message(
    F.text == CONTINUE_TEXT
)
async def continue_handler(
    message: types.Message,
    state: FSMContext
):

    data = await state.get_data()

    paused = data.get(
        "paused_state"
    )

    current = await state.get_state()

    if current:

        await show_current_state_prompt(
            message,
            state
        )

        return

    if not paused:

        await message.answer(
            "Незавершённого акта нет.",
            reply_markup=main_keyboard
        )

        return

    await state.set_state(
        paused
    )

    await show_current_state_prompt(
        message,
        state
    )


# =========================================================
# СОЗДАТЬ АКТ
# =========================================================

@dp.message(
    F.text == CREATE_TEXT
)
async def create_handler(
    message: types.Message,
    state: FSMContext
):

    data = await state.get_data()

    if data.get(
        "draft_active"
    ):

        await message.answer(

            "⚠️ У тебя уже есть незавершённый акт.\n\n"
            "Если начать новый, текущий черновик будет удалён.\n\n"
            "Продолжить текущий акт можно кнопкой "
            "«▶️ Продолжить акт».",

            reply_markup=new_report_confirm_keyboard()
        )

        return

    await start_new_report(
        message,
        state
    )


# =========================================================
# НОВЫЙ АКТ
# =========================================================

@dp.message(
    Command("new")
)
async def new_command(
    message: types.Message,
    state: FSMContext
):

    await start_new_report(
        message,
        state
    )


async def start_new_report(
    message,
    state
):

    await state.clear()

    await state.update_data(
        draft_active=True
    )

    await state.set_state(
        InspectionForm.master_name
    )

    await message.answer(

        "🆕 <b>Новый акт ЛИПГУС-ГРУП</b>\n\n"
        "Введите имя мастера осмотра.\n\n"
        "Например: Ян Ковальский",

        parse_mode="HTML",

        reply_markup=back_keyboard
    )


# =========================================================
# ПОДТВЕРЖДЕНИЕ НОВОГО АКТА
# =========================================================

@dp.callback_query(
    F.data == "new_confirm"
)
async def new_confirm_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await start_new_report(
        callback.message,
        state
    )


@dp.callback_query(
    F.data == "new_cancel"
)
async def new_cancel_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.message.answer(
        "Текущий акт сохранён.",
        reply_markup=main_keyboard
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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.report_date,

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
            "Введите: ДД.ММ.ГГГГ"
        )

        return

    await state.update_data(
        report_date=report_date
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.make,

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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.model,

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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.year,

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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.vin,

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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.mileage,

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
            "Введите пробег только цифрами."
        )

        return

    await state.update_data(
        mileage=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.body_type,

        "Введите тип кузова.\n\n"
        "Например: Седан / Кроссовер / Минивэн"
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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.body_color,

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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.wheel_radius,

        "Введите радиус колёс.\n\n"
        "Например: R18"
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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.drive,

        "Введите привод автомобиля.\n\n"
        "Например: Передний / Задний / 4х4 / Полный привод"
    )


# =========================================================
# ПРИВОД
# =========================================================

@dp.message(
    InspectionForm.drive
)
async def drive_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите привод автомобиля."
        )

        return

    await state.update_data(
        drive=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.paint_type,

        "Введите тип лакокрасочного покрытия.\n\n"
        "Например: Металлик / Перламутр / Обычное покрытие"
    )


# =========================================================
# ЛКП ТИП
# =========================================================

@dp.message(
    InspectionForm.paint_type
)
async def paint_type_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите тип лакокрасочного покрытия."
        )

        return

    await state.update_data(
        paint_type=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.display_size,

        "Введите размер дисплея.\n\n"
        "Например: 10.25 дюйма"
    )


# =========================================================
# ДИСПЛЕЙ
# =========================================================

@dp.message(
    InspectionForm.display_size
)
async def display_size_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите размер дисплея."
        )

        return

    await state.update_data(
        display_size=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.seat_material,

        "Введите материал сидений.\n\n"
        "Например: Кожа / Алькантара / Ткань"
    )


# =========================================================
# МАТЕРИАЛ СИДЕНИЙ
# =========================================================

@dp.message(
    InspectionForm.seat_material
)
async def seat_material_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите материал сидений."
        )

        return

    await state.update_data(
        seat_material=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.wheel_type,

        "Введите тип дисков.\n\n"
        "Например: Легкосплавные / Штампованные / Кованые"
    )


# =========================================================
# ТИП ДИСКОВ
# =========================================================

@dp.message(
    InspectionForm.wheel_type
)
async def wheel_type_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите тип дисков."
        )

        return

    await state.update_data(
        wheel_type=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.interior_color,

        "Введите цвет салона.\n\n"
        "Например: Чёрный"
    )


# =========================================================
# ЦВЕТ САЛОНА
# =========================================================

@dp.message(
    InspectionForm.interior_color
)
async def interior_color_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите цвет салона."
        )

        return

    await state.update_data(
        interior_color=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.seat_count,

        "Введите количество мест.\n\n"
        "Например: 5"
    )


# =========================================================
# КОЛИЧЕСТВО МЕСТ
# =========================================================

@dp.message(
    InspectionForm.seat_count
)
async def seat_count_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value.isdigit() or not 1 <= int(value) <= 20:

        await message.answer(
            "Введите количество мест цифрами от 1 до 20."
        )

        return

    await state.update_data(
        seat_count=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.audio_system_name,

        "Введите название аудиосистемы.\n\n"
        "Например: Harman Kardon"
    )


# =========================================================
# АУДИО
# =========================================================

@dp.message(
    InspectionForm.audio_system_name
)
async def audio_system_name_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите название аудиосистемы."
        )

        return

    await state.update_data(
        audio_system_name=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.speaker_count,

        "Введите количество динамиков.\n\n"
        "Например: 16"
    )


# =========================================================
# ДИНАМИКИ
# =========================================================

@dp.message(
    InspectionForm.speaker_count
)
async def speaker_count_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value.isdigit() or not 0 <= int(value) <= 100:

        await message.answer(
            "Введите количество динамиков цифрами от 0 до 100."
        )

        return

    await state.update_data(
        speaker_count=value
    )

    data = await state.get_data()

    if data.get(
        "edit_return_to_review"
    ):

        await state.update_data(
            edit_return_to_review=False
        )

        await state.set_state(
            InspectionForm.review
        )

        await show_review(
            message,
            state
        )

        return

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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.engine_volume,

        "Введите объём двигателя в литрах.\n\n"
        "Например: 2.0\n"
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
            "Введите объём цифрами.\n"
            "Например: 2.0"
        )

        return

    await state.update_data(
        engine_volume=value
    )

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.engine_hp,

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

    await finish_or_continue_edit(

        message,
        state,

        InspectionForm.gearbox,

        "Выберите коробку передач.",

        gearbox_keyboard
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

    data = await state.get_data()

    if data.get(
        "edit_return_to_review"
    ):

        await state.update_data(
            edit_return_to_review=False
        )

        await state.set_state(
            InspectionForm.review
        )

        await show_review(
            message,
            state
        )

        return

    measurements = data.get(
        "measurements"
    )

    if not isinstance(
        measurements,
        dict
    ):

        measurements = {}

    await state.update_data(

        lkp_index=data.get(
            "lkp_index",
            0
        ),

        measurements=measurements
    )

    await state.set_state(
        InspectionForm.lkp
    )

    await message.answer(

        f"🎨 <b>ЛКП</b>\n\n"
        f"{progress_text(InspectionForm.lkp.state)}\n\n"
        f"Введите толщину ЛКП.\n\n"
        f"Деталь: {LKP_PARTS[data.get('lkp_index', 0)]}\n\n"
        f"Например: 145",

        parse_mode="HTML",
        reply_markup=back_keyboard
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

    index = data.get(
        "lkp_index",
        0
    )

    measurements = data.get(
        "measurements",
        {}
    )

    if not isinstance(
        measurements,
        dict
    ):

        measurements = {}

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

            f"✅ {current_part}: {measurement} µm\n\n"
            f"Следующая деталь:\n"
            f"<b>{LKP_PARTS[next_index]}</b>\n\n"
            f"Введите значение:",

            parse_mode="HTML",
            reply_markup=back_keyboard
        )

        return

    await state.update_data(
        measurements=measurements
    )

    data = await state.get_data()

    if data.get(
        "edit_return_to_review"
    ):

        await state.update_data(
            edit_return_to_review=False
        )

        await state.set_state(
            InspectionForm.review
        )

        await show_review(
            message,
            state
        )

        return

    await state.set_state(
        InspectionForm.photos
    )

    await message.answer(

        "✅ <b>Все замеры ЛКП получены.</b>\n\n"
        "Теперь отправьте фотографии автомобиля.\n\n"
        "Можно отправлять несколько фотографий подряд.\n"
        "Когда закончите — нажмите «Готово».",

        parse_mode="HTML",

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

        f"📷 Фото №{len(photos)} получено.\n"
        f"Можешь отправить следующее или нажать «Готово».",

        reply_markup=finish_photos_keyboard
    )


# =========================================================
# ГОТОВО ФОТО
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
            "Отправь хотя бы одну фотографию автомобиля."
        )

        return

    # Если мы пришли сюда из финального редактирования —
    # просто возвращаемся к проверке.
    if data.get(
        "edit_return_to_review"
    ):

        await state.update_data(
            edit_return_to_review=False
        )

        await state.set_state(
            InspectionForm.review
        )

        await message.answer(
            f"📷 Сохранено фотографий: {len(photo_ids)}",
            reply_markup=back_keyboard
        )

        await show_review(
            message,
            state
        )

        return

    # Если комплектация уже существует — не пересоздаём её.
    equipment_results = data.get(
        "equipment_results"
    )

    manual_queue = data.get(
        "manual_equipment_queue"
    )

    if not equipment_results:

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
                ],

                paint_type=data[
                    "paint_type"
                ],

                display_size=data[
                    "display_size"
                ],

                seat_material=data[
                    "seat_material"
                ],

                wheel_type=data[
                    "wheel_type"
                ],

                interior_color=data[
                    "interior_color"
                ],

                seat_count=data[
                    "seat_count"
                ],

                audio_system_name=data[
                    "audio_system_name"
                ],

                speaker_count=data[
                    "speaker_count"
                ]
            )
        )

    if not manual_queue:

        manual_queue = (
            build_manual_equipment_queue()
        )

    await state.update_data(

        equipment_results=
            equipment_results,

        manual_equipment_queue=
            manual_queue,

        manual_equipment_index=
            data.get(
                "manual_equipment_index",
                0
            )
    )

    await state.set_state(
        InspectionForm.manual_equipment
    )

    await message.answer(

        f"📷 Получено фотографий: "
        f"{len(photo_ids)}.\n\n"

        "Фотографии сохранены в Telegram.\n"
        "При формировании PDF они будут автоматически загружены.\n\n"

        "Теперь заполним комплектацию вручную.",

        reply_markup=back_keyboard
    )

    await ask_next_manual_equipment(
        message,
        state
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

    if callback.data == "eq_yes":

        value = "Есть"

    elif callback.data == "eq_no":

        value = "Нет"

    else:

        value = "—"

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

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:

        pass

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

        await callback.message.answer(

            f"🧰 <b>ПРОВЕРКА КОМПЛЕКТАЦИИ</b>\n\n"
            f"Позиция: {next_index + 1} из {len(queue)}\n"
            f"Раздел: {next_category}\n"
            f"Опция: {next_option}\n\n"
            f"Укажите результат:",

            parse_mode="HTML",

            reply_markup=
                manual_equipment_keyboard()
        )

        return

    data = await state.get_data()

    # Если это редактирование — возвращаемся в review.
    if data.get(
        "edit_return_to_review"
    ):

        await state.update_data(
            edit_return_to_review=False
        )

        await state.set_state(
            InspectionForm.review
        )

        await callback.message.answer(
            "🧰 Комплектация обновлена."
        )

        await show_review(
            callback.message,
            state
        )

        return

    # Если мы возвращались назад из эндоскопии,
    # после завершения комплектации возвращаемся туда.
    resume_state = data.get(
        "endoscopy_resume_state"
    )

    if resume_state:

        await state.update_data(
            endoscopy_resume_state=None
        )

        await state.set_state(
            resume_state
        )

        await callback.message.answer(
            "Возвращаемся к эндоскопии."
        )

        await show_current_state_prompt(
            callback.message,
            state
        )

        return

    await state.set_state(
        InspectionForm.endoscopy_cylinders
    )

    await callback.message.answer(

        "✅ Комплектация полностью заполнена.\n\n"
        "🔬 Теперь заполним эндоскопию двигателя.\n\n"
        "1/7. Введите результат по цилиндрам.",

        reply_markup=endoscopy_keyboard
    )


# =========================================================
# НАЗАД В РУЧНОЙ КОМПЛЕКТАЦИИ
# =========================================================

@dp.callback_query(
    InspectionForm.manual_equipment,
    F.data == "eq_back"
)
async def manual_equipment_back_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    data = await state.get_data()

    index = data.get(
        "manual_equipment_index",
        0
    )

    if index > 0:

        index -= 1

        await state.update_data(
            manual_equipment_index=index
        )

        try:

            await callback.message.edit_reply_markup(
                reply_markup=None
            )

        except Exception:

            pass

        await ask_next_manual_equipment(
            callback.message,
            state
        )

        return

    await state.set_state(
        InspectionForm.photos
    )

    await callback.message.answer(

        "Возвращаемся к фотографиям.",

        reply_markup=finish_photos_keyboard
    )


# =========================================================
# ЭНДОСКОПИЯ
# =========================================================

async def save_endoscopy_value(
    message,
    state,
    key,
    value,
    next_state,
    prompt
):

    data = await state.get_data()

    endoscopy_data = data.get(
        "endoscopy_data",
        {}
    )

    endoscopy_data[key] = value

    await state.update_data(
        endoscopy_data=endoscopy_data
    )

    if data.get(
        "edit_return_to_review"
    ) and key == "overall":

        await state.update_data(
            edit_return_to_review=False
        )

        await state.set_state(
            InspectionForm.review
        )

        await show_review(
            message,
            state
        )

        return

    await state.set_state(
        next_state
    )

    await send_prompt(
        message,
        state,
        prompt,
        endoscopy_keyboard
    )


@dp.message(
    InspectionForm.endoscopy_cylinders
)
async def endoscopy_cylinders_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите результат по цилиндрам."
        )

        return

    await save_endoscopy_value(

        message,
        state,

        "cylinders",
        value,

        InspectionForm.endoscopy_cylinder_walls,

        "2/7. Опишите стенки цилиндров."
    )


@dp.message(
    InspectionForm.endoscopy_cylinder_walls
)
async def endoscopy_walls_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите состояние стенок цилиндров."
        )

        return

    await save_endoscopy_value(

        message,
        state,

        "cylinder_walls",
        value,

        InspectionForm.endoscopy_pistons,

        "3/7. Опишите состояние поршней."
    )


@dp.message(
    InspectionForm.endoscopy_pistons
)
async def endoscopy_pistons_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите состояние поршней."
        )

        return

    await save_endoscopy_value(

        message,
        state,

        "pistons",
        value,

        InspectionForm.endoscopy_scoring,

        "4/7. Опишите наличие или отсутствие задиров."
    )


@dp.message(
    InspectionForm.endoscopy_scoring
)
async def endoscopy_scoring_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите информацию о задирах."
        )

        return

    await save_endoscopy_value(

        message,
        state,

        "scoring",
        value,

        InspectionForm.endoscopy_carbon,

        "5/7. Опишите наличие или отсутствие нагара."
    )


@dp.message(
    InspectionForm.endoscopy_carbon
)
async def endoscopy_carbon_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите информацию о нагаре."
        )

        return

    await save_endoscopy_value(

        message,
        state,

        "carbon",
        value,

        InspectionForm.endoscopy_oil,

        "6/7. Опишите наличие или отсутствие масла."
    )


@dp.message(
    InspectionForm.endoscopy_oil
)
async def endoscopy_oil_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите информацию о следах масла."
        )

        return

    await save_endoscopy_value(

        message,
        state,

        "oil",
        value,

        InspectionForm.endoscopy_overall,

        "7/7. Введите общее состояние двигателя по результатам эндоскопии."
    )


@dp.message(
    InspectionForm.endoscopy_overall
)
async def endoscopy_overall_handler(
    message: types.Message,
    state: FSMContext
):

    value = (
        message.text or ""
    ).strip()

    if not value:

        await message.answer(
            "Введите общее состояние двигателя."
        )

        return

    data = await state.get_data()

    endoscopy_data = data.get(
        "endoscopy_data",
        {}
    )

    endoscopy_data["overall"] = value

    await state.update_data(
        endoscopy_data=endoscopy_data
    )

    if data.get(
        "edit_return_to_review"
    ):

        await state.update_data(
            edit_return_to_review=False
        )

        await state.set_state(
            InspectionForm.review
        )

        await message.answer(
            "🔬 Эндоскопия обновлена."
        )

        await show_review(
            message,
            state
        )

        return

    await state.set_state(
        InspectionForm.review
    )

    await message.answer(
        "✅ Эндоскопия заполнена."
    )

    await show_review(
        message,
        state
    )


# =========================================================
# REVIEW CALLBACKS
# =========================================================

@dp.callback_query(
    InspectionForm.review,
    F.data == "review_pdf"
)
async def review_pdf_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:

        pass

    await generate_and_send_report(
        callback.message,
        state
    )


@dp.callback_query(
    InspectionForm.review,
    F.data == "review_edit"
)
async def review_edit_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.set_state(
        InspectionForm.edit_menu
    )

    await callback.message.answer(

        "✏️ <b>Что хотите изменить?</b>\n\n"
        "После изменения бот вернёт вас обратно "
        "к финальной проверке.",

        parse_mode="HTML",

        reply_markup=edit_menu_keyboard()
    )


# =========================================================
# EDIT MENU
# =========================================================

@dp.callback_query(
    InspectionForm.edit_menu,
    F.data == "edit_back"
)
async def edit_back_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.set_state(
        InspectionForm.review
    )

    await show_review(
        callback.message,
        state
    )


@dp.callback_query(
    InspectionForm.edit_menu,
    F.data == "edit_car"
)
async def edit_car_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.update_data(
        edit_return_to_review=True
    )

    await state.set_state(
        InspectionForm.master_name
    )

    await callback.message.answer(
        "✏️ Изменение данных автомобиля.\n\n"
        "Введите имя мастера.",
        reply_markup=back_keyboard
    )


@dp.callback_query(
    InspectionForm.edit_menu,
    F.data == "edit_lkp"
)
async def edit_lkp_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.update_data(
        edit_return_to_review=True,
        lkp_index=0
    )

    await state.set_state(
        InspectionForm.lkp
    )

    await callback.message.answer(

        f"✏️ Изменение ЛКП.\n\n"
        f"Деталь: {LKP_PARTS[0]}\n\n"
        f"Введите значение:",

        reply_markup=back_keyboard
    )


@dp.callback_query(
    InspectionForm.edit_menu,
    F.data == "edit_photos"
)
async def edit_photos_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.update_data(
        edit_return_to_review=True
    )

    await state.set_state(
        InspectionForm.photos
    )

    data = await state.get_data()

    await callback.message.answer(

        f"✏️ Фотографии.\n\n"
        f"Сейчас сохранено: "
        f"{len(data.get('photos', []))}\n\n"
        f"Можешь добавить новые фотографии.\n"
        f"Когда закончишь — нажми «Готово».",

        reply_markup=finish_photos_keyboard
    )


@dp.callback_query(
    InspectionForm.edit_menu,
    F.data == "edit_equipment"
)
async def edit_equipment_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    data = await state.get_data()

    equipment_results = data.get(
        "equipment_results"
    )

    if not equipment_results:

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
                ],

                paint_type=data[
                    "paint_type"
                ],

                display_size=data[
                    "display_size"
                ],

                seat_material=data[
                    "seat_material"
                ],

                wheel_type=data[
                    "wheel_type"
                ],

                interior_color=data[
                    "interior_color"
                ],

                seat_count=data[
                    "seat_count"
                ],

                audio_system_name=data[
                    "audio_system_name"
                ],

                speaker_count=data[
                    "speaker_count"
                ]
            )
        )

    queue = build_manual_equipment_queue()

    await state.update_data(

        edit_return_to_review=True,

        equipment_results=
            equipment_results,

        manual_equipment_queue=
            queue,

        manual_equipment_index=
            0
    )

    await state.set_state(
        InspectionForm.manual_equipment
    )

    await callback.message.answer(
        "✏️ Изменение комплектации.",
    )

    await ask_next_manual_equipment(
        callback.message,
        state
    )


@dp.callback_query(
    InspectionForm.edit_menu,
    F.data == "edit_endoscopy"
)
async def edit_endoscopy_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.update_data(
        edit_return_to_review=True
    )

    await state.set_state(
        InspectionForm.endoscopy_cylinders
    )

    await callback.message.answer(

        "✏️ Изменение эндоскопии.\n\n"
        "1/7. Введите результат по цилиндрам.",

        reply_markup=endoscopy_keyboard
    )


# =========================================================
# ТЕКСТ ПРИ РУЧНОЙ КОМПЛЕКТАЦИИ
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
# ТЕКСТ ВМЕСТО ФОТО
# =========================================================

@dp.message(
    InspectionForm.photos,
    F.text
)
async def photos_text_handler(
    message: types.Message
):

    await message.answer(

        "📷 Отправляй фотографии автомобиля.\n\n"
        "Когда закончишь — нажми «Готово»."
    )


# =========================================================
# RENDER HEALTH
# =========================================================

async def health(
    request
):

    return web.Response(
        text="ЛИПГУС-ГРУП BOT OK"
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
        "ЛИПГУС-ГРУП BOT STARTED"
    )

    print(
        "MODE: MANUAL INSPECTION"
    )

    print(
        f"FSM DATABASE: {DB_PATH}"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
