import os
from dotenv import load_dotenv

load_dotenv()

# конфиг, чтобы потом не идти в .env
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "tickets_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASS", "postgres")
CACHE_DIR = os.getenv("CACHE_DIR", "cache")
