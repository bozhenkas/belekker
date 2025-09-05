import logging
import os
from pathlib import Path
import secrets
import asyncio
from typing import Union
import aiogram
from dotenv import load_dotenv

from aiogram import Router, F, types
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from database.database import Database
from bot.keyboards import buy_more, buy_ticket_kb
from bot.utils.messages import get_messages
from bot.tickets.generator import TICKET_TEMPLATE_PATH, TICKETS_DIR, generate_ticket_image

ADMINS = [int(el) for el in os.getenv("ADMINS").split(",")]

load_dotenv()
router = Router()


async def _generate_promo(db: Database, admin_id: int, value: float = 750, usage_limit: int = 1) -> str | None:
    """Генерирует уникальный промокод с указанной суммой и количеством доступных использований."""
    import secrets, asyncio, logging

    code = secrets.token_hex(3).upper()  # генерим короткий промокод
    try:
        success = await db.create_promo_code(code=code, admin_telegram_id=admin_id, value=value,
                                             usage_limit=usage_limit)
        if not success:
            logging.warning(f"Сгенерированный промокод {code} уже существует. Повторная попытка.")
            return await _generate_promo(db, admin_id, value=value, usage_limit=usage_limit)
        await asyncio.sleep(0.5)  # небольшая пауза для надежности
        return code
    except Exception as e:
        logging.exception(f"Ошибка при создании промокода: {e}")
        return None


@router.message(Command("promo"), F.from_user.id.in_(ADMINS))
async def promo_command(message: Message, db: Database):
    """
    Команда для генерации нового промокода.
    Форматы:
      /promo             → промокод с номиналом 750 и 1 использованием
      /promo 600         → промокод с номиналом 600 и 1 использованием
      /promo 500 10      → промокод с номиналом 500 и 10 доступными использований
    """
    msgs = get_messages()
    parts = message.text.split()
    value = 750  # значение по умолчанию
    usage_limit = 1  # количество использований по умолчанию

    if len(parts) > 1:
        try:
            value = float(parts[1])
        except ValueError:
            await message.answer(msgs["promo_invalid_value"])
            return

    if len(parts) > 2:
        try:
            usage_limit = int(parts[2])
            if usage_limit < 1:
                raise ValueError
        except ValueError:
            await message.answer(msgs["promo_invalid_usage"])
            return

    msg = await message.answer(msgs["promo_generating"])
    promo_code = await _generate_promo(db, message.from_user.id, value=value, usage_limit=usage_limit)

    if promo_code:
        await msg.edit_text(msgs["promo"].format(promo_code, value, usage_limit))
    else:
        await msg.edit_text(msgs["promo_failed"])


@router.message(Command("afisha"), F.from_user.id.in_(ADMINS))
async def afisha_send_command(message: Message):
    channel_id = os.getenv("CHANNEL_ID")
    file_id = os.getenv("FILE_ID")
    if not file_id:
        msg = await message.bot.send_photo(chat_id=channel_id, photo=types.FSInputFile("assets/afisha.jpg"),
                                           caption=get_messages()['afisha'],
                                           reply_markup=await buy_ticket_kb())
        await message.answer('отправлено')
        file_id = msg.photo[-1].file_id
        with open(".env", "a") as f:
            f.write(f"\nFILE_ID={file_id}")
        os.environ["FILE_ID"] = file_id
    else:
        await message.bot.send_photo(chat_id=channel_id, photo=file_id, caption=get_messages()['afisha'],
                                     reply_markup=await buy_ticket_kb())
        await message.answer('отправлено')


@router.callback_query(F.data.startswith("approve:"))
async def approve(callback: CallbackQuery, db: Database):
    """
    Обработчик для кнопки 'подтвердить' от модератора.
    Подтверждает транзакцию, генерирует и отправляет билеты пользователю.
    """
    await callback.answer("Обрабатываю...")
    try:
        transaction_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.message.answer("Ошибка: некорректный ID транзакции.")
        return

    try:
        # Подтверждаем транзакцию в БД и получаем токены билетов
        new_tickets = await db.approve_transaction(transaction_id=transaction_id)

        # Редактируем сообщение модератора
        moderator_username = callback.from_user.username
        await callback.bot.edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=f"{callback.message.caption}\n\n[принято @{moderator_username}]",
            reply_markup=None
        )

        # Получаем данные транзакции для отправки билетов пользователю
        transaction_info = await db.get_transaction(transaction_id)
        user_id = transaction_info.get("user_telegram_id")

        # Отправляем общее сообщение пользователю перед билетами
        await callback.bot.send_message(
            chat_id=user_id,
            text=get_messages()[
                "ticket_delivered" if len(new_tickets) == 1 else "tickets_delivered"].format('🎟' * len(new_tickets)),
            reply_markup=None
        )

        # Генерируем и отправляем каждый билет отдельно
        for token in new_tickets:
            try:
                ticket_path = await generate_ticket_image(
                    token=token,
                    bot_username='be_lekker_bot',
                    template_path=TICKET_TEMPLATE_PATH,
                    qr_size=(750, 750),
                    qr_position=(170, 610),
                    output_dir=TICKETS_DIR
                )

                await callback.bot.send_document(
                    chat_id=user_id,
                    document=types.FSInputFile(ticket_path),
                    disable_notification=True,
                    reply_markup=await buy_more()
                )

                # Удаляем временный файл билета после отправки
                os.remove(ticket_path)
            except Exception as e:
                logging.error(f"Failed to generate or send ticket {token}: {e}")
                await callback.bot.send_message(
                    chat_id=user_id,
                    text=f"Произошла ошибка при отправке одного из ваших билетов. Пожалуйста, обратитесь к администратору.\nТокен билета: `{token}`",
                    disable_notification=True
                )


    except ValueError as e:
        # Обработка ошибок, которые выдает database.py
        await callback.message.answer(f"Ошибка: {e}")
    except Exception as e:
        logging.exception("Ошибка в обработчике одобрения транзакции.")
        await callback.message.answer("Произошла непредвиденная ошибка при обработке.")


