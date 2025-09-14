import asyncpg
import csv
import os
import time
import uuid
from datetime import datetime
from .config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """
        Создает пул подключений к базе данных.
        Предполагается, что структура БД (таблицы, триггеры) уже создана
        с помощью отдельного скрипта инициализации.
        """
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                min_size=1,
                max_size=10,
                max_inactive_connection_lifetime=30,
                max_queries=50000
            )
            print("Пул подключений к базе данных успешно создан.")

    async def close(self):
        """Закрывает пул подключений."""
        if self.pool:
            await self.pool.close()
            print("Пул подключений закрыт.")

    # --- Методы для работы с пользователями ---

    async def add_user(self, telegram_id: int, username: str, name: str) -> bool:  # <-- Добавили name
        """
        Добавляет нового пользователя в базу данных.
        Если пользователь существует, обновляет его username и name.
        Возвращает True, если пользователь был добавлен, и False, если обновлен.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                INSERT INTO users (telegram_id, username, name)
                VALUES ($1, $2, $3)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    name = EXCLUDED.name,
                    created_at = users.created_at;
                """,
                telegram_id, username, name
            )
            # INSERT ... возвращает "INSERT 0 1", если была вставка
            return result.startswith("INSERT")

    async def get_user_by_telegram_id(self, telegram_id: int):
        """Возвращает данные пользователя по его telegram_id."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1", telegram_id
            )

    async def count_users(self) -> int:
        """Возвращает общее количество пользователей."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM users")

    # --- Методы для работы с транзакциями (покупками) ---

    async def create_transaction(self, user_telegram_id: int, quantity: int, amount: float,
                                 promo_code: str | None = None) -> int:
        """
        Создает новую транзакцию со статусом 'on_check'.
        Если указан промокод, он будет применен.
        Возвращает ID созданной транзакции.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                promo_code_id = None
                if promo_code:
                    # Находим ID промокода. Проверяем, что использований меньше лимита
                    promo_code_id = await conn.fetchval(
                        "SELECT id FROM promo_codes WHERE code = $1 AND used_count < usage_limit", promo_code
                    )
                    if not promo_code_id:
                        raise ValueError("Промокод не найден или использован полностью.")

                # Вставляем транзакцию
                transaction_id = await conn.fetchval(
                    """
                    INSERT INTO transactions (user_telegram_id, quantity, amount, promo_code_id, status)
                    VALUES ($1, $2, $3, $4, 'on_check')
                    RETURNING id
                    """,
                    user_telegram_id, quantity, amount, promo_code_id
                )

                # Обновляем счетчик использований промокода
                if promo_code_id:
                    await conn.execute(
                        "UPDATE promo_codes SET used_count = used_count + 1 WHERE id = $1", promo_code_id
                    )

                return transaction_id

    async def add_purchase(self, telegram_id: int, qty: int, amount: int, repost: bool,
                           moderator_id: int | None = None):
        """
        Совместимый со старой версией метод для добавления покупки.
        Создает транзакцию со статусом 'on_check'.
        Параметры `repost` и `moderator_id` игнорируются.
        """
        # Просто вызываем новый, более точный метод. Промокод здесь не передается.
        await self.create_transaction(user_telegram_id=telegram_id, quantity=qty, amount=float(amount))

    async def get_transaction(self, transaction_id: int):
        """
        Получает информацию о транзакции по ее ID.
        Возвращает: запись (record) или None, если не найдена.
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT user_telegram_id, status FROM transactions WHERE id = $1;
            """
            return await conn.fetchrow(query, transaction_id)

    async def get_transaction_amount(self, transaction_id: int) -> int:
        """Возвращает сумму для транзакции с учетом промокода, если есть"""
        row = await self.pool.fetchrow(
            "SELECT amount FROM transactions WHERE id=$1",
            transaction_id
        )
        if row:
            return row["amount"]
        return 0

    async def approve_transaction(self, transaction_id: int) -> list[str]:
        """
        Подтверждает транзакцию и создает билеты для пользователя.
        Меняет статус транзакции на 'approved'.
        Возвращает список сгенерированных токенов билетов.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Получаем данные транзакции
                tx_data = await conn.fetchrow(
                    "SELECT user_telegram_id, quantity, status FROM transactions WHERE id = $1",
                    transaction_id
                )
                if not tx_data:
                    raise ValueError("Транзакция не найдена.")
                if tx_data['status'] != 'on_check':
                    raise ValueError(f"Транзакция уже обработана (статус: {tx_data['status']}).")

                # Обновляем статус транзакции
                await conn.execute(
                    "UPDATE transactions SET status = 'approved' WHERE id = $1",
                    transaction_id
                )

                # генерируем и вставляем билеты
                owner_id = tx_data['user_telegram_id']
                quantity = tx_data['quantity']
                new_tickets = []
                for _ in range(quantity):
                    token = token = f"{owner_id:x}aa{int(time.time()):x}{uuid.uuid4().hex[:6]}"
                    await conn.execute(
                        """
                        INSERT INTO tickets (token, owner_telegram_id, transaction_id, status)
                        VALUES ($1, $2, $3, 'active')
                        """,
                        token, owner_id, transaction_id
                    )
                    new_tickets.append(token)

                return new_tickets

    async def reject_transaction(self, transaction_id: int):
        """Отклоняет транзакцию, меняя ее статус на 'rejected'."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE transactions SET status = 'rejected' WHERE id = $1 AND status = 'on_check'",
                transaction_id
            )
            if result == 'UPDATE 0':
                raise ValueError("Транзакция не найдена или уже обработана.")

    # --- Методы для работы с билетами ---

    async def get_user_tickets(self, telegram_id: int) -> int:
        """
        Возвращает количество АКТИВНЫХ билетов у пользователя.
        Сохранено старое название для совместимости.
        """
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM tickets WHERE owner_telegram_id = $1 AND status = 'active'",
                telegram_id
            )
            return count if count is not None else 0

    async def get_user_ticket_list(self, telegram_id: int) -> list:
        """Возвращает список всех активных билетов (токенов) пользователя."""
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT token FROM tickets WHERE owner_telegram_id = $1 AND status = 'active'",
                telegram_id
            )
            return [record['token'] for record in records]

    async def use_ticket(self, token: str) -> bool:
        """
        Помечает билет как 'used'.
        Возвращает True в случае успеха, False если билет не найден или уже использован.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE tickets SET status = 'used' WHERE token = $1 AND status = 'active'",
                token
            )
            return result == 'UPDATE 1'

    async def remove_tickets(self, telegram_id: int, count: int):
        """
        Помечает указанное количество билетов пользователя как 'used'.
        Сохранено старое название для совместимости.
        Билеты выбираются по принципу FIFO (самые старые).
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Находим самые старые активные билеты пользователя для списания
                tickets_to_use = await conn.fetch(
                    """
                    SELECT id FROM tickets
                    WHERE owner_telegram_id = $1 AND status = 'active'
                    ORDER BY created_at ASC
                    LIMIT $2
                    """,
                    telegram_id, count
                )

                if len(tickets_to_use) < count:
                    print(f"Внимание: у пользователя {telegram_id} недостаточно билетов для списания.")

                if not tickets_to_use:
                    return

                ticket_ids = [record['id'] for record in tickets_to_use]
                await conn.execute(
                    "UPDATE tickets SET status = 'used' WHERE id = ANY($1::int[])",
                    ticket_ids
                )

    async def count_tickets(self) -> int:
        """
        Возвращает общее количество АКТИВНЫХ билетов в системе.
        Сохранено старое название для совместимости.
        """
        async with self.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM tickets WHERE status = 'active'")
            return count if count is not None else 0

    async def get_ticket_info_by_token(self, token: str) -> asyncpg.Record | None:
        """
        Возвращает полную информацию о билете и его владельце по токену.
        Использует LEFT JOIN на случай, если пользователь был удален, но билет остался.
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT
                    t.id,
                    t.token,
                    t.status,
                    t.owner_telegram_id,
                    u.username,
                    u.name
                FROM tickets t
                LEFT JOIN users u ON t.owner_telegram_id = u.telegram_id
                WHERE t.token = $1;
            """
            return await conn.fetchrow(query, token)

    async def get_ticket_stats(self) -> asyncpg.Record:
        """
        Возвращает статистику по билетам, сгруппированную по статусам.
        Возвращает запись с полями active_tickets и used_tickets.
        """
        async with self.pool.acquire() as conn:
            # Этот запрос вернет одну строку с двумя колонками: active_tickets и used_tickets
            query = """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'active') AS active_tickets,
                    COUNT(*) FILTER (WHERE status = 'used') AS used_tickets
                FROM tickets;
            """
            # fetchrow вернет одну запись (asyncpg.Record) или None, если таблица пуста
            stats = await conn.fetchrow(query)
            return stats

    async def get_attended_users_ids(self) -> list[int]:
        """
        Возвращает список уникальных telegram_id тех пользователей,
        у которых есть хотя бы один билет со статусом 'used'.
        """
        async with self.pool.acquire() as conn:
            query = "SELECT DISTINCT owner_telegram_id FROM tickets WHERE status = 'used';"
            records = await conn.fetch(query)
            return [record['owner_telegram_id'] for record in records]

    # --- Методы для работы с промокодами ---

    async def create_promo_code(self, code: str, admin_telegram_id: int, value: float = 750,
                                usage_limit: int = 1) -> bool:
        """Создает новый промокод с номиналом (цена билета со скидкой) и лимитом использований."""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    "INSERT INTO promo_codes (code, admin_telegram_id, value, usage_limit, used_count) "
                    "VALUES ($1, $2, $3, $4, 0)",
                    code, admin_telegram_id, value, usage_limit
                )
                return True
            except asyncpg.UniqueViolationError:
                return False  # Такой код уже существует

    async def get_promo_code(self, code: str):
        """Возвращает данные о промокоде."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM promo_codes WHERE code = $1", code)

    async def get_promo_value(self, code: str) -> float | None:
        """Возвращает номинал (value) для указанного промокода."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM promo_codes WHERE code = $1", code)
            return row["value"] if row else None

    # --- Вспомогательные методы ---

    async def get_total_sales_amount(self) -> float:
        """
        Возвращает общую сумму продаж по подтвержденным транзакциям.
        """
        async with self.pool.acquire() as conn:
            amount = await conn.fetchval(
                "SELECT SUM(amount) FROM transactions WHERE status = 'approved'"
            )
            return amount if amount is not None else 0.0

    async def export_users_csv(self) -> str:
        """
        Экспортирует данные по всем пользователям и количеству их активных билетов в CSV файл.
        """
        filename = f"stats_exports/users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs("stats_exports", exist_ok=True)

        async with self.pool.acquire() as conn:
            data = await conn.fetch("""
                SELECT
                    u.id,
                    u.telegram_id,
                    u.username,
                    u.name, 
                    u.created_at,
                    COUNT(t.id) FILTER (WHERE t.status = 'active') AS active_tickets_count
                FROM users u
                LEFT JOIN tickets t ON u.telegram_id = t.owner_telegram_id
                GROUP BY u.id, u.telegram_id, u.username, u.name, u.created_at
                ORDER BY u.id;
            """)

        # Добавляем 'name' в заголовок
        headers = ["id", "telegram_id", "username", "name", "registration_date", "active_tickets_count"]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)  # заголовки
            for row in data:
                writer.writerow([
                    row['id'],
                    row['telegram_id'],
                    row['username'] if row['username'] else '',
                    row['name'] if row['name'] else '',
                    row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row['created_at'] else '',
                    row['active_tickets_count']
                ])

        return filename

    async def export_transactions_csv(self) -> str:
        """
        Экспортирует данные по всем транзакциям в CSV-файл.
        """
        filename = f"stats_exports/transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs("stats_exports", exist_ok=True)

        async with self.pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT
                    id,
                    user_telegram_id,
                    quantity,
                    amount,
                    status,
                    created_at
                FROM transactions
                ORDER BY created_at DESC;
            """)

        headers = ["id", "user_telegram_id", "quantity", "amount", "status", "created_at"]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in records:
                writer.writerow([
                    row["id"],
                    row["user_telegram_id"],
                    row["quantity"],
                    float(row["amount"]),  # чтобы всегда было число
                    row["status"],
                    row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row["created_at"] else ""
                ])

        return filename

    async def export_tickets_csv(self) -> str:
        """
        Экспортирует данные по всем билетам в CSV-файл.
        """
        filename = f"stats_exports/tickets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs("stats_exports", exist_ok=True)

        async with self.pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT
                    id,
                    token,
                    owner_telegram_id,
                    transaction_id,
                    status,
                    created_at
                FROM tickets
                ORDER BY created_at DESC;
            """)

        headers = ["id", "token", "owner_telegram_id", "transaction_id", "status", "created_at"]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in records:
                writer.writerow([
                    row["id"],
                    row["token"],
                    row["owner_telegram_id"],
                    row["transaction_id"],
                    row["status"],
                    row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row["created_at"] else ""
                ])

        return filename

    async def get_ticket_owners(self) -> list[str]:
        """
        Возвращает список пользователей, у которых есть билеты,
        в формате @username (или telegram_id, если username пустой).
        """
        async with self.pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT DISTINCT ON (u.telegram_id) u.telegram_id, u.username
                FROM tickets t
                JOIN users u ON u.telegram_id = t.owner_telegram_id
                ORDER BY u.telegram_id;
            """)
            result = []
            for r in records:
                if r["username"]:
                    result.append(f"@{r['username']}")
                else:
                    result.append(str(r["telegram_id"]))
            return result
