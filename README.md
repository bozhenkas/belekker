# belekker Telegram Bot

**belekker** is an asynchronous Telegram bot built with Python, aiogram (3.13.1), and PostgreSQL for managing ticket
sales, promo codes, and user interactions. It supports user ticket purchases, admin moderation, and QR-code ticket
generation. The project is containerized using Docker for easy deployment.

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd belekker
```

### 2. Configure `.env`

Copy the example `.env` file and edit it:

```bash
cp .env.example .env
nano .env
```

Fill in `TELEGRAM_TOKEN`, `CHAT_ID`, `CHANNEL_ID`, and `ADMINS` with your values.

### 3. Run the Bot

```bash
docker-compose up --build
```

This builds and starts the bot and PostgreSQL containers. The database is automatically initialized.

## Project Structure

```
belekker/
├── assets/                    # Static files (e.g., afisha.jpg)
├── cache/                     # Temporary files (logs, exports)
├── src/                       # Source code
│   ├── bot/                   # Bot logic
│   │   ├── handlers/          # Command and callback handlers
│   │   ├── keyboards/         # Inline and reply keyboards
│   │   ├── middlewares/       # Custom middleware (e.g., AddUserMiddleware)
│   │   ├── states/            # FSM states for purchase flow
│   │   ├── tickets/           # Ticket generation and storage
│   │   └── utils/             # Utilities (e.g., message parsing)
│   └── database/              # Database connection and queries
├── Dockerfile                 # Docker image for bot
├── docker-compose.yml         # Docker Compose for bot + PostgreSQL
├── init.sql                   # Database schema initialization
├── requirements.txt           # Python dependencies
└── README.md                  # Project documentation
```

## Features

- **User Features**:
    - Buy tickets with or without promo codes.
    - View event information (`/start`, "информация").
    - Submit payment proofs for admin review.
    - Receive QR-code-based tickets after approval.
- **Admin Features**:
    - Generate promo codes (`/promo`).
    - Approve/reject transactions (`approve:`, `reject:`).
    - Send event posters to a channel (`/afisha`).
    - View statistics (`/stats_info`, `/stats_transactions`, `/stats_tickets`).
- **Technical**:
    - Built with aiogram 3.13.1 for async Telegram API interactions.
    - PostgreSQL with asyncpg for data storage (users, transactions, tickets, promo codes).
    - FSM (Finite State Machine) for handling purchase flows.
    - QR-code ticket generation using PIL and qrcode.
    - Centralized configuration with pydantic.
    - Dockerized with docker-compose for easy deployment.


## Prerequisites

- Python 3.10+
- Docker and Docker Compose (for containerized deployment)
- PostgreSQL 16 (if running locally without Docker)
- Telegram Bot Token (obtained from @BotFather)


## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes (`git commit -m "Add feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.

## License

This project is licensed under the MIT License.

