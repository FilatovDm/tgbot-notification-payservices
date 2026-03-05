from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import get_settings
from database import init_db
from handlers import router as main_router
from scheduler import setup_scheduler


async def main() -> None:
    settings = get_settings()

    await init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_router(main_router)

    scheduler = AsyncIOScheduler()
    setup_scheduler(scheduler, bot)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

