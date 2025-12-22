from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import DEFAULT_LANGUAGE
from i18n import t
from keyboards.common import main_menu, back_keyboard, choices_keyboard, phone_keyboard, confirm_keyboard
from services.api import ApiClient, ApiClientError, ApiServerError, ApiTimeoutError, ApiNetworkError
from services.analytics import send_event
from states_school import SchoolFlow
from utils.validators import normalize_phone
from utils.whatsapp import build_wa_link_school

router = Router()


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




def get_name_by_lang(item: dict, lang: str) -> str:
    """Получить название на нужном языке"""
    if lang == "KZ" and "name_kz" in item:
        return item.get("name_kz") or item.get("name_ru", "")
    return item.get("name_ru", item.get("name", {}).get("ru", ""))


def get_tariff_name(tariff_item: dict, lang: str) -> str:
    """Получить название тарифа на нужном языке из данных API"""
    if lang == "KZ":
        return tariff_item.get('name_kz') or tariff_item.get('name_ru') or tariff_item.get('code', '')
    return tariff_item.get('name_ru') or tariff_item.get('code', '')


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


# Обработчики кнопок меню должны быть первыми и работать в любом состоянии
@router.message(F.text.in_(["Главное меню", "Басты мәзір", "главное меню", "басты мәзір"]))
async def handle_main_menu(message: Message, state: FSMContext):
    lang = await get_language(state)
    await state.clear()
    await message.answer(t("main_welcome", lang), reply_markup=main_menu(lang))


@router.message(Command("schools"))
@router.message(F.text.in_(["Автошколы", "Автошколалар", "автошколы"]))
async def schools_start(message: Message, state: FSMContext):
    # Очищаем текущее состояние перед началом нового потока
    await state.clear()
    lang = await get_language(state)
    await send_event("flow_selected", {"flow": "schools"}, bot_user_id=message.from_user.id)
    api = ApiClient()
    try:
        cities = await api.get_cities()
    except Exception as e:
        await api.close()
        await handle_api_error(e, lang, message, state)
        return
    await api.close()
    if not cities:
        await message.answer(t("no_cities", lang), reply_markup=main_menu(lang))
        return
    await state.set_state(SchoolFlow.city)
    options = [f"{c['id']}: {get_name_by_lang(c, lang)}" for c in cities]
    await state.update_data(cities=cities, language=lang)
    await message.answer(t("choose_city", lang), reply_markup=choices_keyboard(options, lang))


@router.message(SchoolFlow.city)
async def schools_choose_city(message: Message, state: FSMContext):
    lang = await get_language(state)
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        # На первом шаге "Назад" ведет в главное меню
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    data = await state.get_data()
    cities = data.get("cities", [])
    city_id = None
    for c in cities:
        if message.text.startswith(f"{c['id']}:"):
            city_id = c["id"]
            break
    if not city_id:
        await message.answer(t("choose_city", lang), reply_markup=choices_keyboard([f"{c['id']}: {get_name_by_lang(c, lang)}" for c in cities], lang))
        return
    await send_event("city_selected", {"city_id": city_id}, bot_user_id=message.from_user.id)
    api = ApiClient()
    try:
        categories = await api.get_categories()
    except Exception as e:
        await api.close()
        await handle_api_error(e, lang, message, state)
        return
    await api.close()
    
    # Фильтрация категорий: только B для потоков без CERT_NOT_PASSED intent
    data = await state.get_data()
    main_intent = data.get("main_intent")
    if main_intent != "CERT_NOT_PASSED":
        # Оставляем только категорию B
        categories = [c for c in categories if c.get('code') == 'B']
        if not categories:
            await message.answer(t("no_categories", lang) if hasattr(t, "no_categories") else "Категория B не найдена", reply_markup=main_menu(lang))
            await state.clear()
            return
    
    await state.update_data(city_id=city_id, categories=categories)
    opts = [f"{c['id']}: {get_name_by_lang(c, lang)}" for c in categories]
    await state.set_state(SchoolFlow.category)
    await message.answer(t("choose_category", lang), reply_markup=choices_keyboard(opts, lang))


