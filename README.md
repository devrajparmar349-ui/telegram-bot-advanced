# Advanced Telegram Bot

This bot includes local, no-external-API features: profiles, bilingual-friendly replies, tasks, reminders, notes, habits, polls, support tickets, SQLite storage, rate limiting, logging, admin statistics, broadcast, ban/unban, and document-ready project structure.

## Local setup

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and put your BotFather token in `TELEGRAM_BOT_TOKEN`. Never commit `.env` or share the token.

```bash
python bot.py
```

## Render

Create a **Background Worker**, choose this repository, use:

- Build command: `pip install -r requirements.txt`
- Start command: `python bot.py`
- Environment variable: `TELEGRAM_BOT_TOKEN` = your new token
- Environment variable: `ADMIN_ID` = `74376339`

SQLite is suitable for testing. Render restarts can lose local disk data, so use a managed PostgreSQL database before production if permanent data matters. A paid always-on worker may be required for continuous uptime.

## Main commands

`/start`, `/help`, `/profile`, `/addtask`, `/tasks`, `/done`, `/addnote`, `/notes`, `/deletenote`, `/addhabit`, `/habits`, `/loghabit`, `/habitstats`, `/remind`, `/reminders`, `/poll`, `/vote`, `/pollresults`, `/support`, `/mytickets`.

Admin: `/stats`, `/users`, `/broadcast`, `/ban`, `/unban`.

This version intentionally does not include external APIs or payments, as requested. Weather, news, GitHub, AI, and payment integrations require separate provider keys and configuration.
