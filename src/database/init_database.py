import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from config import *

# подключение к системной базе postgres
conn = psycopg2.connect(dbname="postgres", user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

# проверяем, существует ли база
cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
exists = cur.fetchone()

if exists:
    print(f"база {DB_NAME} уже существует, удаляю...")
    # завершаем активные подключения
    cur.execute(f"""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '{DB_NAME}' AND pid <> pg_backend_pid();
    """)
    # удаляем БД
    cur.execute(f"DROP DATABASE {DB_NAME}")

# создаём заново
cur.execute(f"CREATE DATABASE {DB_NAME}")
print(f"база {DB_NAME} создана заново")

cur.close()
conn.close()

# подключение к новой базе
conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
cur = conn.cursor()

# включаем расширение pg_trgm
cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

# создаём таблицы
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_username_trgm ON users USING GIN (username gin_trgm_ops);

CREATE TABLE IF NOT EXISTS promo_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    admin_telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE SET NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_promo_codes_admin ON promo_codes(admin_telegram_id);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    amount DECIMAL(10, 2) NOT NULL CHECK (amount >= 0),
    promo_code_id INTEGER REFERENCES promo_codes(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'on_check' CHECK (status IN ('on_check', 'approved', 'rejected')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_telegram_id);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_promo ON transactions(promo_code_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_telegram_id, created_at);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    owner_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'used', 'expired')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tickets_owner ON tickets(owner_telegram_id);
CREATE INDEX IF NOT EXISTS idx_tickets_transaction ON tickets(transaction_id);
""")

# триггер для обновления is_used в promo_codes
cur.execute("""
CREATE OR REPLACE FUNCTION update_promo_used() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.promo_code_id IS NOT NULL THEN
        UPDATE promo_codes SET is_used = TRUE WHERE id = NEW.promo_code_id AND is_used = FALSE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Промокод уже использован или не существует';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trig_update_promo ON transactions;
CREATE TRIGGER trig_update_promo BEFORE INSERT ON transactions
FOR EACH ROW EXECUTE PROCEDURE update_promo_used();
""")

conn.commit()
cur.close()
conn.close()

print("база данных полностью пересоздана и инициализирована успешно.")
# Подключение для создания БД
conn = psycopg2.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

# Создание БД если не существует
cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_NAME}'")
exists = cur.fetchone()
if not exists:
    cur.execute(f"CREATE DATABASE {DB_NAME}")
cur.close()
conn.close()

# Подключение к новой БД
conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
cur = conn.cursor()

# Включение расширений (только pg_trgm)
cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

# Создание таблиц
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_username_trgm ON users USING GIN (username gin_trgm_ops);

CREATE TABLE IF NOT EXISTS promo_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    admin_telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE SET NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_promo_codes_admin ON promo_codes(admin_telegram_id);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    amount DECIMAL(10, 2) NOT NULL CHECK (amount >= 0),
    promo_code_id INTEGER REFERENCES promo_codes(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'on_check' CHECK (status IN ('on_check', 'approved', 'rejected')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_telegram_id);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_promo ON transactions(promo_code_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_telegram_id, created_at);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    owner_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'used', 'expired')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tickets_owner ON tickets(owner_telegram_id);
CREATE INDEX IF NOT EXISTS idx_tickets_transaction ON tickets(transaction_id);
""")

# Триггер для обновления is_used в promo_codes (пример, optional)
cur.execute("""
CREATE OR REPLACE FUNCTION update_promo_used() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.promo_code_id IS NOT NULL THEN
        UPDATE promo_codes SET is_used = TRUE WHERE id = NEW.promo_code_id AND is_used = FALSE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Промокод уже использован или не существует';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trig_update_promo ON transactions;
CREATE TRIGGER trig_update_promo BEFORE INSERT ON transactions
FOR EACH ROW EXECUTE PROCEDURE update_promo_used();
""")

conn.commit()
cur.close()
conn.close()

print("База данных инициализирована успешно.")
