import asyncio
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

load_dotenv()
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "74376339"))
DB_PATH = os.environ.get("DB_PATH", "bot.db")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
RATE = {}


def db(sql, args=(), many=False, fetch=False, one=False):
    with sqlite3.connect(DB_PATH) as c:
        if many:
            c.executemany(sql, args)
        else:
            cur = c.execute(sql, args)
        if fetch:
            return cur.fetchone() if one else cur.fetchall()
        c.commit()
        return cur.lastrowid


def init_db():
    db("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, name TEXT, joined TEXT, banned INTEGER DEFAULT 0)""")
    db("""CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, done INTEGER DEFAULT 0, created TEXT)""")
    db("""CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, created TEXT)""")
    db("""CREATE TABLE IF NOT EXISTS habits(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, created TEXT)""")
    db("""CREATE TABLE IF NOT EXISTS habit_logs(habit_id INTEGER, day TEXT, UNIQUE(habit_id, day))""")
    db("""CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, due TEXT, sent INTEGER DEFAULT 0)""")
    db("""CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, status TEXT DEFAULT 'open', created TEXT)""")
    db("""CREATE TABLE IF NOT EXISTS polls(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, question TEXT, options TEXT, created TEXT)""")
    db("""CREATE TABLE IF NOT EXISTS votes(poll_id INTEGER, user_id INTEGER, option_no INTEGER, UNIQUE(poll_id,user_id))""")


def now():
    return datetime.now(timezone.utc).isoformat()


def register(update):
    u = update.effective_user
    db("INSERT OR IGNORE INTO users(id,username,name,joined) VALUES(?,?,?,?)", (u.id, u.username or "", u.full_name, now()))
    db("UPDATE users SET username=?,name=? WHERE id=?", (u.username or "", u.full_name, u.id))


def allowed(fn):
    @wraps(fn)
    async def wrapper(update, context, *args, **kwargs):
        register(update)
        uid = update.effective_user.id
        banned = db("SELECT banned FROM users WHERE id=?", (uid,), True, True, True)
        if banned and banned[0]:
            return
        current = time.monotonic()
        if current - RATE.get(uid, 0) < 0.7:
            return
        RATE[uid] = current
        return await fn(update, context, *args, **kwargs)
    return wrapper


def argtext(context):
    return " ".join(context.args).strip()


@allowed
async def start(update, context):
    await update.message.reply_text("Namaste! Main aapka advanced assistant bot hoon. /help likhkar commands dekhiye.\nHello! Type /help for commands.")


@allowed
async def help_cmd(update, context):
    await update.message.reply_text("""Commands / Commands:
/start, /help, /profile
/addtask <text>, /tasks, /done <id>
/addnote <text>, /notes, /deletenote <id>
/addhabit <name>, /habits, /loghabit <id>, /habitstats <id>
/remind <minutes> <text>, /reminders
/poll <question> | <option1> | <option2>..., /vote <poll_id> <number>, /pollresults <id>
/support <problem>, /mytickets
/stats (admin), /users (admin), /broadcast <message> (admin)
/ban <user_id> and /unban <user_id> (admin)

Roman Hindi ya English dono me likh sakte hain. External API aur payment abhi enabled nahi hain.""")


@allowed
async def profile(update, context):
    u = update.effective_user
    row = db("SELECT joined FROM users WHERE id=?", (u.id,), True, True, True)
    await update.message.reply_text(f"ID: {u.id}\nUsername: @{u.username or 'N/A'}\nName: {u.full_name}\nJoined: {row[0] if row else 'N/A'}")


@allowed
async def addtask(update, context):
    text = argtext(context)
    if not text:
        return await update.message.reply_text("Usage: /addtask <task>")
    task_id = db("INSERT INTO tasks(user_id,text,created) VALUES(?,?,?)", (update.effective_user.id, text, now()))
    await update.message.reply_text(f"Task added / task save ho gaya. ID: {task_id}")


@allowed
async def tasks(update, context):
    rows = db("SELECT id,text FROM tasks WHERE user_id=? AND done=0 ORDER BY id DESC", (update.effective_user.id,), True, True)
    await update.message.reply_text("\n".join(f"{i}: {t}" for i, t in rows) or "No pending tasks.")


@allowed
async def done(update, context):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Usage: /done <task_id>")
    changed = db("UPDATE tasks SET done=1 WHERE id=? AND user_id=?", (int(context.args[0]), update.effective_user.id))
    await update.message.reply_text("Task complete." if changed else "Task nahi mila.")


