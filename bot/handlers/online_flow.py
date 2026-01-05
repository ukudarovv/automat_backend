from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import DEFAULT_LANGUAGE
from i18n import t
from keyboards.common import main_menu, back_keyboard, choices_keyboard, phone_keyboard, confirm_keyboard
from services.api import ApiClient, ApiClientError, ApiServerError, ApiTimeoutError, ApiNetworkError
from states_online import OnlineFlow
from utils.validators import normalize_phone, is_valid_iin
from utils.whatsapp import build_wa_link_online
from services.analytics import send_event

router = Router()


def get_name_by_lang(item: dict, lang: str) -> str:
    """Получить название на нужном языке"""
    if lang == "KZ" and "name_kz" in item:
        return item.get("name_kz") or item.get("name_ru", "")
    return item.get("name_ru", item.get("name", {}).get("ru", ""))


def format_choice_option(index: int, name: str) -> str:
    """Форматировать опцию выбора - просто название без номера"""
    return name.strip()


def find_item_by_text(items: list, text: str, lang: str) -> dict:
    """Найти элемент по тексту кнопки"""
    text = text.strip()
    for item in items:
        name = get_name_by_lang(item, lang).strip()
        if text == name:
            return item
    return None


async def get_language(state: FSMContext) -> str:
    """Получить язык из state или вернуть дефолтный"""
    data = await state.get_data()
    return data.get("language", DEFAULT_LANGUAGE)


async def handle_api_error(error: Exception, lang: str, message: Message, state: FSMContext):
    """Обработать ошибку API и отправить понятное сообщение пользователю"""
    if isinstance(error, ApiClientError):
        error_msg = t("error_client", lang)
    elif isinstance(error, ApiServerError):
        error_msg = t("error_server", lang)
    elif isinstance(error, ApiTimeoutError):
        error_msg = t("error_timeout", lang)
    elif isinstance(error, ApiNetworkError):
        error_msg = t("error_network", lang)
    else:
        error_msg = t("error_unknown", lang)
    
    await message.answer(error_msg, reply_markup=main_menu(lang))
    await state.clear()


def is_back(text: str, lang: str = "RU") -> bool:
    if not text:
        return False
    text_lower = text.lower()
    if lang == "KZ":
        return text_lower in {t("back", "KZ").lower(), "назад"}
    return text_lower in {t("back", "RU").lower()}


def is_main_menu(text: str, lang: str = "RU") -> bool:
    if not text:
        return False
    text_lower = text.lower()
    if lang == "KZ":
        return text_lower in {t("main_menu", "KZ").lower(), "главное меню"}
    return text_lower in {t("main_menu", "RU").lower()}


# Обработчики кнопок меню должны быть первыми
@router.message(F.text.in_(["Главное меню", "Басты мәзір", "главное меню", "басты мәзір"]))
async def handle_main_menu(message: Message, state: FSMContext):
    lang = await get_language(state)
    await state.clear()
    await message.answer(t("main_welcome", lang), reply_markup=main_menu(lang))


async def online_start(message: Message, state: FSMContext):
    """Начало потока онлайн-обучения - выбор продукта"""
    await state.clear()
    lang = await get_language(state)
    await send_event("flow_selected", {"flow": "online"}, bot_user_id=message.from_user.id)
    
    await state.update_data(language=lang)
    await state.set_state(OnlineFlow.product_choice)
    
    # Показываем 3 кнопки для выбора продукта
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    product_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("online_product_pdd_tests", lang))],
            [KeyboardButton(text=t("online_product_start", lang))],
            [KeyboardButton(text=t("online_product_pro_drive", lang))],
            [KeyboardButton(text=t("back", lang))],
            [KeyboardButton(text=t("main_menu", lang))],
        ],
        resize_keyboard=True,
    )
    
    await message.answer(t("online_choose_product", lang), reply_markup=product_keyboard)


