import logging
import json
import os
from datetime import datetime, time
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── CONFIG ───────────────────────────────────────────────────────────────────
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

# ── PERSISTENCIA ─────────────────────────────────────────────────────────────
def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "today": today_key(),
        "done": {}, "total": {},
        "users": {}, "usernames": {},
        "weekly": {}, "monthly": {},
        "week": current_week(), "month": current_month()
    }

def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def today_key():
    return datetime.now(ART).strftime("%Y-%m-%d")

def current_week():
    now = datetime.now(ART)
    return f"{now.year}-W{now.isocalendar()[1]:02d}"

def current_month():
    return datetime.now(ART).strftime("%Y-%m")

def check_periods(data):
    """Resetea daily/weekly/monthly según corresponda."""
    changed = False

    if data.get("today") != today_key():
        data["today"] = today_key()
        data["done"]  = {}
        changed = True

    if data.get("week") != current_week():
        data["week"]   = current_week()
        data["weekly"] = {}
        changed = True

    if data.get("month") != current_month():
        data["month"]   = current_month()
        data["monthly"] = {}
        changed = True

    if changed:
        save(data)
    return data

def find_member(name: str):
    n = name.strip().lower()
    for m in MEMBERS:
        if m.lower() == n or m.lower().startswith(n):
            return m
    return None

# ── UI HELPERS ────────────────────────────────────────────────────────────────
def bar(done, total, width=8):
    filled = round((done / total) * width) if total else 0
    return "█" * filled + "░" * (width - filled)

def mention(member, data):
    """Devuelve @username si está disponible, sino el nombre."""
    uname = data.get("usernames", {}).get(member)
    return f"@{uname}" if uname else f"*{member}*"

def ranking_block(scores, label_col=8):
    medals   = ["🥇","🥈","🥉"] + ["  "] * 10
    sorted_m = sorted(scores.keys(), key=lambda m: scores[m], reverse=True)
    lines = []
    for i, m in enumerate(sorted_m):
        pts = scores[m]
        lines.append(f"{medals[i]} {m:<{label_col}} {pts} pts")
    return "\n".join(lines)

def daily_scores(data):
    return {m: sum(TASKS[t]["pts"] for t in data["done"].get(m, [])) for m in MEMBERS}

def resolve_member(update, ctx, data):
    if ctx.args:
        return find_member(" ".join(ctx.args))
    uid = str(update.effective_user.id)
    return data.get("users", {}).get(uid)

# ── COMMANDS ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cmds = "\n".join(f"  /{k}  {v['emoji']} {v['label']} (+{v['pts']}pts)" for k, v in TASKS.items())
    await update.message.reply_text(
        "🟢 *BOUNCE Tracker activo*\n\n"
        "Comandos de tarea:\n" + cmds + "\n\n"
        "Usá `/tiktok` si ya te registraste, o `/tiktok Lucas` si no.\n\n"
        "Otros:\n"
        "  /registrar NombreCompleto\n"
        "  /ranking — tabla del día\n"
        "  /semanal — ranking de la semana\n"
        "  /mensual — ranking del mes\n"
        "  /miperfil — tus tareas de hoy",
        parse_mode="Markdown"
    )

async def cmd_registrar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = check_periods(load())
    if not ctx.args:
        await update.message.reply_text("Uso: `/registrar TuNombre`", parse_mode="Markdown")
        return
    member = find_member(" ".join(ctx.args))
    if not member:
        await update.message.reply_text(
            f"❌ Nombre no encontrado.\nMiembros: {', '.join(MEMBERS)}", parse_mode="Markdown"
        )
        return
    uid   = str(update.effective_user.id)
    uname = update.effective_user.username
    if "users" not in data:     data["users"]     = {}
    if "usernames" not in data: data["usernames"] = {}
    data["users"][uid]        = member
    if uname:
        data["usernames"][member] = uname
    save(data)
    await update.message.reply_text(
        f"✅ Registrado como *{member}*" + (f" (@{uname})" if uname else "") + ".",
        parse_mode="Markdown"
    )

