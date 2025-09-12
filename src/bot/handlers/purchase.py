import os
import time
import asyncio
import json
import csv
import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards import (
    kb_quantity,
    kb_confirm_paid,
    kb_choosing_price,
    kb_buy_choice,
    admin_buttons,
    kb_promo_code,
)
from bot.states import PurchaseState
from bot.utils.messages import get_messages

from database.database import Database

router = Router()

_album_buffers: dict = {}
_album_meta: dict = {}
_album_tasks: dict = {}


async def forward_to_group_and_log(
        message: Message,
        qty: int,
        files: list,
        ts: int,
        data: dict,
        repost: bool,
        transaction_id: int,
        db: Database,
):
    try:
        # логируем метаданные (для альбома — список файлов через |)
        meta = {
            "user_id": message.from_user.id,
            "username": message.from_user.username,
            "qty": qty,
            "timestamp": ts,
            "repost": repost,
            "file": "|".join(f["filename"] for f in files),
        }
        # jsonl
        with open("cache/payments_log.jsonl", "a", encoding="utf-8") as jf:
            jf.write(json.dumps(meta, ensure_ascii=False) + "\n")
        # csv
        write_header = not os.path.exists("cache/payments_log.csv")
        with open("cache/payments_log.csv", "a", newline="", encoding="utf-8") as cf:
            w = csv.DictWriter(
                cf,
                fieldnames=["user_id", "username", "qty", "timestamp", "file"],
                extrasaction="ignore",
            )
            if write_header:
                w.writeheader()
            w.writerow(meta)
    except Exception:
        logging.exception("Ошибка при логировании")

    group_chat_id = data.get("group_chat_id") or data.get("admin_chat_id")
    if not group_chat_id:
        return

    uname = (
        ("@" + message.from_user.username)
        if message.from_user.username
        else (message.from_user.full_name or get_messages()["default_username"])
    )

    # сумма: берем прямо из транзакции
    total_amount = await db.get_transaction_amount(transaction_id)

    promo_label = get_messages()["promo_label"] if total_amount not in (750, 900) else (
        get_messages()["repost_true_label"] if repost else get_messages()["repost_false_label"])

    # сообщение модераторам
    caption_text = get_messages()["moderation_caption"].format(uname, qty, promo_label, total_amount)

    kb = await admin_buttons(transaction_id)

    if len(files) > 1:
        # альбом: отправляем все фото без подписи
        media = [types.InputMediaPhoto(media=f["file_id"]) for f in files]
        try:
            await message.bot.send_media_group(chat_id=group_chat_id, media=media, disable_notification=True)
        except Exception:
            logging.exception("Ошибка при отправке альбома")
            return

        # следом — инфо-сообщение с подписью и кнопками
        try:
            await message.bot.send_message(
                chat_id=group_chat_id,
                text=caption_text,
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception:
            logging.exception("Ошибка при отправке сообщения с кнопками")
    else:
        # одиночное фото: подпись + кнопки в одном сообщении
        await message.bot.send_photo(
            chat_id=group_chat_id,
            photo=files[0]["file_id"],
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=kb,
        )


@router.callback_query(F.data == "buy:1")
async def buy_one(call: CallbackQuery, state: FSMContext):
    # один билет — сначала показываем цены (с/без репоста)
    await state.update_data(qty=1, came_from="one")
    await call.message.edit_text(get_messages()["choosing_price"], reply_markup=await kb_choosing_price())
    await state.set_state(PurchaseState.choosing_price)
    await call.answer()


@router.callback_query(F.data == "buy:more")
async def buy_more(call: CallbackQuery, state: FSMContext):
    # спрашиваем сколько
    await state.update_data(came_from="more")
    await call.message.edit_text(get_messages()["choose_quantity"], reply_markup=await kb_quantity())
    await state.set_state(PurchaseState.choosing_quantity)
    await call.answer()


@router.callback_query(PurchaseState.choosing_quantity, F.data.startswith("qty:"))
async def choose_qty(call: CallbackQuery, state: FSMContext):
    # несколько билетов — сначала показываем цены (с/без репоста)
    qty = int(call.data.split(":")[1])
    await state.update_data(qty=qty)
    await call.message.edit_text(get_messages()["choosing_price"], reply_markup=await kb_choosing_price())
    await state.set_state(PurchaseState.choosing_price)
    await call.answer()


@router.callback_query(PurchaseState.choosing_price, F.data == "back")
@router.callback_query(PurchaseState.choosing_quantity, F.data == "back")
async def back_from_qty(call: CallbackQuery, state: FSMContext):
    # назад к выбору купить 1/больше (инлайн)
    await state.clear()
    await call.message.edit_text(get_messages()["choose_quantity"], reply_markup=await kb_buy_choice())
    await call.answer()


@router.callback_query(PurchaseState.waiting_payment_confirm, F.data == "back")
async def back_from_requisites(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Удаляем отладочный вывод
    # await call.message.answer('data:', str(data))

    # Определяем, куда вернуться в зависимости от того, как пользователь пришел к выбору цены
    # Если был введен промокод, то нужно вернуться к выбору промокода.
    # Иначе - к выбору цены (с репостом/без).
    if data.get("promo_code"):
        # Если был промокод, возвращаемся к его вводу
        await call.message.edit_text(get_messages()["ask_promo_code"], reply_markup=await kb_promo_code())
        await state.set_state(PurchaseState.waiting_promo_code)
    else:
        # Иначе возвращаемся к выбору цены (с репостом/без), сохраняя qty
        await call.message.edit_text(get_messages()["choosing_price"], reply_markup=await kb_choosing_price())
        await state.set_state(PurchaseState.choosing_price)

    await call.answer()


@router.callback_query(PurchaseState.waiting_payment_confirm, F.data == "paid:confirm")
async def ask_proof(call: CallbackQuery, state: FSMContext):
    # просим скрин — редактируем то же сообщение
    msg = (
        get_messages()["ask_proof_repost"]
        if (await state.get_data()).get("repost")
        else get_messages()["ask_proof_no_repost"]
    )
    await call.message.edit_text(msg)
    await state.set_state(PurchaseState.waiting_payment_proof)
    await call.answer()


@router.callback_query(PurchaseState.choosing_price, F.data.startswith("repost:"))
async def choose_price(call: CallbackQuery, state: FSMContext):
    repost_val = call.data.split(":")[1]
    repost = repost_val == "true"
    await state.update_data(repost=repost)
    sd = await state.get_data()
    qty = int(sd.get("qty", 1))

    # per_ticket = 900 if not repost else 0  # если репост, цену подтянем позже. Это была ошибка.
    # Корректная логика: 750 с репостом, 900 без репоста.
    per_ticket = 750 if repost else 1100
    total_amount = per_ticket * qty
    await state.update_data(amount=total_amount)

    if repost:
        # Если выбран репост (т.е. цена 750), предлагаем ввести промокод.
        # Если промокод будет введен, total_amount может измениться.
        await call.message.edit_text(get_messages()["ask_promo_code"], reply_markup=await kb_promo_code())
        await state.set_state(PurchaseState.waiting_promo_code)
    else:
        # Если без репоста (цена 900), сразу к реквизитам.
        await call.message.edit_text(
            get_messages()["payment_requisites"].format(total_amount),
            reply_markup=await kb_confirm_paid(),
        )
        await state.set_state(PurchaseState.waiting_payment_confirm)

    await call.answer()


@router.callback_query(PurchaseState.waiting_promo_code, F.data == "back")
async def back_from_promo(call: CallbackQuery, state: FSMContext):
    # При возврате из состояния ввода промокода, возвращаемся к выбору цены (с репостом/без)
    await state.update_data(promo_code=None)  # Очищаем промокод, если пользователь вернулся
    await call.message.edit_text(get_messages()["choosing_price"], reply_markup=await kb_choosing_price())
    await state.set_state(PurchaseState.choosing_price)
    await call.answer()


@router.callback_query(F.data == "back")
async def back(call: CallbackQuery, state: FSMContext):
    # этот обработчик ловит "back" из kb_back_only, который используется в info, buy_ticket
    # и должен возвращать в главное меню (ReplyKeyboard)
    # Если FSM-состояние активно, оно будет обработано более специфичными хэндлерами выше.
    # Если нет активного FSM-состояния, этот хэндлер сработает.
    await state.clear()
    await call.message.edit_text(get_messages()['choose_quantity'], reply_markup=await kb_buy_choice())
    await call.answer()


@router.message(PurchaseState.waiting_promo_code, F.text)
async def check_promo_code(message: Message, state: FSMContext, db: Database):
    promo_code = message.text.strip()
    promo_data = await db.get_promo_code(promo_code)

    # Проверка, что promo_data не None и что промокод не использован полностью.
    if not promo_data or promo_data['used_count'] >= promo_data['usage_limit']:
        await message.answer(get_messages()["promo_code_invalid"])
        return

    # Получаем value для этого промокода
    promo_value = promo_data['value']  # Используем значение из promo_data, чтобы избежать лишнего запроса
    if promo_value is None:  # На случай, если каким-то образом value оказалось None (чего быть не должно)
        await message.answer(get_messages()["promo_code_invalid"])
        return

    sd = await state.get_data()
    qty = int(sd.get("qty", 1))
    total_amount = promo_value * qty

    # Сохраняем промо и сумму
    await state.update_data(promo_code=promo_code, amount=total_amount)

    await message.answer(
        get_messages()["payment_requisites"].format(total_amount),
        reply_markup=await kb_confirm_paid(),
    )
    await state.set_state(PurchaseState.waiting_payment_confirm)


@router.message(PurchaseState.waiting_payment_proof, F.photo)
async def got_proof(message: Message, state: FSMContext, **data):
    # создаем транзакцию в БД
    sd = await state.get_data()
    qty = sd.get("qty", 1)
    repost = sd.get("repost", False)
    total_amount = sd.get("amount")
    promo_code = sd.get("promo_code", None)
    db: Database = data.get("db")  # Get the db object from workflow_data

    # Создаем транзакцию в БД ОДИН РАЗ, перед любым асинхронным ожиданием
    try:
        transaction_id = await db.create_transaction(
            user_telegram_id=message.from_user.id,
            quantity=qty,
            amount=total_amount,
            promo_code=promo_code
        )
    except ValueError as e:
        await message.answer(f"Произошла ошибка при создании транзакции: {e}")
        logging.error(f"Error creating transaction: {e}")
        return

    # собираем альбом в буфер и шлем один раз
    mgid = getattr(message, "media_group_id", None)
    os.makedirs("cache", exist_ok=True)
    p = message.photo[-1]
    file_id = p.file_id
    file = await message.bot.get_file(file_id)
    ts = int(time.time())
    filename = f"cache/pay_{message.from_user.id}_{ts}_{file_id[-8:]}.jpg"
    try:
        await message.bot.download(file, destination=filename)
    except Exception:
        pass

    if mgid:
        key = (message.from_user.id, mgid)
        _album_buffers.setdefault(key, []).append({"file_id": message.photo[-1].file_id, "filename": filename})
        # обновляем метаданные каждый раз (последние данные победят)
        _album_meta[key] = {"ts": ts, "qty": qty, "data": data, "chat_id": message.chat.id, "repost": repost}

        # дебаунсим отправку: пересоздаём задачу на каждый новый элемент альбома
        prev_task = _album_tasks.get(key)
        if prev_task and not prev_task.done():
            try:
                prev_task.cancel()
            except Exception:
                pass

        async def _flush(local_key=key, local_transaction_id=transaction_id):
            try:
                await asyncio.sleep(1.2)
            except asyncio.CancelledError:
                return
            if _album_tasks.get(local_key) is not asyncio.current_task():
                return
            files = _album_buffers.pop(local_key, [])
            meta = _album_meta.pop(local_key, None) or {}
            _album_tasks.pop(local_key, None)
            if files:
                await forward_to_group_and_log(
                    message,
                    meta.get("qty", qty),
                    files,
                    meta.get("ts", ts),
                    meta.get("data", data),
                    meta.get("repost", repost),
                    local_transaction_id,
                    db
                )
                await message.answer(get_messages()["on_review"])
                await state.set_state(PurchaseState.on_review)

        task = asyncio.create_task(_flush())
        _album_tasks[key] = task
        return

    # одиночное фото — шлем сразу
    await forward_to_group_and_log(
        message,
        qty,
        [{"file_id": message.photo[-1].file_id, "filename": filename}],
        ts,
        data,
        repost,
        transaction_id,
        db
    )
    await message.answer(get_messages()["on_review"])
    await state.set_state(PurchaseState.on_review)
