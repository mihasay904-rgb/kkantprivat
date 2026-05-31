import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, filters, MessageHandler
)

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────────────────
TOKEN = ""
GROUP_LINK = "https://t.me/+"
ACCESS_PRICE = 200      # цена доступа в рублях
ADMIN_ID =     # твой Telegram ID (@userinfobot)
DB_FILE = "users.json"  # файл с балансами

# ─── База данных (простой JSON файл) ──────────────────────────────────────────
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def get_user(uid: int):
    db = load_db()
    uid = str(uid)
    if uid not in db:
        db[uid] = {"balance": 0, "access": False, "username": ""}
        save_db(db)
    return db[uid]

def update_user(uid: int, data: dict):
    db = load_db()
    uid = str(uid)
    db[uid].update(data)
    save_db(db)

# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    # Сохраняем пользователя
    u = get_user(uid)
    update_user(uid, {"username": user.username or user.first_name})

    # Уведомляем админа о новом пользователе
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"👤 Новый пользователь!\n"
             f"Имя: {user.full_name}\n"
             f"Username: @{user.username}\n"
             f"ID: {uid}\n"
             f"Баланс: {u['balance']}₽"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Мой баланс", callback_data="balance")],
        [InlineKeyboardButton("🔐 Купить доступ", callback_data="buy")],
    ])
    await update.message.reply_text(
        f"👾 Привет, {user.first_name}!\n\n"
        f"Твой ID: `{uid}`\n"
        f"Баланс: *{u['balance']}₽*\n\n"
        f"Доступ к группе стоит *{ACCESS_PRICE}₽*.\n"
        f"Пополни баланс у администратора и нажми «Купить доступ».",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ─── Кнопки ───────────────────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    u = get_user(uid)

    if query.data == "balance":
        status = "✅ Есть доступ" if u["access"] else "❌ Нет доступа"
        await query.message.reply_text(
            f"💰 Твой баланс: *{u['balance']}₽*\n"
            f"Статус: {status}\n"
            f"Твой ID: `{uid}`",
            parse_mode="Markdown"
        )

    elif query.data == "buy":
        if u["access"]:
            await query.message.reply_text(
                f"✅ У тебя уже есть доступ!\n{GROUP_LINK}"
            )
        elif u["balance"] >= ACCESS_PRICE:
            # Списываем баланс и даём доступ
            update_user(uid, {
                "balance": u["balance"] - ACCESS_PRICE,
                "access": True
            })
            await query.message.reply_text(
                f"✅ *Доступ куплен!*\n\n"
                f"Списано: {ACCESS_PRICE}₽\n"
                f"Остаток: {u['balance'] - ACCESS_PRICE}₽\n\n"
                f"Ссылка на группу:\n{GROUP_LINK}\n\n"
                f"⚠️ Не делись ссылкой!",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔐 Куплен доступ!\nID: {uid} (@{query.from_user.username})"
            )
        else:
            need = ACCESS_PRICE - u["balance"]
            await query.message.reply_text(
                f"❌ Недостаточно средств!\n\n"
                f"Баланс: *{u['balance']}₽*\n"
                f"Нужно ещё: *{need}₽*\n\n"
                f"Обратись к администратору для пополнения.\n"
                f"Твой ID: `{uid}`",
                parse_mode="Markdown"
            )

# ─── АДМИН КОМАНДЫ ────────────────────────────────────────────────────────────

# /addbalance 123456789 500 — пополнить баланс
async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        amount = int(context.args[1])
        u = get_user(uid)
        new_balance = u["balance"] + amount
        update_user(uid, {"balance": new_balance})
        await update.message.reply_text(
            f"✅ Баланс пополнен!\nID: {uid}\nДобавлено: {amount}₽\nНовый баланс: {new_balance}₽"
        )
        # Уведомляем пользователя
        await context.bot.send_message(
            chat_id=uid,
            text=f"💰 Твой баланс пополнен на *{amount}₽*!\n"
                 f"Текущий баланс: *{new_balance}₽*\n\n"
                 f"Нажми /start чтобы купить доступ.",
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text("Использование: /addbalance [ID] [сумма]")

# /setbalance 123456789 200 — установить баланс
async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        amount = int(context.args[1])
        update_user(uid, {"balance": amount})
        await update.message.reply_text(f"✅ Баланс установлен!\nID: {uid}\nБаланс: {amount}₽")
    except Exception:
        await update.message.reply_text("Использование: /setbalance [ID] [сумма]")

# /removeaccess 123456789 — забрать доступ
async def removeaccess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        update_user(uid, {"access": False})
        await update.message.reply_text(f"✅ Доступ забран у ID: {uid}")
    except Exception:
        await update.message.reply_text("Использование: /removeaccess [ID]")

# /userinfo 123456789 — инфо о пользователе
async def userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = context.args[0]
        db = load_db()
        if uid not in db:
            await update.message.reply_text("Пользователь не найден.")
            return
        u = db[uid]
        await update.message.reply_text(
            f"👤 Пользователь {uid}\n"
            f"Username: @{u.get('username', '?')}\n"
            f"Баланс: {u['balance']}₽\n"
            f"Доступ: {'✅ Да' if u['access'] else '❌ Нет'}"
        )
    except Exception:
        await update.message.reply_text("Использование: /userinfo [ID]")

# /allusers — список всех пользователей
async def allusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    db = load_db()
    if not db:
        await update.message.reply_text("Пользователей нет.")
        return
    text = "👥 Все пользователи:\n\n"
    for uid, u in db.items():
        access = "✅" if u["access"] else "❌"
        text += f"{access} ID: {uid} | @{u.get('username','?')} | {u['balance']}₽\n"
    await update.message.reply_text(text)

# /giveaccess 123456789 — выдать доступ без оплаты
async def giveaccess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        get_user(uid)
        update_user(uid, {"access": True})
        await update.message.reply_text(f"✅ Доступ выдан ID: {uid}")
        await context.bot.send_message(
            chat_id=uid,
            text=f"🎁 Тебе выдан бесплатный доступ!\n\n{GROUP_LINK}",
        )
    except Exception:
        await update.message.reply_text("Использование: /giveaccess [ID]")

# /adminhelp — список команд админа
async def adminhelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "👑 *Команды админа:*\n\n"
        "/addbalance [ID] [сумма] — пополнить баланс\n"
        "/setbalance [ID] [сумма] — установить баланс\n"
        "/giveaccess [ID] — выдать доступ бесплатно\n"
        "/removeaccess [ID] — забрать доступ\n"
        "/userinfo [ID] — инфо о пользователе\n"
        "/allusers — все пользователи\n",
        parse_mode="Markdown"
    )

# ─── Запуск ───────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(CommandHandler("setbalance", setbalance))
    app.add_handler(CommandHandler("giveaccess", giveaccess))
    app.add_handler(CommandHandler("removeaccess", removeaccess))
    app.add_handler(CommandHandler("userinfo", userinfo))
    app.add_handler(CommandHandler("allusers", allusers))
    app.add_handler(CommandHandler("adminhelp", adminhelp))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()