@router.message(SchoolFlow.category)
async def schools_choose_category(message: Message, state: FSMContext):
    lang = await get_language(state)
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        # Возврат к выбору города
        data = await state.get_data()
        cities = data.get("cities", [])
        if cities:
            await state.set_state(SchoolFlow.city)
            options = [f"{c['id']}: {get_name_by_lang(c, lang)}" for c in cities]
            await message.answer(t("choose_city", lang), reply_markup=choices_keyboard(options, lang))
        else:
            await state.clear()
            await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    data = await state.get_data()
    categories = data.get("categories", [])
    category_id = None
    selected_category = None
    for c in categories:
        if message.text.startswith(f"{c['id']}:"):
            category_id = c["id"]
            selected_category = c
            break
    if not category_id:
        await message.answer(t("choose_category", lang), reply_markup=choices_keyboard([f"{c['id']}: {get_name_by_lang(c, lang)}" for c in categories], lang))
        return
    
    # Валидация: проверяем, что выбрана категория B для потоков без CERT_NOT_PASSED
    main_intent = data.get("main_intent")
    if main_intent != "CERT_NOT_PASSED" and selected_category.get('code') != 'B':
        await message.answer(
            "Доступна только категория B" if lang == "RU" else "Тек B санаты қолжетімді",
            reply_markup=choices_keyboard([f"{c['id']}: {get_name_by_lang(c, lang)}" for c in categories], lang)
        )
        return
    await send_event("category_selected", {"category_id": category_id}, bot_user_id=message.from_user.id)
    api = ApiClient()
    try:
        formats = await api.get_training_formats()
    except Exception as e:
        await api.close()
        await handle_api_error(e, lang, message, state)
        return
    await api.close()
    await state.update_data(category_id=category_id, formats=formats)
    opts = [f"{f['id']}: {get_name_by_lang(f, lang)}" for f in formats]
    await state.set_state(SchoolFlow.training_format)
    await message.answer(t("choose_format", lang), reply_markup=choices_keyboard(opts, lang))


@router.message(SchoolFlow.training_format)
async def schools_choose_format(message: Message, state: FSMContext):
    lang = await get_language(state)
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        # Возврат к выбору категории
        data = await state.get_data()
        categories = data.get("categories", [])
        if categories:
            await state.set_state(SchoolFlow.category)
            opts = [f"{c['id']}: {get_name_by_lang(c, lang)}" for c in categories]
            await message.answer(t("choose_category", lang), reply_markup=choices_keyboard(opts, lang))
        else:
            await state.clear()
            await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    data = await state.get_data()
    formats = data.get("formats", [])
    fmt_id = None
    for f in formats:
        if message.text.startswith(f"{f['id']}:"):
            fmt_id = f["id"]
            break
    if not fmt_id:
        await message.answer(t("choose_format", lang), reply_markup=choices_keyboard([f"{f['id']}: {get_name_by_lang(f, lang)}" for f in formats], lang))
        return
    city_id = data["city_id"]
    api = ApiClient()
    try:
        schools = await api.get_schools(city_id=city_id)
    except Exception as e:
        await api.close()
        await handle_api_error(e, lang, message, state)
        return
    await api.close()
    if not schools:
        await message.answer(t("no_schools", lang), reply_markup=main_menu(lang))
        await state.clear()
        return
    await send_event("format_selected", {"training_format_id": fmt_id}, bot_user_id=message.from_user.id)
    await state.update_data(training_format_id=fmt_id, schools=schools)
    opts = []
    for s in schools:
        name_dict = s.get('name', {})
        school_name = name_dict.get('kz' if lang == "KZ" else 'ru', name_dict.get('ru', ''))
        opts.append(f"{s['id']}: {school_name}")
    await state.set_state(SchoolFlow.school)
    await message.answer(t("choose_school", lang), reply_markup=choices_keyboard(opts, lang))