@router.callback_query(F.data.startswith("reject:"))
async def reject(callback: CallbackQuery, db: Database):
    """
    Обработчик для кнопки 'Отклонить' от модератора.
    Отклоняет транзакцию и уведомляет пользователя.
    """
    await callback.answer("Отклоняю...")
    try:
        transaction_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.message.answer("Ошибка: некорректный ID транзакции.")
        return

    try:
        # Отклоняем транзакцию в БД
        await db.reject_transaction(transaction_id=transaction_id)

        # Редактируем сообщение модератора
        moderator_username = callback.from_user.username
        await callback.bot.edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=f"{callback.message.caption}\n\n[принято @{moderator_username}]",
            reply_markup=None
        )

        # Получаем данные транзакции для отправки сообщения пользователю
        transaction_info = await db.get_transaction(transaction_id)
        user_id = transaction_info.get("user_telegram_id")

        # Отправляем сообщение пользователю
        await callback.bot.send_message(chat_id=user_id, text=get_messages()['rejected'])

    except ValueError as e:
        # Обработка ошибок, которые выдает database.py
        await callback.message.answer(f"Ошибка: {e}")
    except Exception as e:
        logging.exception("Ошибка в обработчике отклонения транзакции.")
        await callback.message.answer("Произошла непредвиденная ошибка при обработке.")


@router.message(Command("stats_info"), F.from_user.id.in_(ADMINS))
async def stats_info_command(message: Message, db: Database):
    """
    Показывает общую статистику по боту.
    """
    try:
        total_users = await db.count_users()
        total_active_tickets = await db.count_tickets()
        total_sales_amount = await db.get_total_sales_amount()

        stats_message = (
            f"📊 <b>Статистика по боту:</b>\n\n"
            f"👥 Всего пользователей: <b>{total_users}</b>\n"
            f"🎟️ Всего активных билетов: <b>{total_active_tickets}</b>\n"
            f"💰 Общая сумма продаж: <b>{total_sales_amount:.2f}</b> руб."
        )

        await message.answer(stats_message, parse_mode='HTML')
    except Exception as e:
        logging.exception("Ошибка при получении статистики.")
        await message.answer("Не удалось получить статистику. Пожалуйста, проверьте логи.")


@router.message(Command("stats_transactions"), F.from_user.id.in_(ADMINS))
async def stats_transactions_command(message: Message, db: Database):
    """
    Экспортирует и отправляет CSV-файл со всеми транзакциями.
    """
    try:
        msg = await message.answer("🔄 Генерирую файл со списком транзакций...")
        csv_file_path = await db.export_transactions_csv()

        await message.answer_document(
            document=types.FSInputFile(csv_file_path),
            caption="Отчет по всем транзакциям."
        )

        await msg.delete()
        os.remove(csv_file_path)  # Удаляем временный файл
    except Exception as e:
        logging.exception("Ошибка при экспорте транзакций.")
        await message.answer("Не удалось сгенерировать отчет. Пожалуйста, проверьте логи.")


@router.message(Command("stats_tickets"), F.from_user.id.in_(ADMINS))
async def stats_tickets_command(message: Message, db: Database):
    """
    Экспортирует и отправляет CSV-файл со всеми билетами.
    """
    try:
        msg = await message.answer("🔄 Генерирую файл со списком билетов...")
        csv_file_path = await db.export_tickets_csv()

        await message.answer_document(
            document=types.FSInputFile(csv_file_path),
            caption="Отчет по всем билетам."
        )

        await msg.delete()
        os.remove(csv_file_path)  # Удаляем временный файл
    except Exception as e:
        logging.exception("Ошибка при экспорте билетов.")
        await message.answer("Не удалось сгенерировать отчет. Пожалуйста, проверьте логи.")


@router.message(Command("stats_users"), F.from_user.id.in_(ADMINS))
async def stats_users_command(message: Message, db: Database):
    """
    Экспортирует и отправляет CSV-файл со всеми пользователями и их активными билетами.
    """
    try:
        msg = await message.answer("🔄 Генерирую файл со списком пользователей...")
        csv_file_path = await db.export_users_csv()

        await message.answer_document(
            document=types.FSInputFile(csv_file_path),
            caption="Отчет по пользователям и активным билетам."
        )

        await msg.delete()
        os.remove(csv_file_path)  # Удаляем временный файл
    except Exception as e:
        logging.exception("Ошибка при экспорте пользователей.")
        await message.answer("Не удалось сгенерировать отчет. Пожалуйста, проверьте логи.")