@router.message(OnlineFlow.product_choice)
async def online_choose_product(message: Message, state: FSMContext):
    """Обработка выбора продукта"""
    lang = await get_language(state)
    
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    
    # Определяем выбранный продукт
    pdd_text_ru = t("online_product_pdd_tests", "RU")
    pdd_text_kz = t("online_product_pdd_tests", "KZ")
    start_text_ru = t("online_product_start", "RU")
    start_text_kz = t("online_product_start", "KZ")
    pro_text_ru = t("online_product_pro_drive", "RU")
    pro_text_kz = t("online_product_pro_drive", "KZ")
    
    selected_product = None
    tariff_plan_code = None
    
    if message.text in [pdd_text_ru, pdd_text_kz]:
        selected_product = "PDD_TESTS"
        tariff_plan_code = "PDD_TESTS"
    elif message.text in [start_text_ru, start_text_kz]:
        selected_product = "ONLINE_START"
        tariff_plan_code = "ONLINE_START"
    elif message.text in [pro_text_ru, pro_text_kz]:
        selected_product = "ONLINE_PRO_DRIVE"
        tariff_plan_code = "ONLINE_PRO_DRIVE"
    else:
        # Неверный выбор, показываем снова
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        product_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=t("online_product_pdd_tests", lang))],
                [KeyboardButton(text=t("online_product_start", lang))],
                [KeyboardButton(text=t("online_product_pro_drive", lang))],
                [KeyboardButton(text=t("back", lang))],
                [KeyboardButton(text=t("main_menu", lang))],
            ],
            resize_keyboard=True,
        )
        await message.answer(t("online_choose_product", lang), reply_markup=product_keyboard)
        return
    
    await state.update_data(
        selected_product=selected_product,
        tariff_plan_code=tariff_plan_code
    )
    
    # Для ПДД-тестов - показываем выбор категории
    if selected_product == "PDD_TESTS":
        await send_event("product_selected", {"product": "PDD_TESTS"}, bot_user_id=message.from_user.id)
        api = ApiClient()
        try:
            categories = await api.get_categories()
        except Exception as e:
            await api.close()
            await handle_api_error(e, lang, message, state)
            return
        await api.close()
        
        if not categories:
            await message.answer("Категории не найдены", reply_markup=main_menu(lang))
            await state.clear()
            return
        
        await state.update_data(categories=categories)
        await state.set_state(OnlineFlow.category)
        opts = [format_choice_option(i, get_name_by_lang(c, lang)) for i, c in enumerate(categories)]
        await message.answer(t("choose_category", lang), reply_markup=choices_keyboard(opts, lang))
    else:
        # Для START и PRO - категория фиксирована B
        await send_event("product_selected", {"product": selected_product}, bot_user_id=message.from_user.id)
        api = ApiClient()
        try:
            categories = await api.get_categories()
            # Находим категорию B
            category_b = None
            for cat in categories:
                if cat.get("code") == "B":
                    category_b = cat
                    break
            
            if not category_b:
                await message.answer("Категория B не найдена", reply_markup=main_menu(lang))
                await api.close()
                await state.clear()
                return
            
            category_id = category_b["id"]
            category_name = get_name_by_lang(category_b, lang)
            await state.update_data(category_id=category_id, category_name=category_name)
        except Exception as e:
            await api.close()
            await handle_api_error(e, lang, message, state)
            return
        await api.close()
        
        # Переход сразу к форме
        await state.set_state(OnlineFlow.first_name)
        await message.answer(t("online_enter_first_name", lang), reply_markup=back_keyboard(lang))


@router.message(OnlineFlow.category)
async def online_choose_category(message: Message, state: FSMContext):
    """Обработка выбора категории для ПДД-тестов"""
    lang = await get_language(state)
    
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        # Возврат к выбору продукта
        await state.set_state(OnlineFlow.product_choice)
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        product_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=t("online_product_pdd_tests", lang))],
                [KeyboardButton(text=t("online_product_start", lang))],
                [KeyboardButton(text=t("online_product_pro_drive", lang))],
                [KeyboardButton(text=t("back", lang))],
                [KeyboardButton(text=t("main_menu", lang))],
            ],
            resize_keyboard=True,
        )
        await message.answer(t("online_choose_product", lang), reply_markup=product_keyboard)
        return
    
    data = await state.get_data()
    categories = data.get("categories", [])
    selected_category = find_item_by_text(categories, message.text, lang)
    
    if not selected_category:
        opts = [format_choice_option(i, get_name_by_lang(c, lang)) for i, c in enumerate(categories)]
        await message.answer(t("choose_category", lang), reply_markup=choices_keyboard(opts, lang))
        return
    
    category_id = selected_category["id"]
    category_name = get_name_by_lang(selected_category, lang)
    
    await send_event("category_selected", {"category_id": category_id}, bot_user_id=message.from_user.id)
    await state.update_data(category_id=category_id, category_name=category_name)
    
    # Переход к форме
    await state.set_state(OnlineFlow.first_name)
    await message.answer(t("online_enter_first_name", lang), reply_markup=back_keyboard(lang))