@router.message(SchoolFlow.school)
async def schools_choose_school(message: Message, state: FSMContext):
    lang = await get_language(state)
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        # Возврат к выбору формата обучения
        data = await state.get_data()
        formats = data.get("formats", [])
        if formats:
            await state.set_state(SchoolFlow.training_format)
            opts = [f"{f['id']}: {get_name_by_lang(f, lang)}" for f in formats]
            await message.answer(t("choose_format", lang), reply_markup=choices_keyboard(opts, lang))
        else:
            await state.clear()
            await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    data = await state.get_data()
    schools = data.get("schools", [])
    school_id = None
    for s in schools:
        if message.text.startswith(f"{s['id']}:"):
            school_id = s["id"]
            break
    if not school_id:
        opts = []
        for s in schools:
            name_dict = s.get('name', {})
            school_name = name_dict.get('kz' if lang == "KZ" else 'ru', name_dict.get('ru', ''))
            opts.append(f"{s['id']}: {school_name}")
        await message.answer(t("choose_school", lang), reply_markup=choices_keyboard(opts, lang))
        return
    api = ApiClient()
    try:
        category_id = data.get("category_id")
        training_format_id = data.get("training_format_id")
        detail = await api.get_school_detail(
            school_id,
            category_id=category_id,
            training_format_id=training_format_id
        )
    except Exception as e:
        await api.close()
        await handle_api_error(e, lang, message, state)
        return
    await api.close()
    tariffs = detail.get("tariffs", [])
    
    # Дополнительная фильтрация на стороне бота (на случай, если API не отфильтровал)
    # Логика: тариф показывается, если он не привязан (None) или совпадает с выбранными параметрами
    if category_id or training_format_id:
        filtered_tariffs = []
        for tariff in tariffs:
            tariff_category_id = tariff.get("category_id")
            tariff_training_format_id = tariff.get("training_format_id")
            
            # Проверяем соответствие категории: показываем если null или совпадает
            if category_id:
                if tariff_category_id is not None and tariff_category_id != category_id:
                    continue
            
            # Проверяем соответствие формата обучения: показываем если null или совпадает
            if training_format_id:
                if tariff_training_format_id is not None and tariff_training_format_id != training_format_id:
                    continue
            
            filtered_tariffs.append(tariff)
        tariffs = filtered_tariffs
    
    if not tariffs:
        await message.answer(t("no_tariffs", lang), reply_markup=main_menu(lang))
        await state.clear()
        return
    await send_event("school_opened", {"school_id": school_id}, bot_user_id=message.from_user.id)
    await state.update_data(school_id=school_id, school_detail=detail, tariffs=tariffs)
    
    # Формируем карточку автошколы согласно ТЗ
    school_name = get_name_by_lang(detail.get('name', {}), lang) or detail.get('name', {}).get('ru', '')
    rating = detail.get('rating', 0)
    trust_index = detail.get('trust_index', 0)
    address = detail.get('address', {})
    address_text = address.get('kz' if lang == "KZ" else 'ru', address.get('ru', ''))
    nearest_intake = detail.get('nearest_intake', {})
    intake_text = nearest_intake.get('text_kz' if lang == "KZ" else 'text_ru', nearest_intake.get('text_ru', ''))
    intake_date = nearest_intake.get('date')
    description = detail.get('description', {})
    description_text = description.get('kz' if lang == "KZ" else 'ru', description.get('ru', ''))
    
    card_text_ru = (
        f"{t('school_card_title', lang)}\n\n"
        f"<b>{school_name}</b>\n\n"
        f"{t('school_rating', lang)}: {rating}\n"
        f"{t('school_trust', lang)}: {trust_index}\n"
        f"{t('school_address', lang)}: {address_text}\n"
    )
    if intake_date or intake_text:
        card_text_ru += f"{t('school_intake', lang)}: "
        if intake_date:
            from datetime import datetime
            try:
                date_obj = datetime.fromisoformat(intake_date.replace('Z', '+00:00'))
                card_text_ru += date_obj.strftime("%d.%m.%Y")
            except:
                card_text_ru += intake_date
        if intake_text:
            if intake_date:
                card_text_ru += f" ({intake_text})"
            else:
                card_text_ru += intake_text
        card_text_ru += "\n"
    
    # Добавляем описание школы, если оно есть
    if description_text:
        card_text_ru += f"\n{description_text}\n"
    
    card_text_kz = (
        f"{t('school_card_title', lang)}\n\n"
        f"<b>{school_name}</b>\n\n"
        f"{t('school_rating', lang)}: {rating}\n"
        f"{t('school_trust', lang)}: {trust_index}\n"
        f"{t('school_address', lang)}: {address_text}\n"
    )
    if intake_date or intake_text:
        card_text_kz += f"{t('school_intake', lang)}: "
        if intake_date:
            from datetime import datetime
            try:
                date_obj = datetime.fromisoformat(intake_date.replace('Z', '+00:00'))
                card_text_kz += date_obj.strftime("%d.%m.%Y")
            except:
                card_text_kz += intake_date
        if intake_text:
            if intake_date:
                card_text_kz += f" ({intake_text})"
            else:
                card_text_kz += intake_text
        card_text_kz += "\n"
    
    # Добавляем описание школы, если оно есть
    if description_text:
        card_text_kz += f"\n{description_text}\n"
    
    card_text = card_text_kz if lang == "KZ" else card_text_ru
    
    # Кнопка "Записаться"
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    register_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("register_button", lang))]],
        resize_keyboard=True,
    )
    
    await state.set_state(SchoolFlow.school_card)
    await message.answer(card_text, reply_markup=register_keyboard, parse_mode="HTML")