async def cmd_ranking(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = check_periods(load())
    scores = daily_scores(data)
    await update.message.reply_text(
        f"🏆 *BOUNCE — Ranking hoy* `{today_key()}`\n\n`{ranking_block(scores)}`",
        parse_mode="Markdown"
    )

async def cmd_semanal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = check_periods(load())
    scores = {m: data["weekly"].get(m, 0) for m in MEMBERS}
    await update.message.reply_text(
        f"📅 *BOUNCE — Ranking semanal* `{current_week()}`\n\n`{ranking_block(scores)}`",
        parse_mode="Markdown"
    )

async def cmd_mensual(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = check_periods(load())
    scores = {m: data["monthly"].get(m, 0) for m in MEMBERS}
    await update.message.reply_text(
        f"📆 *BOUNCE — Ranking mensual* `{current_month()}`\n\n`{ranking_block(scores)}`",
        parse_mode="Markdown"
    )

async def cmd_miperfil(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data   = check_periods(load())
    member = resolve_member(update, ctx, data)
    if not member:
        await update.message.reply_text("Registrate con `/registrar TuNombre`.", parse_mode="Markdown")
        return
    done_today = data["done"].get(member, [])
    lines = [f"{'✅' if tid in done_today else '⬜'} {t['emoji']} {t['label']} (+{t['pts']}pts)" for tid, t in TASKS.items()]
    dp = sum(TASKS[t]["pts"] for t in done_today)
    tp = data["total"].get(member, 0)
    wp = data["weekly"].get(member, 0)
    mp = data["monthly"].get(member, 0)
    await update.message.reply_text(
        f"👤 *{member}* — hoy\n\n" + "\n".join(lines) +
        f"\n\n{bar(dp, MAX_PTS)} {dp}/{MAX_PTS} pts hoy\n"
        f"Esta semana: {wp} pts  |  Este mes: {mp} pts\n"
        f"Total histórico: {tp} pts",
        parse_mode="Markdown"
    )

def make_task_handler(task_id: str):
    async def handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        data   = check_periods(load())
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
        pts = task["pts"]
        data["total"][member]   = data["total"].get(member, 0)   + pts
        data["weekly"][member]  = data["weekly"].get(member, 0)  + pts
        data["monthly"][member] = data["monthly"].get(member, 0) + pts
        save(data)
        dp = sum(TASKS[t]["pts"] for t in done_today)
        tp = data["total"][member]
        await update.message.reply_text(
            f"{task['emoji']} *{member}* sumó *+{pts} pts* — {task['label']}!\n"
            f"Hoy: {bar(dp, MAX_PTS)} {dp}/{MAX_PTS} pts\n"
            f"Total acumulado: {tp} pts",
            parse_mode="Markdown"
        )
    return handler

# ── JOBS PROGRAMADOS ──────────────────────────────────────────────────────────
async def recordatorio_14(ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_message(
        chat_id=CHAT_ID,
        text="📢 *Recuerden subir contenido hoy!* 🎵\n_Cada post cuenta para el ranking._",
        parse_mode="Markdown"
    )

async def recordatorio_18(ctx: ContextTypes.DEFAULT_TYPE):
    await ctx.bot.send_message(
        chat_id=CHAT_ID,
        text="⚡ *Quedan pocas horas!* Hagan contenido ahora que todavía están a tiempo 🔥\n_A las 23:00 se cierra el día._",
        parse_mode="Markdown"
    )

async def recordatorio_22(ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    # Miembros que no subieron ningún TikTok hoy
    sin_tiktok = [m for m in MEMBERS if "tiktok" not in data["done"].get(m, [])]

    if not sin_tiktok:
        await ctx.bot.send_message(
            chat_id=CHAT_ID,
            text="✅ *Todo el equipo subió TikTok hoy. Rompieron!* 🏆",
            parse_mode="Markdown"
        )
        return

    menciones = " ".join(mention(m, data) for m in sin_tiktok)
    await ctx.bot.send_message(
        chat_id=CHAT_ID,
        text=f"⏰ {menciones}\n\n"
             "Un TikTok cuesta 20 minutos en hacerse. Por favor háganlo 🙏\n"
             "_Queda 1 hora para el cierre del día._",
        parse_mode="Markdown"
    )

async def resumen_nocturno(ctx: ContextTypes.DEFAULT_TYPE):
    data   = load()
    scores = daily_scores(data)
    await ctx.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            f"🌙 *BOUNCE — Resumen del día* `{today_key()}`\n\n"
            f"`{ranking_block(scores)}`\n\n"
            "_Mañana es otro día. A darle 🔥_"
        ),
        parse_mode="Markdown"
    )

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("registrar", cmd_registrar))
    app.add_handler(CommandHandler("ranking",   cmd_ranking))
    app.add_handler(CommandHandler("semanal",   cmd_semanal))
    app.add_handler(CommandHandler("mensual",   cmd_mensual))
    app.add_handler(CommandHandler("miperfil",  cmd_miperfil))

    for task_id in TASKS:
        app.add_handler(CommandHandler(task_id, make_task_handler(task_id)))

    jq = app.job_queue
    jq.run_daily(recordatorio_14,  time=time(14,  0, tzinfo=ART))
    jq.run_daily(recordatorio_18,  time=time(18,  0, tzinfo=ART))
    jq.run_daily(recordatorio_22,  time=time(22,  0, tzinfo=ART))
    jq.run_daily(resumen_nocturno, time=time(23,  0, tzinfo=ART))

    print("🟢 BOUNCE Bot corriendo... (Ctrl+C para detener)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
