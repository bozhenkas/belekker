# from aiogram import types
# import asyncio
#
#
# async def kb_choosing_price() -> types.InlineKeyboardMarkup:
#     anim_list = ['◻️', '◻️', '◻️', '◻️', '◻️']
#     for i in range(len(anim_list)):
#         anim_list[i] = '🌅'
#         k = [
#             [types.InlineKeyboardButton(
#                 text=anim_list[k],
#                 url="https://www.instagram.com/p/DN6MRP1iMA4/?igsh=bWJ5dzg4Zm12bzlm"
#             )]
#             for k in range(len(anim_list))
#         ]
#         return types.InlineKeyboardMarkup(inline_keyboard=k)
#         # await asyncio.sleep(1)