@router.message(OnlineFlow.first_name)
async def online_first_name(message: Message, state: FSMContext):
    """Обработка ввода имени"""
    lang = await get_language(state)
    
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        data = await state.get_data()
        selected_product = data.get("selected_product")
        if selected_product == "PDD_TESTS":
            # Возврат к выбору категории
            categories = data.get("categories", [])
            if categories:
                await state.set_state(OnlineFlow.category)
                opts = [format_choice_option(i, get_name_by_lang(c, lang)) for i, c in enumerate(categories)]
                await message.answer(t("choose_category", lang), reply_markup=choices_keyboard(opts, lang))
            else:
                await state.set_state(OnlineFlow.product_choice)
                from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
                product_keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text=t("online_product_pdd_tests", lang))],
                        [KeyboardButton(text=t("online_product_start", lang))],
                        [KeyboardButton(text=t("online_product_pro_drive", lang))],
                        [KeyboardButton(text=t("back", lang))],
                        [KeyboardButton(text=t("main_menu", lang))],
                    ],
                    resize_keyboard=True,
                )
                await message.answer(t("online_choose_product", lang), reply_markup=product_keyboard)
        else:
            # Возврат к выбору продукта
            await state.set_state(OnlineFlow.product_choice)
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
            product_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text=t("online_product_pdd_tests", lang))],
                    [KeyboardButton(text=t("online_product_start", lang))],
                    [KeyboardButton(text=t("online_product_pro_drive", lang))],
                    [KeyboardButton(text=t("back", lang))],
                    [KeyboardButton(text=t("main_menu", lang))],
                ],
                resize_keyboard=True,
            )
            await message.answer(t("online_choose_product", lang), reply_markup=product_keyboard)
        return
    
    first_name = message.text.strip()
    if len(first_name) < 2:
        await message.answer(t("invalid_name", lang), reply_markup=back_keyboard(lang))
        return
    
    await state.update_data(first_name=first_name)
    await state.set_state(OnlineFlow.last_name)
    await message.answer(t("online_enter_last_name", lang), reply_markup=back_keyboard(lang))


@router.message(OnlineFlow.last_name)
async def online_last_name(message: Message, state: FSMContext):
    """Обработка ввода фамилии"""
    lang = await get_language(state)
    
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        await state.set_state(OnlineFlow.first_name)
        await message.answer(t("online_enter_first_name", lang), reply_markup=back_keyboard(lang))
        return
    
    last_name = message.text.strip()
    if len(last_name) < 2:
        await message.answer(t("invalid_name", lang), reply_markup=back_keyboard(lang))
        return
    
    await state.update_data(last_name=last_name)
    await state.set_state(OnlineFlow.iin)
    await message.answer(t("enter_iin", lang), reply_markup=back_keyboard(lang))


@router.message(OnlineFlow.iin)
async def online_iin(message: Message, state: FSMContext):
    """Обработка ввода ИИН"""
    lang = await get_language(state)
    
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        await state.set_state(OnlineFlow.last_name)
        await message.answer(t("online_enter_last_name", lang), reply_markup=back_keyboard(lang))
        return
    
    iin = message.text.strip()
    if not is_valid_iin(iin):
        await message.answer(t("invalid_iin", lang), reply_markup=back_keyboard(lang))
        return
    
    await state.update_data(iin=iin)
    await state.set_state(OnlineFlow.whatsapp)
    await message.answer(t("enter_whatsapp_contact", lang), reply_markup=phone_keyboard(lang))


