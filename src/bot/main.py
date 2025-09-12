import asyncio
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.middlewares import AddUserMiddleware
from bot.handlers import start, purchase, admin
from database.database import Database

load_dotenv()


async def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN не найден в .env")

    group_chat_id = os.getenv("CHAT_ID")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=MemoryStorage())

    db = Database()
    await db.connect()

    dp.workflow_data.update({
        "db": db,
        "group_chat_id": int(group_chat_id) if group_chat_id else None,
    })

    dp.message.middleware(AddUserMiddleware())
    dp.callback_query.middleware(AddUserMiddleware())

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(purchase.router)

    try:
        # await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