@router.message(SchoolFlow.school_card)
async def schools_register_button(message: Message, state: FSMContext):
    """Обработка нажатия кнопки 'Записаться' на карточке школы"""
    lang = await get_language(state)
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        # Возврат к выбору школы
        data = await state.get_data()
        schools = data.get("schools", [])
        if schools:
            await state.set_state(SchoolFlow.school)
            opts = []
            for s in schools:
                name_dict = s.get('name', {})
                school_name = name_dict.get('kz' if lang == "KZ" else 'ru', name_dict.get('ru', ''))
                opts.append(f"{s['id']}: {school_name}")
            await message.answer(t("choose_school", lang), reply_markup=choices_keyboard(opts, lang))
        else:
            await state.clear()
            await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    
    # Проверяем, что нажата кнопка "Записаться"
    register_text_ru = t("register_button", "RU")
    register_text_kz = t("register_button", "KZ")
    if message.text not in [register_text_ru, register_text_kz]:
        # Если не кнопка "Записаться", показываем снова карточку
        data = await state.get_data()
        detail = data.get("school_detail", {})
        school_name = get_name_by_lang(detail.get('name', {}), lang) or detail.get('name', {}).get('ru', '')
        rating = detail.get('rating', 0)
        trust_index = detail.get('trust_index', 0)
        address = detail.get('address', {})
        address_text = address.get('kz' if lang == "KZ" else 'ru', address.get('ru', ''))
        nearest_intake = detail.get('nearest_intake', {})
        intake_text = nearest_intake.get('text_kz' if lang == "KZ" else 'text_ru', nearest_intake.get('text_ru', ''))
        intake_date = nearest_intake.get('date')
        description = detail.get('description', {})
        description_text = description.get('kz' if lang == "KZ" else 'ru', description.get('ru', ''))
        
        card_text_ru = (
            f"{t('school_card_title', lang)}\n\n"
            f"<b>{school_name}</b>\n\n"
            f"{t('school_rating', lang)}: {rating}\n"
            f"{t('school_trust', lang)}: {trust_index}\n"
            f"{t('school_address', lang)}: {address_text}\n"
        )
        if intake_date or intake_text:
            card_text_ru += f"{t('school_intake', lang)}: "
            if intake_date:
                from datetime import datetime
                try:
                    date_obj = datetime.fromisoformat(intake_date.replace('Z', '+00:00'))
                    card_text_ru += date_obj.strftime("%d.%m.%Y")
                except:
                    card_text_ru += intake_date
            if intake_text:
                if intake_date:
                    card_text_ru += f" ({intake_text})"
                else:
                    card_text_ru += intake_text
            card_text_ru += "\n"
        
        # Добавляем описание школы, если оно есть
        if description_text:
            card_text_ru += f"\n{description_text}\n"
        
        card_text_kz = (
            f"{t('school_card_title', lang)}\n\n"
            f"<b>{school_name}</b>\n\n"
            f"{t('school_rating', lang)}: {rating}\n"
            f"{t('school_trust', lang)}: {trust_index}\n"
            f"{t('school_address', lang)}: {address_text}\n"
        )
        if intake_date or intake_text:
            card_text_kz += f"{t('school_intake', lang)}: "
            if intake_date:
                from datetime import datetime
                try:
                    date_obj = datetime.fromisoformat(intake_date.replace('Z', '+00:00'))
                    card_text_kz += date_obj.strftime("%d.%m.%Y")
                except:
                    card_text_kz += intake_date
            if intake_text:
                if intake_date:
                    card_text_kz += f" ({intake_text})"
                else:
                    card_text_kz += intake_text
            card_text_kz += "\n"
        
        # Добавляем описание школы, если оно есть
        if description_text:
            card_text_kz += f"\n{description_text}\n"
        
        card_text = card_text_kz if lang == "KZ" else card_text_ru
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        register_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=t("register_button", lang))]],
            resize_keyboard=True,
        )
        await message.answer(card_text, reply_markup=register_keyboard, parse_mode="HTML")
        return
    
    # Нажата кнопка "Записаться" - показываем выбор тарифа
    data = await state.get_data()
    await send_event("register_button_clicked", {"school_id": data.get("school_id")}, bot_user_id=message.from_user.id)
    tariffs = data.get("tariffs", [])
    opts = []
    for tariff_item in tariffs:
        tariff_id = tariff_item.get('tariff_plan_id')
        # Используем название из API (name_ru/name_kz), если нет - fallback на code
        if lang == "KZ":
            tariff_name = tariff_item.get('name_kz') or tariff_item.get('name_ru') or tariff_item.get('code', '')
        else:
            tariff_name = tariff_item.get('name_ru') or tariff_item.get('code', '')
        opts.append(f"{tariff_id}: {tariff_name}")
    await state.set_state(SchoolFlow.tariff)
    await message.answer(t("choose_tariff", lang), reply_markup=choices_keyboard(opts, lang))