@router.message(OnlineFlow.whatsapp)
async def online_whatsapp(message: Message, state: FSMContext):
    """Обработка ввода WhatsApp"""
    lang = await get_language(state)
    
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        await state.set_state(OnlineFlow.iin)
        await message.answer(t("enter_iin", lang), reply_markup=back_keyboard(lang))
        return
    
    # Обработка request_contact
    whatsapp = None
    if message.contact:
        whatsapp = normalize_phone(message.contact.phone_number)
    elif message.text:
        whatsapp = normalize_phone(message.text)
    
    if not whatsapp:
        await message.answer(t("invalid_phone", lang), reply_markup=phone_keyboard(lang))
        return
    
    await state.update_data(whatsapp=whatsapp)
    
    # Показываем экран подтверждения
    data = await state.get_data()
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    iin = data.get("iin", "")
    category_name = data.get("category_name", "")
    tariff_plan_code = data.get("tariff_plan_code", "")
    
    # Получаем название тарифа
    tariff_plan_name = ""
    if tariff_plan_code == "PDD_TESTS":
        tariff_plan_name = t("online_product_pdd_tests", lang)
    elif tariff_plan_code == "ONLINE_START":
        tariff_plan_name = t("online_product_start", lang)
    elif tariff_plan_code == "ONLINE_PRO_DRIVE":
        tariff_plan_name = t("online_product_pro_drive", lang)
    
    confirm_text_ru = (
        f"{t('online_confirm_message', lang)}\n\n"
        f"👤 Имя: {first_name}\n"
        f"👤 Фамилия: {last_name}\n"
        f"🆔 ИИН: {iin}\n"
        f"💬 WhatsApp: {whatsapp}\n"
        f"📘 Тариф: {tariff_plan_name}\n"
    )
    if category_name:
        confirm_text_ru += f"📗 Категория: {category_name}\n"
    
    confirm_text_kz = (
        f"{t('online_confirm_message', lang)}\n\n"
        f"👤 Аты: {first_name}\n"
        f"👤 Тегі: {last_name}\n"
        f"🆔 ЖСН: {iin}\n"
        f"💬 WhatsApp: {whatsapp}\n"
        f"📘 Тариф: {tariff_plan_name}\n"
    )
    if category_name:
        confirm_text_kz += f"📗 Санат: {category_name}\n"
    
    text = confirm_text_kz if lang == "KZ" else confirm_text_ru
    await message.answer(text, reply_markup=confirm_keyboard(lang))
    await state.set_state(OnlineFlow.confirm)


@router.message(OnlineFlow.confirm, F.text.in_(["✅ Всё верно", "✅ Барлығы дұрыс"]))
async def online_confirm(message: Message, state: FSMContext):
    """Подтверждение и отправка заявки"""
    lang = await get_language(state)
    data = await state.get_data()
    
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip()
    iin = data.get("iin", "")
    whatsapp = data.get("whatsapp", "")
    category_id = data.get("category_id")
    category_name = data.get("category_name", "")
    tariff_plan_code = data.get("tariff_plan_code", "")
    
    # Получаем тариф из API
    api = ApiClient()
    try:
        tariff = await api.get_online_tariff(tariff_plan_code, category_id=category_id)
        if not tariff:
            await message.answer("Тариф не найден", reply_markup=main_menu(lang))
            await api.close()
            await state.clear()
            return
        
        tariff_plan = tariff.get("tariff_plan", {})
        tariff_plan_id = tariff_plan.get("id") if isinstance(tariff_plan, dict) else tariff.get("tariff_plan_id")
        tariff_price_kzt = tariff.get("price_kzt", 0)
        school_id = tariff.get("school_id")
        training_format_id = 1  # Онлайн
        
        if not tariff_plan_id or not school_id:
            await message.answer("Ошибка: не удалось получить данные тарифа", reply_markup=main_menu(lang))
            await api.close()
            await state.clear()
            return
        
        # Получаем название тарифа для WhatsApp
        if isinstance(tariff_plan, dict):
            tariff_plan_name = tariff_plan.get("name_ru", "")
            if lang == "KZ":
                tariff_plan_name = tariff_plan.get("name_kz", tariff_plan_name)
        else:
            # Fallback на переводы из i18n
            if tariff_plan_code == "PDD_TESTS":
                tariff_plan_name = t("online_product_pdd_tests", lang)
            elif tariff_plan_code == "ONLINE_START":
                tariff_plan_name = t("online_product_start", lang)
            elif tariff_plan_code == "ONLINE_PRO_DRIVE":
                tariff_plan_name = t("online_product_pro_drive", lang)
            else:
                tariff_plan_name = ""
    except Exception as e:
        await api.close()
        await handle_api_error(e, lang, message, state)
        return
    
    # Создаем заявку
    payload = {
        "type": "SCHOOL",
        "language": lang,
        "bot_user": {
            "telegram_user_id": message.from_user.id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "language": lang,
        },
        "contact": {"name": full_name, "phone": whatsapp},
        "payload": {
            "school_id": school_id,
            "category_id": category_id,
            "training_format_id": training_format_id,
            "tariff_plan_id": tariff_plan_id,
            "tariff_price_kzt": tariff_price_kzt,
            "iin": iin,
            "whatsapp": whatsapp,
        },
    }
    
    try:
        lead_response = await api.create_lead(payload)
        lead_id = lead_response.get("id") if isinstance(lead_response, dict) else None
    except Exception as exc:
        await api.close()
        await handle_api_error(exc, lang, message, state)
        return
    await api.close()
    
    await send_event("lead_submitted", {"type": "ONLINE", "product": tariff_plan_code}, bot_user_id=message.from_user.id, lead_id=lead_id)
    
    # Показываем благодарность
    await message.answer(t("thank_you", lang), reply_markup=main_menu(lang))
    
    # Генерируем WhatsApp ссылку
    wa_link = build_wa_link_online(tariff_plan_name, first_name, last_name, iin, whatsapp, category_name, lang)
    if wa_link:
        await send_event("whatsapp_opened", {"flow": "online"}, bot_user_id=message.from_user.id)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="Открыть WhatsApp" if lang == "RU" else "WhatsApp ашу",
            url=wa_link
        )]])
        await message.answer(
            "Нажмите на кнопку, чтобы открыть WhatsApp" if lang == "RU" else "WhatsApp ашу үшін батырманы басыңыз",
            reply_markup=keyboard
        )
    
    await state.clear()


