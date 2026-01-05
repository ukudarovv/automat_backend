import urllib.parse

# Номера получателей WhatsApp согласно ТЗ
WHATSAPP_TESTS = "77026953357"  # +7 702 695 33 57 для тестов ПДД
WHATSAPP_SCHOOLS_INSTRUCTORS = "77788981396"  # +7 778 898 13 96 для автошкол и инструкторов (основной)
WHATSAPP_SCHOOLS_INSTRUCTORS_ALT = "77066768821"  # +7 706 676 88 21 (альтернативный, для ротации)
WHATSAPP_SCHOOLS = "77026345274"  # +7 702 634 5274 для автошкол (новый номер согласно ТЗ)


def build_wa_link_tests(phone: str, data: dict, category_name: str = "", lang: str = "RU") -> str:
    """Генерация WhatsApp ссылки для тестов согласно новому ТЗ (номер: +7 702 695 33 57)"""
    # Используем фиксированный номер согласно ТЗ
    owner_phone = WHATSAPP_TESTS  # +7 702 695 33 57
    if not owner_phone:
        return ""
    
    # Новый шаблон согласно ТЗ
    service_name = "Тесты по ПДД" if lang == "RU" else "ЖҚД тесттері"
    
    if lang == "KZ":
        text = (
            f"Здравствуйте!\n\n"
            f"Новая заявка с Telegram-бота.\n\n"
            f"👤 Имя: {data.get('name', '')}\n"
            f"🆔 ЖСН: {data.get('iin', '')}\n"
            f"💬 WhatsApp: {data.get('whatsapp', '')}\n"
            f"📘 Услуга: {service_name}\n"
        )
        if category_name:
            text += f"📗 Санат: {category_name}\n"
        text += f"🌐 Тіл: KZ"
    else:
        text = (
            f"Здравствуйте!\n\n"
            f"Новая заявка с Telegram-бота.\n\n"
            f"👤 Имя: {data.get('name', '')}\n"
            f"🆔 ИИН: {data.get('iin', '')}\n"
            f"💬 WhatsApp: {data.get('whatsapp', '')}\n"
            f"📘 Услуга: {service_name}\n"
        )
        if category_name:
            text += f"📗 Категория: {category_name}\n"
        text += f"🌐 Язык: RU"
    
    return f"https://wa.me/{owner_phone.replace('+', '')}?text={urllib.parse.quote(text)}"


def build_wa_link_school(detail: dict, name: str, phone: str, tariff: dict, category_name: str = "", lang: str = "RU", 
                         training_time: str = "", training_format: str = "", city_name: str = "", gearbox: str = "") -> str:
    """Генерация WhatsApp ссылки с шаблоном для автошколы согласно ТЗ"""
    # Используем новый номер согласно ТЗ: +7 702 634 5274
    owner_phone = WHATSAPP_SCHOOLS
    
    school_name = detail.get('name', {}).get('kz' if lang == "KZ" else 'ru', detail.get('name', {}).get('ru', ''))
    
    # Импортируем функцию перевода
    from i18n import t
    
    # training_time уже приходит как отображаемое название (не код)
    training_time_text = training_time
    
    # Формируем текст для КПП
    gearbox_text = ""
    if gearbox == "AUTOMATIC":
        gearbox_text = f" ({t('gearbox_automatic', lang)})"
    elif gearbox == "MANUAL":
        gearbox_text = f" ({t('gearbox_manual', lang)})"
    
    # Новый шаблон согласно ТЗ
    if lang == "KZ":
        text = (
            f"Здравствуйте!\n"
            f"Заявка на обучение:\n\n"
        )
        if city_name:
            text += f"Қала: {city_name}\n"
        if category_name:
            text += f"Санат: {category_name}{gearbox_text}\n"
        if training_format:
            text += f"Формат: {training_format}\n"
        if training_time_text:
            text += f"Уақыт: {training_time_text}\n"
        text += f"Автошкола: {school_name}\n"
        text += f"Аты: {name}\n"
        text += f"Телефон: {phone}"
    else:
        text = (
            f"Здравствуйте!\n"
            f"Заявка на обучение:\n\n"
        )
        if city_name:
            text += f"Город: {city_name}\n"
        if category_name:
            text += f"Категория: {category_name}{gearbox_text}\n"
        if training_format:
            text += f"Формат: {training_format}\n"
        if training_time_text:
            text += f"Время: {training_time_text}\n"
        text += f"Автошкола: {school_name}\n"
        text += f"Имя: {name}\n"
        text += f"Телефон: {phone}"
    
    return f"https://wa.me/{owner_phone.replace('+', '')}?text={urllib.parse.quote(text)}"