@router.message(SchoolFlow.tariff)
async def schools_choose_tariff(message: Message, state: FSMContext):
    lang = await get_language(state)
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        # Возврат к выбору школы
        data = await state.get_data()
        schools = data.get("schools", [])
        if schools:
            await state.set_state(SchoolFlow.school)
            opts = []
            for s in schools:
                name_dict = s.get('name', {})
                school_name = name_dict.get('kz' if lang == "KZ" else 'ru', name_dict.get('ru', ''))
                opts.append(f"{s['id']}: {school_name}")
            await message.answer(t("choose_school", lang), reply_markup=choices_keyboard(opts, lang))
        else:
            await state.clear()
            await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    data = await state.get_data()
    tariffs = data.get("tariffs", [])
    tariff = None
    for tariff_item in tariffs:
        if message.text.startswith(f"{tariff_item['tariff_plan_id']}:"):
            tariff = tariff_item
            break
    if not tariff:
        opts = []
        for tariff_item in tariffs:
            tariff_id = tariff_item.get('tariff_plan_id')
            tariff_name = get_tariff_name(tariff_item, lang)
            opts.append(f"{tariff_id}: {tariff_name}")
        await message.answer(t("choose_tariff", lang), reply_markup=choices_keyboard(opts, lang))
        return
    await send_event("tariff_selected", {"tariff_plan_id": tariff['tariff_plan_id']}, bot_user_id=message.from_user.id)
    await state.update_data(selected_tariff=tariff)
    
    # Получаем описание тарифа
    tariff_description = tariff.get('description_kz' if lang == "KZ" else 'description_ru', tariff.get('description_ru', ''))
    
    # Показываем описание тарифа, если оно есть
    if tariff_description:
        tariff_name = get_tariff_name(tariff, lang)
        tariff_price = tariff.get('price_kzt', 0)
        
        description_text = (
            f"<b>{tariff_name} — {tariff_price} KZT</b>\n\n"
            f"{tariff_description}"
        )
        await message.answer(description_text, parse_mode="HTML")
    
    await send_event("lead_form_opened", {"step": "name", "flow": "schools"}, bot_user_id=message.from_user.id)
    await state.set_state(SchoolFlow.name)
    await message.answer(t("enter_name", lang), reply_markup=back_keyboard(lang))


