# ai_pa_deepseek_bot.py
import logging, sqlite3, os, asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import openai

# --- CONFIG ---
TELEGRAM_TOKEN = "7512132460:AAETmFjHKwPhghPSFVndNG0mBYTwwUgS_hk"
DEEPSEEK_API_KEY = "sk-e4cad95f1850499882c9c543dd09e0bd"

# DeepSeek setup
openai.api_key = DEEPSEEK_API_KEY
openai.api_base = "https://api.deepseek.com"   # Base URL for DeepSeek API

DB_PATH = "ai_pa.db"

# --- DB utilities ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, goals TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, detail TEXT, ts TEXT)""")
    conn.commit(); conn.close()

def save_goals(user_id:int, goals:str):
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("INSERT OR REPLACE INTO users(user_id, goals) VALUES(?, ?)", (user_id, goals))
    conn.commit(); conn.close()

def get_goals(user_id:int):
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT goals FROM users WHERE user_id=?", (user_id,))
    r = c.fetchone(); conn.close()
    return r[0] if r else None

def add_log(user_id:int, kind:str, detail:str):
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("INSERT INTO logs(user_id, kind, detail, ts) VALUES(?,?,?,?)", 
              (user_id, kind, detail, datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

def get_weekly_summary(user_id:int):
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    c.execute("SELECT kind, COUNT(*) FROM logs WHERE user_id=? AND ts>=? GROUP BY kind", 
              (user_id, week_ago))
    rows = c.fetchall(); conn.close()
    return rows

# --- DeepSeek helper ---
async def ai_reply(prompt, max_tokens=300):
    loop = asyncio.get_event_loop()

    def call():
        resp = openai.Completion.create(
            model="deepseek-chat",   # or "deepseek-coder" depending on what you need
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.7
        )
        return resp

    resp = await loop.run_in_executor(None, call)
    return resp.choices[0].text.strip()

# --- Bot handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"Hi {user.first_name}! I'm your AI PA powered by DeepSeek 🚀\n"
        "Use /setgoal to save goals, /plan for a daily routine, /log to track habits, /progress to see summary, /ask to ask anything.\n"
        "Type /help for commands."
    )
    await update.message.reply_text(text)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/setgoal <text>\n/mygoals\n/plan\n/log <type> <detail>\n/progress\n/ask <question>"
    )

async def setgoal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    goals = " ".join(context.args)
    if not goals:
        await update.message.reply_text("Usage: /setgoal I want to gain 20kg muscle, learn hacking, earn money")
        return
    save_goals(user_id, goals)
    await update.message.reply_text("Saved your goals ✅")

async def mygoals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = get_goals(update.effective_user.id) or "No goals set. Use /setgoal"
    await update.message.reply_text(f"Your goals:\n{g}")

async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    goals = get_goals(user_id) or ""
    prompt = f"Create a concise daily routine (morning, afternoon, night) for these goals: {goals}. Keep it short and actionable."
    reply = await ai_reply(prompt, max_tokens=200)
    await update.message.reply_text(reply)

async def log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /log <type> <detail>")
        return
    kind = context.args[0]
    detail = " ".join(context.args[1:])
    add_log(user_id, kind, detail)
    await update.message.reply_text(f"Logged {kind}: {detail}")

async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_weekly_summary(user_id)
    if not rows:
        await update.message.reply_text("No logs this week.")
        return
    text = "Weekly summary:\n" + "\n".join(f"{k}: {v}" for k,v in rows)
    await update.message.reply_text(text)

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = " ".join(context.args)
    if not q:
        await update.message.reply_text("Usage: /ask <your question>")
        return
    await update.message.reply_text("Thinking... 🤖")
    ans = await ai_reply(q, max_tokens=250)
    await update.message.reply_text(ans)

# --- main ---
def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("setgoal", setgoal))
    app.add_handler(CommandHandler("mygoals", mygoals))
    app.add_handler(CommandHandler("plan", plan))
    app.add_handler(CommandHandler("log", log))
    app.add_handler(CommandHandler("progress", progress))
    app.add_handler(CommandHandler("ask", ask))
    print("Bot started with DeepSeek...")
    app.run_polling()

if __name__ == "__main__":
    main()
