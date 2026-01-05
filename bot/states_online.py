from aiogram.fsm.state import State, StatesGroup


class OnlineFlow(StatesGroup):
    product_choice = State()  # Выбор продукта (ПДД-тесты / START / PRO)
    category = State()  # Только для ПДД-тестов
    first_name = State()
    last_name = State()
    iin = State()
    whatsapp = State()
    confirm = State()

