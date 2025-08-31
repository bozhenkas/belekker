from aiogram import types


async def buy_ticket_kb() -> types.InlineKeyboardMarkup:
    # выбор покупки: один или больше
    k = [
        [types.InlineKeyboardButton(text='купить билет!', url='https://t.me/be_lekker_bot')]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=k)


async def admin_buttons(transaction_id: int) -> types.InlineKeyboardMarkup:
    # админская клавиатура подтверждения/отклонения
    k = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(
            text="подтвердить",
            callback_data=f"approve:{transaction_id}"
        ),
        types.InlineKeyboardButton(
            text="отклонить",
            callback_data=f"reject:{transaction_id}"
        )
    ]])
    return k