@allowed
async def addnote(update, context):
    text = argtext(context)
    if not text:
        return await update.message.reply_text("Usage: /addnote <note>")
    i = db("INSERT INTO notes(user_id,text,created) VALUES(?,?,?)", (update.effective_user.id, text, now()))
    await update.message.reply_text(f"Note saved. ID: {i}")


@allowed
async def notes(update, context):
    rows = db("SELECT id,text FROM notes WHERE user_id=? ORDER BY id DESC LIMIT 30", (update.effective_user.id,), True, True)
    await update.message.reply_text("\n".join(f"{i}: {t}" for i, t in rows) or "No notes yet.")


@allowed
async def deletenote(update, context):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Usage: /deletenote <note_id>")
    db("DELETE FROM notes WHERE id=? AND user_id=?", (int(context.args[0]), update.effective_user.id))
    await update.message.reply_text("Note deleted / note delete ho gaya.")


@allowed
async def addhabit(update, context):
    name = argtext(context)
    if not name:
        return await update.message.reply_text("Usage: /addhabit <habit>")
    i = db("INSERT INTO habits(user_id,name,created) VALUES(?,?,?)", (update.effective_user.id, name, now()))
    await update.message.reply_text(f"Habit added. ID: {i}")


@allowed
async def habits(update, context):
    rows = db("SELECT id,name FROM habits WHERE user_id=?", (update.effective_user.id,), True, True)
    await update.message.reply_text("\n".join(f"{i}: {n}" for i, n in rows) or "No habits yet.")


@allowed
async def loghabit(update, context):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Usage: /loghabit <habit_id>")
    hid = int(context.args[0])
    owns = db("SELECT id FROM habits WHERE id=? AND user_id=?", (hid, update.effective_user.id), True, True, True)
    if not owns:
        return await update.message.reply_text("Habit nahi mila.")
    try:
        db("INSERT INTO habit_logs(habit_id,day) VALUES(?,?)", (hid, datetime.now(timezone.utc).date().isoformat()))
        await update.message.reply_text("Aaj ka habit logged! Great job 🎉")
    except sqlite3.IntegrityError:
        await update.message.reply_text("Aaj pehle hi log ho chuka hai.")


@allowed
async def habitstats(update, context):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Usage: /habitstats <habit_id>")
    count = db("SELECT COUNT(*) FROM habit_logs WHERE habit_id=?", (int(context.args[0]),), True, True, True)[0]
    await update.message.reply_text(f"Habit completions: {count}")


@allowed
async def remind(update, context):
    if len(context.args) < 2 or not context.args[0].isdigit():
        return await update.message.reply_text("Usage: /remind <minutes> <message>")
    minutes, text = int(context.args[0]), " ".join(context.args[1:])
    due = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    i = db("INSERT INTO reminders(user_id,text,due) VALUES(?,?,?)", (update.effective_user.id, text, due.isoformat()))
    await update.message.reply_text(f"Reminder set for {minutes} minute(s). ID: {i}")


@allowed
async def reminders(update, context):
    rows = db("SELECT id,text,due FROM reminders WHERE user_id=? AND sent=0 ORDER BY due", (update.effective_user.id,), True, True)
    await update.message.reply_text("\n".join(f"{i}: {t} ({d})" for i, t, d in rows) or "No reminders.")


@allowed
async def create_poll(update, context):
    parts = [p.strip() for p in argtext(context).split("|") if p.strip()]
    if len(parts) < 3:
        return await update.message.reply_text("Usage: /poll question | option 1 | option 2")
    i = db("INSERT INTO polls(user_id,question,options,created) VALUES(?,?,?,?)", (update.effective_user.id, parts[0], "|".join(parts[1:]), now()))
    await update.message.reply_text(f"Poll {i}: {parts[0]}\n" + "\n".join(f"{n}. {x}" for n, x in enumerate(parts[1:], 1)) + f"\nVote: /vote {i} <number>")


@allowed
async def vote(update, context):
    if len(context.args) != 2 or not all(x.isdigit() for x in context.args):
        return await update.message.reply_text("Usage: /vote <poll_id> <option_number>")
    pid, opt = map(int, context.args)
    row = db("SELECT options FROM polls WHERE id=?", (pid,), True, True, True)
    if not row or not 1 <= opt <= len(row[0].split("|")):
        return await update.message.reply_text("Poll ya option invalid hai.")
    try:
        db("INSERT INTO votes(poll_id,user_id,option_no) VALUES(?,?,?)", (pid, update.effective_user.id, opt))
        await update.message.reply_text("Vote recorded / vote save ho gaya.")
    except sqlite3.IntegrityError:
        await update.message.reply_text("Aap is poll me pehle vote kar chuke hain.")


