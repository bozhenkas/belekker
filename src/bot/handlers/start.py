from dotenv import load_dotenv
import os

from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardRemove

from bot.keyboards import kb_main_for_user, kb_buy_choice, kb_back_only
from bot.utils.messages import get_messages
from database.database import Database

load_dotenv()

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, **data):
    # привет и меню
    await message.answer(get_messages()['start_intro'], reply_markup=await kb_main_for_user())


@router.message(F.text == "информация")
async def info(message: Message):
    file_id = os.getenv("FILE_ID")
    if not file_id:
        msg = await message.answer_photo(
            types.FSInputFile("assets/afisha.jpg"),
            caption=get_messages()['info_text'],
        )
        file_id = msg.photo[-1].file_id
        with open(".env", "a") as f:
            f.write(f"\nFILE_ID={file_id}")
        os.environ["FILE_ID"] = file_id
    else:
        await message.answer_photo(file_id, caption=get_messages()['info_text'], reply_markup=await kb_back_only())

    # старый
    # msg = await message.answer_photo(types.FSInputFile("src/afisha_demo.jpg"), caption=get_messages()['info_text'],
    #                                  reply_markup=await kb_back_only())
    # print(msg.photo[-1].file_id)


@router.message(Command("cancel"))
async def admin_cancel(message: Message, state):
    # чистим состояние и пишем что отменено (скрытая команда для своих)
    await state.clear()
    await message.answer(get_messages()['canceled'])


@router.message(F.text == "↩️ назад")
async def back_to_menu(message: Message, **data):
    db: Database = data.get('db')
    await message.answer(get_messages()['start_intro'], reply_markup=await kb_main_for_user())


@router.message(F.text == "купить ещё")
@router.message(F.text == "купить билет")
async def buy_ticket(message: Message):
    await message.answer(get_messages()['emoji_placeholder'], reply_markup=await kb_back_only(),
                         disable_notification=True)
    await message.answer(get_messages()['choose_quantity'], reply_markup=await kb_buy_choice())
