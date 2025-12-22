from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import DEFAULT_LANGUAGE
from i18n import t
from keyboards.common import main_menu, choices_keyboard, back_keyboard
from services.analytics import send_event
from states_certificate import CertificateFlow

router = Router()


# Обработчики кнопок меню должны быть первыми и работать в любом состоянии
@router.message(F.text.in_(["Главное меню", "Басты мәзір", "главное меню", "басты мәзір"]))
async def handle_main_menu(message: Message, state: FSMContext):
    lang = await get_language(state)
    await state.clear()
    await message.answer(t("main_welcome", lang), reply_markup=main_menu(lang))


async def get_language(state: FSMContext) -> str:
    """Получить язык из state или вернуть дефолтный"""
    data = await state.get_data()
    return data.get("language", DEFAULT_LANGUAGE)


def is_back(text: str, lang: str = "RU") -> bool:
    """Проверить, является ли текст командой 'Назад'"""
    if not text:
        return False
    text_lower = text.lower()
    if lang == "KZ":
        return text_lower in {"артқа", "назад"}
    return text_lower in {"назад"}


def is_main_menu(text: str, lang: str = "RU") -> bool:
    """Проверить, является ли текст командой 'Главное меню'"""
    if not text:
        return False
    text_lower = text.lower()
    if lang == "KZ":
        return text_lower in {"басты мәзір", "главное меню"}
    return text_lower in {"главное меню"}


async def certificate_start(message: Message, state: FSMContext):
    """Начало потока 'Есть сертификат' - выбор действия"""
    lang = await get_language(state)
    await send_event("certificate_flow_started", {}, bot_user_id=message.from_user.id)
    
    # Текст согласно ТЗ
    text_ru = (
        "У вас есть сертификат об окончании автошколы,\n"
        "но экзамен ещё не сдан. Выберите, что вам нужно."
    )
    text_kz = (
        "Сізде автошколаны бітірген сертификат бар,\n"
        "бірақ емтихан әлі тапсырылмаған. Сізге не керек екенін таңдаңыз."
    )
    text = text_kz if lang == "KZ" else text_ru
    
    # Кнопки согласно ТЗ (тесты перенесены в главное меню)
    options_ru = [
        "🏫 Пройти автошколу заново",
        "🚗 Записаться к инструктору",
    ]
    options_kz = [
        "🏫 Автошколаны қайта өту",
        "🚗 Нұсқаушыға жазылу",
    ]
    options = options_kz if lang == "KZ" else options_ru
    
    await state.set_state(CertificateFlow.select_action)
    await state.update_data(language=lang)
    # Добавляем кнопки "Назад" и "Главное меню"
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=opt)] for opt in options
        ] + [
            [KeyboardButton(text=t("back", lang)), KeyboardButton(text=t("main_menu", lang))],
        ],
        resize_keyboard=True,
    )
    await message.answer(text, reply_markup=keyboard)


@router.message(CertificateFlow.select_action)
async def certificate_choose_action(message: Message, state: FSMContext):
    """Обработка выбора действия в потоке 'Есть сертификат'"""
    lang = await get_language(state)
    
    # Обработка кнопок "Главное меню" и "Назад"
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_welcome", lang), reply_markup=main_menu(lang))
        return
    
    if is_back(message.text, lang):
        await state.clear()
        await message.answer(t("main_welcome", lang), reply_markup=main_menu(lang))
        return
    
    text = message.text or ""
    text_lower = text.lower() if text else ""
    
    # Проверяем выбор пользователя
    # Сохраняем intent CERT_NOT_PASSED для дочерних потоков
    data = await state.get_data()
    if "main_intent" not in data:
        await state.update_data(main_intent="CERT_NOT_PASSED")
    
    if "автошкол" in text_lower or "автомектеп" in text_lower:
        # Переход в поток автошкол
        await send_event("certificate_action_selected", {"action": "schools"}, bot_user_id=message.from_user.id)
        from handlers.schools_flow import schools_start
        await schools_start(message, state)
    elif "инструктор" in text_lower or "нұсқаушы" in text_lower:
        # Переход в поток инструкторов
        await send_event("certificate_action_selected", {"action": "instructors"}, bot_user_id=message.from_user.id)
        from handlers.instructors_flow import instructors_start
        await instructors_start(message, state)
    else:
        # Неверный выбор - показываем снова
        await certificate_start(message, state)

