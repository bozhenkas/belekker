# базовый образ
FROM python:3.11-slim

# не буферим вывод, отключаем кэш pip
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# системные зависимости для asyncpg и проверки сети
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# копируем и апгрейдим pip
COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# копируем код
COPY src ./src
COPY init.sql ./init.sql

# пусть питон видит пакеты из src
ENV PYTHONPATH=/app/src

CMD ["python", "-m", "bot.main"]