@router.message(OnlineFlow.confirm)
async def online_confirm_any(message: Message, state: FSMContext):
    """Обработка других сообщений в состоянии подтверждения"""
    lang = await get_language(state)
    
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    
    # Обработка кнопки "Исправить"
    fix_text_ru = t("fix", "RU")
    fix_text_kz = t("fix", "KZ")
    if message.text in [fix_text_ru, fix_text_kz]:
        # Возврат к вводу имени
        await state.set_state(OnlineFlow.first_name)
        await message.answer(t("online_enter_first_name", lang), reply_markup=back_keyboard(lang))
        return
    
    # Если не "Всё верно" и не "Исправить", показываем снова подтверждение
    data = await state.get_data()
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    iin = data.get("iin", "")
    whatsapp = data.get("whatsapp", "")
    category_name = data.get("category_name", "")
    tariff_plan_code = data.get("tariff_plan_code", "")
    
    tariff_plan_name = ""
    if tariff_plan_code == "PDD_TESTS":
        tariff_plan_name = t("online_product_pdd_tests", lang)
    elif tariff_plan_code == "ONLINE_START":
        tariff_plan_name = t("online_product_start", lang)
    elif tariff_plan_code == "ONLINE_PRO_DRIVE":
        tariff_plan_name = t("online_product_pro_drive", lang)
    
    confirm_text_ru = (
        f"{t('online_confirm_message', lang)}\n\n"
        f"👤 Имя: {first_name}\n"
        f"👤 Фамилия: {last_name}\n"
        f"🆔 ИИН: {iin}\n"
        f"💬 WhatsApp: {whatsapp}\n"
        f"📘 Тариф: {tariff_plan_name}\n"
    )
    if category_name:
        confirm_text_ru += f"📗 Категория: {category_name}\n"
    
    confirm_text_kz = (
        f"{t('online_confirm_message', lang)}\n\n"
        f"👤 Аты: {first_name}\n"
        f"👤 Тегі: {last_name}\n"
        f"🆔 ЖСН: {iin}\n"
        f"💬 WhatsApp: {whatsapp}\n"
        f"📘 Тариф: {tariff_plan_name}\n"
    )
    if category_name:
        confirm_text_kz += f"📗 Санат: {category_name}\n"
    
    text = confirm_text_kz if lang == "KZ" else confirm_text_ru
    await message.answer(text, reply_markup=confirm_keyboard(lang))

