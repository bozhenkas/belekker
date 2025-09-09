-- Этот скрипт предназначен для инициализации схемы в УЖЕ СУЩЕСТВУЮЩЕЙ базе данных.
-- Создание самой БД теперь обрабатывается через docker-compose.yml.

-- Включаем расширение для поиска по части слова
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Создаем таблицы, только если они еще не существуют

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- === НОВАЯ КОМАНДА МИГРАЦИИ ===
-- Добавляем столбец 'name', только если он отсутствует
ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_username_trgm ON users USING GIN (username gin_trgm_ops);

CREATE TABLE IF NOT EXISTS promo_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    admin_telegram_id BIGINT REFERENCES users(telegram_id) ON DELETE SET NULL,
    value NUMERIC(10,2) NOT NULL DEFAULT 750,
    usage_limit INTEGER NOT NULL DEFAULT 1,
    used_count INTEGER NOT NULL DEFAULT 0,
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

-- Создаем или заменяем функцию и триггер
CREATE OR REPLACE FUNCTION update_promo_used() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.promo_code_id IS NOT NULL THEN
        UPDATE promo_codes
        SET used_count = used_count + 1
        WHERE id = NEW.promo_code_id
          AND used_count < usage_limit;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Промокод уже использован максимальное количество раз или не существует';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trig_update_promo ON transactions;
CREATE TRIGGER trig_update_promo BEFORE INSERT ON transactions
FOR EACH ROW EXECUTE PROCEDURE update_promo_used();