from aiogram import types


async def kb_main_for_user() -> types.ReplyKeyboardMarkup:
    k = [
        [types.KeyboardButton(text='купить билет'), ],
        [types.KeyboardButton(text='информация')]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=k, resize_keyboard=True, is_persistent=False)
    return keyboard


async def buy_more() -> types.ReplyKeyboardMarkup:
    k = [[types.KeyboardButton(text='купить ещё')]]
    return types.ReplyKeyboardMarkup(keyboard=k, resize_keyboard=True, is_persistent=False)


async def kb_back_only() -> types.ReplyKeyboardMarkup:
    k = [[types.KeyboardButton(text='↩️ назад')]]
    return types.ReplyKeyboardMarkup(keyboard=k, resize_keyboard=True, is_persistent=False)
