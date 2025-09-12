from aiogram import types


async def kb_buy_choice() -> types.InlineKeyboardMarkup:
    # выбор покупки: один или больше
    k = [
        [types.InlineKeyboardButton(text='купить 1 билет', callback_data='buy:1')],
        [types.InlineKeyboardButton(text='купить больше билетов', callback_data='buy:more')],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=k)


async def kb_choosing_price() -> types.InlineKeyboardMarkup:
    # выбор покупки: один или больше
    k = [
        [
            types.InlineKeyboardButton(text='⇉ оплатить ⇇', callback_data='repost:false')],
        [types.InlineKeyboardButton(text='подписаться на инст',
                                    url='https://www.instagram.com/p/DN6MRP1iMA4/?igsh=bWJ5dzg4Zm12bzlm')],
        [types.InlineKeyboardButton(text='⤝ назад', callback_data='back')]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=k)


async def kb_quantity() -> types.InlineKeyboardMarkup:
    # выбор количества
    k = [[types.InlineKeyboardButton(text=str(n), callback_data=f'qty:{n}')] for n in [2, 3, 4]]
    k.append([types.InlineKeyboardButton(text='⤝ назад', callback_data='back')])
    return types.InlineKeyboardMarkup(inline_keyboard=k)


async def kb_confirm_paid() -> types.InlineKeyboardMarkup:
    k = [
        [types.InlineKeyboardButton(text='я перевел', callback_data='paid:confirm')],
        [types.InlineKeyboardButton(text='⤝ назад', callback_data='back')]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=k)


async def kb_promo_code() -> types.InlineKeyboardMarkup:
    k = [
        [types.InlineKeyboardButton(text='⤝ назад', callback_data='back')],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=k)