def build_wa_link_instructor(instructor_detail: dict, name: str, phone: str, category_name: str = "", lang: str = "RU", preferred_time: str = "", training_period: str = "") -> str:
    """Генерация WhatsApp ссылки с шаблоном для инструктора согласно ТЗ"""
    # Используем фиксированный номер согласно ТЗ
    owner_phone = WHATSAPP_SCHOOLS_INSTRUCTORS
    
    instructor_name = instructor_detail.get('display_name', '')
    service_name = "Инструктор" if lang == "RU" else "Нұсқаушы"
    
    # Импортируем функцию перевода
    from i18n import t
    
    # preferred_time уже приходит как отображаемое название (не код)
    preferred_time_text = preferred_time
    
    # Формируем текст для периода
    training_period_text = ""
    if training_period == "10_DAYS":
        training_period_text = t("training_period_10_days", lang)
    elif training_period == "MONTH":
        training_period_text = t("training_period_month", lang)
    elif training_period == "NO_MATTER":
        training_period_text = t("training_period_no_matter", lang)
    
    # Новый шаблон согласно ТЗ
    if lang == "KZ":
        text = (
            f"Здравствуйте!\n\n"
            f"Новая заявка с Telegram-бота.\n\n"
            f"👤 Имя: {name}\n"
            f"💬 WhatsApp: {phone}\n"
            f"📘 Услуга: {service_name} — {instructor_name}\n"
        )
        if category_name:
            text += f"📗 Санат: {category_name}\n"
        if preferred_time_text:
            text += f"⏰ {t('preferred_time_label', lang)}: {preferred_time_text}\n"
        if training_period_text:
            text += f"📅 {t('training_period_label', lang)}: {training_period_text}\n"
        text += f"🌐 Тіл: KZ"
    else:
        text = (
            f"Здравствуйте!\n\n"
            f"Новая заявка с Telegram-бота.\n\n"
            f"👤 Имя: {name}\n"
            f"💬 WhatsApp: {phone}\n"
            f"📘 Услуга: {service_name} — {instructor_name}\n"
        )
        if category_name:
            text += f"📗 Категория: {category_name}\n"
        if preferred_time_text:
            text += f"⏰ {t('preferred_time_label', lang)}: {preferred_time_text}\n"
        if training_period_text:
            text += f"📅 {t('training_period_label', lang)}: {training_period_text}\n"
        text += f"🌐 Язык: RU"
    
    return f"https://wa.me/{owner_phone.replace('+', '')}?text={urllib.parse.quote(text)}"


def build_wa_link_online(tariff_plan_name: str, first_name: str, last_name: str, iin: str, whatsapp: str, 
                         category_name: str = "", lang: str = "RU") -> str:
    """Генерация WhatsApp ссылки для онлайн-продуктов"""
    # Используем номер для автошкол: +7 702 634 5274
    owner_phone = WHATSAPP_SCHOOLS
    
    full_name = f"{first_name} {last_name}".strip()
    
    # Формируем текст сообщения
    if lang == "KZ":
        text = (
            f"Здравствуйте! Заявка на онлайн-обучение.\n\n"
            f"Тариф: {tariff_plan_name}\n"
        )
        if category_name:
            text += f"Санат: {category_name}\n"
        text += (
            f"ЖСН: {iin}\n"
            f"Аты: {full_name}\n"
            f"WhatsApp: {whatsapp}"
        )
    else:
        text = (
            f"Здравствуйте! Заявка на онлайн-обучение.\n\n"
            f"Тариф: {tariff_plan_name}\n"
        )
        if category_name:
            text += f"Категория: {category_name}\n"
        text += (
            f"ИИН: {iin}\n"
            f"Имя: {full_name}\n"
            f"WhatsApp: {whatsapp}"
        )
    
    return f"https://wa.me/{owner_phone.replace('+', '')}?text={urllib.parse.quote(text)}"