@router.message(SchoolFlow.name)
async def schools_enter_name(message: Message, state: FSMContext):
    lang = await get_language(state)
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        # Возврат к выбору тарифа
        data = await state.get_data()
        tariffs = data.get("tariffs", [])
        if tariffs:
            await state.set_state(SchoolFlow.tariff)
            opts = []
            for tariff_item in tariffs:
                tariff_id = tariff_item.get('tariff_plan_id')
                tariff_name = get_tariff_name(tariff_item, lang)
                opts.append(f"{tariff_id}: {tariff_name}")
            await message.answer(t("choose_tariff", lang), reply_markup=choices_keyboard(opts, lang))
        else:
            await state.clear()
            await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer(t("invalid_name", lang), reply_markup=back_keyboard(lang))
        return
    await state.update_data(name=name)
    await state.set_state(SchoolFlow.phone)
    await message.answer(t("enter_phone_contact", lang), reply_markup=phone_keyboard(lang))


@router.message(SchoolFlow.phone)
async def schools_enter_phone(message: Message, state: FSMContext):
    lang = await get_language(state)
    if is_main_menu(message.text, lang):
        await state.clear()
        await message.answer(t("main_menu", lang), reply_markup=main_menu(lang))
        return
    if is_back(message.text, lang):
        # Возврат к вводу имени
        await state.set_state(SchoolFlow.name)
        await message.answer(t("enter_name", lang), reply_markup=back_keyboard(lang))
        return
    
    # Обработка request_contact
    phone = None
    if message.contact:
        phone = normalize_phone(message.contact.phone_number)
    elif message.text:
        phone = normalize_phone(message.text)
    
    if not phone:
        await message.answer(t("invalid_phone", lang), reply_markup=phone_keyboard(lang))
        return
    await state.update_data(phone=phone)
    data = await state.get_data()
    detail = data["school_detail"]
    tariff = data["selected_tariff"]
    cities = data.get("cities", [])
    categories = data.get("categories", [])
    formats = data.get("formats", [])
    city_name = next((get_name_by_lang(c, lang) for c in cities if c["id"] == data['city_id']), str(data['city_id']))
    category_name = next((get_name_by_lang(c, lang) for c in categories if c["id"] == data['category_id']), str(data['category_id']))
    format_name = next((get_name_by_lang(f, lang) for f in formats if f["id"] == data['training_format_id']), str(data['training_format_id']))
    school_name = get_name_by_lang(detail.get('name', {}), lang) or detail.get('name', {}).get('ru', '')
    tariff_name = get_tariff_name(tariff, lang)
    confirm_text_ru = (
        f"{t('confirm_data', lang)}\n\n"
        f"Город: {city_name}\n"
        f"Категория: {category_name}\n"
        f"Тариф: {tariff_name} {tariff['price_kzt']} KZT\n"
        f"Автошкола: {school_name}\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {phone}"
    )
    confirm_text_kz = (
        f"{t('confirm_data', lang)}\n\n"
        f"Қала: {city_name}\n"
        f"Санат: {category_name}\n"
        f"Тариф: {tariff_name} {tariff['price_kzt']} KZT\n"
        f"Автошкола: {school_name}\n"
        f"Аты: {data['name']}\n"
        f"Телефон: {phone}"
    )
    text = confirm_text_kz if lang == "KZ" else confirm_text_ru
    await state.set_state(SchoolFlow.confirm)
    await message.answer(text, reply_markup=confirm_keyboard(lang))


