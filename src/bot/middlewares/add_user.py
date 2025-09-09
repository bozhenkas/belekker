# src/bot/middlewares/add_user.py

import asyncio
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Awaitable, Dict, Any


class AddUserMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self._lock = asyncio.Lock()

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        db = data.get("db")
        user = data.get('event_from_user')
        if db and user:
            # формируем полное имя пользователя
            full_name = " ".join(filter(None, [user.first_name, user.last_name]))

            async with self._lock:
                try:
                    # Передаем все три параметра в метод add_user
                    await db.add_user(user.id, user.username or "", full_name)
                except Exception:
                    pass

        return await handler(event, data)
