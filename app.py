import logging
from aiogram import executor

from loader import dp
import middlewares, filters, handlers
from utils.notify_admins import on_startup_notify
from utils.set_bot_commands import set_default_commands
from utils.db_api.database import create_tables
from utils.scheduler import setup_scheduler, load_user_reminders

logger = logging.getLogger(__name__)


async def on_startup(dispatcher):
    # Jadvallarni yaratish (yangi modellar ham qo'shildi)
    await create_tables()
    logger.info("Database tables created/verified")

    # Default komandalar
    await set_default_commands(dispatcher)

    # Adminga xabar
    await on_startup_notify(dispatcher)

    # Scheduler ishga tushirish
    setup_scheduler()

    # Mavjud eslatmalarni schedule qilish
    await load_user_reminders()

    logger.info("Bot started successfully")


async def on_shutdown(dispatcher):
    # aiohttp session ni yopish
    try:
        from services.drf_client import close_session
        await close_session()
        logger.info("aiohttp session closed")
    except Exception as e:
        logger.warning(f"Session close error: {e}")


if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)
