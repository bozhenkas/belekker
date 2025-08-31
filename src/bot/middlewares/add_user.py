import asyncio
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Awaitable, Dict, Any


class AddUserMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self._lock = asyncio.Lock()  # ограничиваем одновременный доступ

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        db = data.get("db")
        user = data.get('event_from_user')
        if db and user:
            # оборачиваем вызов add_user в lock, чтобы избежать гонки
            async with self._lock:
                try:
                    await db.add_user(user.id, user.username or "")
                except Exception:
                    pass

        return await handler(event, data)
