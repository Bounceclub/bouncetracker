import logging
import json
import os
from datetime import datetime, time
import pytz
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)

# ── CONFIG ──────────────────────────────────────────────────────────────────
TOKEN   = "8658604167:AAFh6AUHBS2fIHjVkxwFAgaSD0dp9PtK_0g"
CHAT_ID = -1003843600567

MEMBERS = ["Lucas", "Emi", "Julián", "Luis", "Ved", "Rod", "Cufa"]

TASKS = {
    "tiktok":    {"emoji": "🎵", "label": "TikTok",            "pts": 3},
    "reel":      {"emoji": "🎞️",  "label": "Reel",              "pts": 3},
    "story":     {"emoji": "📸", "label": "Story",             "pts": 2},
    "whatsapp":  {"emoji": "📲", "label": "Promo en WhatsApp", "pts": 2},
    "playlist":  {"emoji": "🎧", "label": "Playlist",          "pts": 2},
    "comunidad": {"emoji": "💬", "label": "Comunidad",         "pts": 1},
}

MAX_PTS   = sum(t["pts"] for t in TASKS.values())
DATA_FILE = "bounce_data.json"
ART       = pytz.timezone("America/Argentina/Buenos_Aires")

logging.basicConfig(level=logging.INFO)

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"today": today_key(), "done": {}, "total": {}, "users": {}}

def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def today_key():
    return datetime.now(ART).strftime("%Y-%m-%d")

def check_day(data):
    if data.get("today") != today_key():
        data["today"] = today_key()
        data["done"]  = {}
        save(data)
    return data

def find_member(name: str):
    n = name.strip().lower()
    for m in MEMBERS:
        if m.lower() == n or m.lower().startswith(n):
            return m
    return None

def bar(done, total, width=8):
    filled = round((done / total) * width) if total else 0
    return "█" * filled + "░" * (width - filled)

def ranking_text(data):
    medals   = ["🥇","🥈","🥉"] + ["  "] * 10
    sorted_m = sorted(
        MEMBERS,
        key=lambda m: sum(TASKS[t]["pts"] for t in data["done"].get(m, [])),
        reverse=True
    )
    lines = []
    for i, m in enumerate(sorted_m):
        dp = sum(TASKS[t]["pts"] for t in data["done"].get(m, []))
        tp = data["total"].get(m, 0)
        lines.append(f"{medals[i]} {m:<8} {bar(dp, MAX_PTS)} {dp}/{MAX_PTS}  (total: {tp})")
    return "\n".join(lines)

def resolve_member(update, ctx, data):
    if ctx.args:
        return find_member(" ".join(ctx.args))
    uid = str(update.effective_user.id)
    return data.get("users", {}).get(uid)

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cmds = "\n".join(f"  /{k}  {v['emoji']} {v['label']} (+{v['pts']}pts)" for k, v in TASKS.items())
    await update.message.reply_text(
        "🟢 *BOUNCE Tracker activo*\n\n"
        "Comandos de tarea:\n" + cmds + "\n\n"
        "Usá `/tiktok` si ya te registraste, o `/tiktok Lucas` si no.\n\n"
        "Otros:\n"
        "  /registrar NombreCompleto\n"
        "  /ranking\n"
        "  /miperfil",
        parse_mode="Markdown"
    )

async def cmd_registrar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = check_day(load())
    if not ctx.args:
        await update.message.reply_text("Uso: `/registrar TuNombre`", parse_mode="Markdown")
        return
    member = find_member(" ".join(ctx.args))
    if not member:
        await update.message.reply_text(
            f"❌ Nombre no encontrado.\nMiembros: {', '.join(MEMBERS)}", parse_mode="Markdown"
        )
        return
    if "users" not in data:
        data["users"] = {}
    data["users"][str(update.effective_user.id)] = member
    save(data)
    await update.message.reply_text(f"✅ Registrado como *{member}*.", parse_mode="Markdown")

async def cmd_ranking(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = check_day(load())
    await update.message.reply_text(
        f"🏆 *BOUNCE — Ranking hoy* `{today_key()}`\n\n`{ranking_text(data)}`",
        parse_mode="Markdown"
    )

async def cmd_miperfil(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data   = check_day(load())
    member = resolve_member(update, ctx, data)
    if not member:
        await update.message.reply_text("Registrate con `/registrar TuNombre`.", parse_mode="Markdown")
        return
    done_today = data["done"].get(member, [])
    lines = [f"{'✅' if tid in done_today else '⬜'} {t['emoji']} {t['label']} (+{t['pts']}pts)" for tid, t in TASKS.items()]
    dp = sum(TASKS[t]["pts"] for t in done_today)
    tp = data["total"].get(member, 0)
    await update.message.reply_text(
        f"👤 *{member}* — hoy\n\n" + "\n".join(lines) +
        f"\n\n{bar(dp, MAX_PTS)} {dp}/{MAX_PTS} pts hoy\nTotal: {tp} pts",
        parse_mode="Markdown"
    )

def make_task_handler(task_id: str):
    async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        data   = check_day(load())
        member = resolve_member(update, ctx, data)
        if not member:
            await update.message.reply_text(
                f"¿Quién sos? Usá `/registrar TuNombre` o `/{task_id} TuNombre`.",
                parse_mode="Markdown"
            )
            return
        task       = TASKS[task_id]
        done_today = data["done"].setdefault(member, [])
        if task_id in done_today:
            await update.message.reply_text(
                f"⚠️ *{member}* ya registró {task['emoji']} *{task['label']}* hoy.",
                parse_mode="Markdown"
            )
            return
        done_today.append(task_id)
        data["total"][member] = data["total"].get(member, 0) + task["pts"]
        save(data)
        dp = sum(TASKS[t]["pts"] for t in done_today)
        tp = data["total"][member]
        await update.message.reply_text(
            f"{task['emoji']} *{member}* sumó *+{task['pts']} pts* — {task['label']}!\n"
            f"Hoy: {bar(dp, MAX_PTS)} {dp}/{MAX_PTS} pts\n"
            f"Total acumulado: {tp} pts",
            parse_mode="Markdown"
        )
    return handler

async def resumen_nocturno(ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    await ctx.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            f"🌙 *BOUNCE — Resumen del día* `{today_key()}`\n\n"
            f"`{ranking_text(data)}`\n\n_Mañana es otro día. A darle 🔥_"
        ),
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("registrar", cmd_registrar))
    app.add_handler(CommandHandler("ranking",   cmd_ranking))
    app.add_handler(CommandHandler("miperfil",  cmd_miperfil))
    for task_id in TASKS:
        app.add_handler(CommandHandler(task_id, make_task_handler(task_id)))
    app.job_queue.run_daily(
        resumen_nocturno,
        time=time(hour=23, minute=0, tzinfo=ART),
    )
    print("🟢 BOUNCE Bot corriendo... (Ctrl+C para detener)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