@router.message(SchoolFlow.confirm, F.text.in_(["✅ Всё верно", "✅ Барлығы дұрыс"]))
async def schools_confirm(message: Message, state: FSMContext):
    lang = await get_language(state)
    data = await state.get_data()
    detail = data["school_detail"]
    tariff = data["selected_tariff"]
    api = ApiClient()
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
        "contact": {"name": data["name"], "phone": data["phone"]},
        "payload": {
            "city_id": data["city_id"],
            "category_id": data["category_id"],
            "training_format_id": data["training_format_id"],
            "school_id": data["school_id"],
            "tariff_plan_id": tariff["tariff_plan_id"],
            "tariff_price_kzt": tariff.get("price_kzt"),
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
    await send_event("lead_submitted", {"type": "SCHOOL"}, bot_user_id=message.from_user.id, lead_id=lead_id)
    
    # Получаем название категории для WhatsApp сообщения
    categories = data.get("categories", [])
    category_name = ""
    for c in categories:
        if c.get("id") == data.get("category_id"):
            category_name = get_name_by_lang(c, lang)
            break
    
    # Показываем благодарность согласно ТЗ
    await message.answer(t("thank_you", lang), reply_markup=main_menu(lang))
    
    # Генерируем WhatsApp ссылку с шаблоном (автоматически открывается)
    wa_link = build_wa_link_school(detail, data["name"], data["phone"], tariff, category_name, lang)
    if wa_link:
        await send_event("whatsapp_opened", {"flow": "schools", "school_id": data["school_id"]}, bot_user_id=message.from_user.id)
        # Отправляем ссылку для автоматического открытия WhatsApp
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="Открыть WhatsApp" if lang == "RU" else "WhatsApp ашу",
            url=wa_link
        )]])
        await message.answer(
            "Нажмите на кнопку, чтобы открыть WhatsApp" if lang == "RU" else "WhatsApp ашу үшін батырманы басыңыз",
            reply_markup=keyboard
        )
    
    await state.clear()


@router.message(SchoolFlow.confirm)
async def schools_confirm_any(message: Message, state: FSMContext):
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
        await state.set_state(SchoolFlow.name)
        await message.answer(t("enter_name", lang), reply_markup=back_keyboard(lang))
        return
    
    # Если не "Всё верно" и не "Исправить", показываем снова подтверждение
    data = await state.get_data()
    detail = data["school_detail"]
    tariff = data["selected_tariff"]
    cities = data.get("cities", [])
    categories = data.get("categories", [])
    city_name = next((get_name_by_lang(c, lang) for c in cities if c["id"] == data['city_id']), str(data['city_id']))
    category_name = next((get_name_by_lang(c, lang) for c in categories if c["id"] == data['category_id']), str(data['category_id']))
    school_name = get_name_by_lang(detail.get('name', {}), lang) or detail.get('name', {}).get('ru', '')
    tariff_name = get_tariff_name(tariff, lang)
    
    confirm_text_ru = (
        f"{t('confirm_data', lang)}\n\n"
        f"Город: {city_name}\n"
        f"Категория: {category_name}\n"
        f"Тариф: {tariff_name} {tariff['price_kzt']} KZT\n"
        f"Автошкола: {school_name}\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}"
    )
    confirm_text_kz = (
        f"{t('confirm_data', lang)}\n\n"
        f"Қала: {city_name}\n"
        f"Санат: {category_name}\n"
        f"Тариф: {tariff_name} {tariff['price_kzt']} KZT\n"
        f"Автошкола: {school_name}\n"
        f"Аты: {data['name']}\n"
        f"Телефон: {data['phone']}"
    )
    text = confirm_text_kz if lang == "KZ" else confirm_text_ru
    await message.answer(text, reply_markup=confirm_keyboard(lang))