@allowed
async def pollresults(update, context):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Usage: /pollresults <poll_id>")
    pid = int(context.args[0]); row = db("SELECT question,options FROM polls WHERE id=?", (pid,), True, True, True)
    if not row: return await update.message.reply_text("Poll nahi mila.")
    counts = dict(db("SELECT option_no,COUNT(*) FROM votes WHERE poll_id=? GROUP BY option_no", (pid,), True, True))
    opts = row[1].split("|")
    await update.message.reply_text(row[0] + "\n" + "\n".join(f"{i}. {x}: {counts.get(i,0)}" for i, x in enumerate(opts, 1)))


@allowed
async def support(update, context):
    text = argtext(context)
    if not text: return await update.message.reply_text("Usage: /support <problem>")
    i = db("INSERT INTO tickets(user_id,text,created) VALUES(?,?,?)", (update.effective_user.id, text, now()))
    await update.message.reply_text(f"Support ticket created: #{i}")


@allowed
async def mytickets(update, context):
    rows = db("SELECT id,text,status FROM tickets WHERE user_id=? ORDER BY id DESC", (update.effective_user.id,), True, True)
    await update.message.reply_text("\n".join(f"#{i} [{s}] {t}" for i,t,s in rows) or "No tickets.")


def admin_only(fn):
    @wraps(fn)
    async def wrapper(update, context, *args, **kwargs):
        if update.effective_user.id != ADMIN_ID:
            return await update.message.reply_text("Ye admin-only command hai.")
        return await fn(update, context, *args, **kwargs)
    return wrapper


@admin_only
async def stats(update, context):
    users = db("SELECT COUNT(*) FROM users", fetch=True, one=True)[0]
    tasks = db("SELECT COUNT(*) FROM tasks WHERE done=0", fetch=True, one=True)[0]
    tickets = db("SELECT COUNT(*) FROM tickets WHERE status='open'", fetch=True, one=True)[0]
    await update.message.reply_text(f"Users: {users}\nPending tasks: {tasks}\nOpen tickets: {tickets}")


@admin_only
async def users_cmd(update, context):
    rows = db("SELECT id,username,name,banned FROM users ORDER BY joined DESC LIMIT 50", fetch=True)
    await update.message.reply_text("\n".join(f"{i} @{u or '-'} {n} {'BANNED' if b else ''}" for i,u,n,b in rows) or "No users.")


@admin_only
async def broadcast(update, context):
    text = argtext(context)
    if not text: return await update.message.reply_text("Usage: /broadcast <message>")
    rows = db("SELECT id FROM users WHERE banned=0", fetch=True)
    sent = 0
    for (uid,) in rows:
        try:
            await context.bot.send_message(uid, text); sent += 1
            await asyncio.sleep(0.05)
        except Exception: log.exception("broadcast failed for %s", uid)
    await update.message.reply_text(f"Broadcast sent: {sent}")


@admin_only
async def ban(update, context):
    if context.args and context.args[0].isdigit():
        db("UPDATE users SET banned=1 WHERE id=?", (int(context.args[0]),))
        await update.message.reply_text("User banned.")


@admin_only
async def unban(update, context):
    if context.args and context.args[0].isdigit():
        db("UPDATE users SET banned=0 WHERE id=?", (int(context.args[0]),))
        await update.message.reply_text("User unbanned.")


async def reminder_job(context):
    rows = db("SELECT id,user_id,text FROM reminders WHERE sent=0 AND due<=?", (now(),), True, True)
    for rid, uid, text in rows:
        try:
            await context.bot.send_message(uid, f"⏰ Reminder: {text}")
            db("UPDATE reminders SET sent=1 WHERE id=?", (rid,))
        except Exception as e:
            log.warning("reminder failed: %s", e)


async def text_handler(update, context):
    register(update)
    await update.message.reply_text("Message received. Commands dekhne ke liye /help likhiye.")


def main():
    if not TOKEN: raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable missing")
    init_db()
    app = Application.builder().token(TOKEN).build()
    handlers = {
        "start": start, "help": help_cmd, "profile": profile, "addtask": addtask, "tasks": tasks, "done": done,
        "addnote": addnote, "notes": notes, "deletenote": deletenote, "addhabit": addhabit, "habits": habits,
        "loghabit": loghabit, "habitstats": habitstats, "remind": remind, "reminders": reminders, "poll": create_poll,
        "vote": vote, "pollresults": pollresults, "support": support, "mytickets": mytickets, "stats": stats,
        "users": users_cmd, "broadcast": broadcast, "ban": ban, "unban": unban,
    }
    for command, handler in handlers.items(): app.add_handler(CommandHandler(command, handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.job_queue.run_repeating(reminder_job, interval=30, first=5)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
