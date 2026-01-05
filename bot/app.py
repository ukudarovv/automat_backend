import asyncio
import signal
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from config import BOT_TOKEN, DEFAULT_LANGUAGE
from i18n import t
from keyboards.common import main_menu, language_keyboard
from handlers import tests_flow, schools_flow, instructors_flow, language_flow, certificate_flow, online_flow
from services.analytics import send_event
from states_language import LanguageFlow

logger = logging.getLogger(__name__)


async def get_user_language(message: Message, state: FSMContext) -> str:
    """Получить язык пользователя из state или вернуть дефолтный"""
    data = await state.get_data()
    return data.get("language", DEFAULT_LANGUAGE)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TELEGRAM_TOKEN is not set")

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    root_router = Router()

    @root_router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext):
        # Отслеживаем вход в бот
        await send_event("bot_started", {}, bot_user_id=message.from_user.id)
        
        # Проверяем, есть ли уже язык в state
        data = await state.get_data()
        lang = data.get("language")
        
        if not lang:
            # Если языка нет - показываем выбор
            await state.set_state(LanguageFlow.select)
            await message.answer(
                t("language_select", DEFAULT_LANGUAGE),
                reply_markup=language_keyboard(),
            )
        else:
            # Если язык уже выбран - показываем главное меню
            await message.answer(
                t("main_welcome", lang),
                reply_markup=main_menu(lang),
            )

    # Обработчики кнопок главного меню - должны работать в любом состоянии
    @root_router.message(F.text.in_(["Главное меню", "Басты мәзір", "главное меню", "басты мәзір"]))
    async def back_to_menu(message: Message, state: FSMContext):
        lang = await get_user_language(message, state)
        await state.clear()
        await message.answer(t("main_welcome", lang), reply_markup=main_menu(lang))
    
    # Обработчик "Выбор автошколы" → поток автошкол
    @root_router.message(F.text.in_([
        "Выбор автошколы",
        "Автошкола таңдау",
    ]))
    async def handle_no_license(message: Message, state: FSMContext):
        await state.clear()
        lang = await get_user_language(message, state)
        await send_event("intent_selected", {"intent": "NO_LICENSE"}, bot_user_id=message.from_user.id)
        # Сохраняем intent в state
        await state.update_data(main_intent="NO_LICENSE", language=lang)
        # Переход в поток автошкол
        from handlers.schools_flow import schools_start
        await schools_start(message, state)
    
    # Обработчик "Записаться на вождение" → поток инструкторов
    @root_router.message(F.text.in_([
        "Записаться на вождение",
        "Жүргізуге жазылу",
    ]))
    async def handle_has_license(message: Message, state: FSMContext):
        await state.clear()
        lang = await get_user_language(message, state)
        await send_event("intent_selected", {"intent": "REFRESH"}, bot_user_id=message.from_user.id)
        # Сохраняем intent в state
        await state.update_data(main_intent="REFRESH", language=lang)
        # Переход в поток инструкторов
        from handlers.instructors_flow import instructors_start
        await instructors_start(message, state)
    
    # Обработчик "Тесты по ПДД" → поток тестов
    @root_router.message(F.text.in_([
        "📘 Тесты по ПДД",
        "📘 ЖҚД тесттері",
    ]))
    async def handle_tests_menu(message: Message, state: FSMContext):
        await state.clear()
        lang = await get_user_language(message, state)
        await send_event("intent_selected", {"intent": "TESTS"}, bot_user_id=message.from_user.id)
        # Сохраняем intent в state
        await state.update_data(main_intent="TESTS", language=lang)
        # Переход в поток тестов
        from handlers.tests_flow import tests_start
        await tests_start(message, state)
    
    # Обработчик "Онлайн-обучение" → поток онлайн-продуктов
    @root_router.message(F.text.in_([
        "💻 Онлайн-обучение",
        "💻 Онлайн оқыту",
    ]))
    async def handle_online_training(message: Message, state: FSMContext):
        await state.clear()
        lang = await get_user_language(message, state)
        await send_event("intent_selected", {"intent": "ONLINE"}, bot_user_id=message.from_user.id)
        # Сохраняем intent в state
        await state.update_data(main_intent="ONLINE", language=lang)
        # Переход в поток онлайн-обучения
        from handlers.online_flow import online_start
        await online_start(message, state)

    # Порядок важен: более специфичные роутеры должны быть первыми
    dp.include_router(language_flow.router)
    dp.include_router(certificate_flow.router)
    dp.include_router(tests_flow.router)
    dp.include_router(online_flow.router)
    dp.include_router(schools_flow.router)
    dp.include_router(instructors_flow.router)
    dp.include_router(root_router)  # Общие обработчики в конце

    # Обработка сигналов для graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        shutdown_event.set()

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Запускаем polling в фоне и ждем сигнала завершения
        polling_task = asyncio.create_task(dp.start_polling(bot))
        
        # Ждем сигнала завершения
        await shutdown_event.wait()
        
        # Останавливаем polling
        logger.info("Stopping polling...")
        await dp.stop_polling()
        polling_task.cancel()
        
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
            
    except Exception as e:
        logger.error(f"Error in polling: {e}", exc_info=True)
        raise
    finally:
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise

