from aiogram import types

from bot.utils.messages import get_messages


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


async def kb_mark_ticket_used(token: str) -> types.InlineKeyboardMarkup:
    """
    Создает клавиатуру с одной кнопкой "отметить" для погашения билета.
    В callback_data зашивается токен билета.
    """
    msgs = get_messages()
    k = [[
        types.InlineKeyboardButton(
            text=msgs['ticket_scan_button_mark'],
            callback_data=f"mark_ticket:{token}"
        )
    ]]
    return types.InlineKeyboardMarkup(inline_keyboard=k)


async def feedback_kb() -> types.InlineKeyboardMarkup:
    k = [
        # [types.InlineKeyboardButton(text='форма обратки', url='https://forms.gle/kDFiVgimnExw9aAi8')],
        [types.InlineKeyboardButton(text='инстаграм',
                                    url='https://www.instagram.com/belekkerx?igsh=MXF6bDF5cmhzbGV3dg%3D%3D&utm_source=qr'),
         types.InlineKeyboardButton(text='телега', url='https://t.me/be_lekker')]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=k)
