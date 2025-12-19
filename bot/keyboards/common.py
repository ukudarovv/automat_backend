from typing import List

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from i18n import t


def language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Русский"), KeyboardButton(text="Қазақша")],
        ],
        resize_keyboard=True,
    )


def main_menu(lang: str = "RU"):
    """Главное меню с 3 интентами согласно новому ТЗ"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("no_license", lang))],
            [KeyboardButton(text=t("has_license", lang))],
            [KeyboardButton(text=t("has_certificate", lang))],
        ],
        resize_keyboard=True,
    )


def back_keyboard(lang: str = "RU"):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("back", lang))],
            [KeyboardButton(text=t("main_menu", lang))],
        ],
        resize_keyboard=True,
    )


def phone_keyboard(lang: str = "RU"):
    """Клавиатура для ввода телефона с кнопкой request_contact"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("enter_phone_contact", lang), request_contact=True)],
            [KeyboardButton(text=t("back", lang))],
            [KeyboardButton(text=t("main_menu", lang))],
        ],
        resize_keyboard=True,
    )


def confirm_keyboard(lang: str = "RU"):
    """Клавиатура для подтверждения с кнопками 'Всё верно' / 'Исправить'"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("all_correct", lang))],
            [KeyboardButton(text=t("fix", lang))],
            [KeyboardButton(text=t("main_menu", lang))],
        ],
        resize_keyboard=True,
    )


def choices_keyboard(options: List[str], lang: str = "RU"):
    rows = [[KeyboardButton(text=opt)] for opt in options]
    rows.append([KeyboardButton(text=t("back", lang)), KeyboardButton(text=t("main_menu", lang))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

