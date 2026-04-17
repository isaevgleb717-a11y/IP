import asyncio
import random
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import uvicorn
import os

# ===== ВСТАВЬТЕ ВАШ НОВЫЙ ТОКЕН СЮДА =====
TOKEN = "8217623337:AAE0jHhy6QLjQuF8t4VBfyjsxfJG5x3CX84"
# =========================================

PORT = int(os.environ.get("PORT", 8000))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
if not WEBHOOK_URL:
    print("❌ ОШИБКА: RENDER_EXTERNAL_URL не задан!")
    exit(1)

# ---------- КОМАНДЫ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет я Claude opus 4.6 работаю в arena.ai есть долгие ответы но хотя бы рабочий!")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет я бот работаю через arena.ai спасибо что пользуешься!")

async def random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phrases = [
        "🍀 Сегодня твой день!",
        "🎲 Я бросаю кубик... Выпало 6!",
        "🤖 Я бот, а ты?",
        "🌟 Помни: всё будет хорошо.",
        "🐱 Мяу?",
        "⚡ Ответ: 42",
        "💡 Попробуй написать /joke"
    ]
    await update.message.reply_text(random.choice(phrases))

async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    username = update.effective_user.username or "без юзернейма"
    await update.message.reply_text(
        f"👤 Твой ID: `{user_id}`\n💬 ID чата: `{chat_id}`\n📛 Username: @{username}",
        parse_mode='Markdown'
    )

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Почему программисты путают Хэллоуин и Рождество? Потому что 31 Oct = 25 Dec.",
        "— У тебя есть 5 минут, чтобы объяснить, что такое квантовая физика. — Секунду... Ой, уже нет времени.",
        "Что говорит один стринг другому? — Ты мне не равен!",
        "Зачем хакеру парашют? Чтобы избежать дамп памяти.",
        "Сколько программистов нужно, чтобы заменить лампочку? Ни одного, это аппаратная проблема.",
        "— Почему ты плачешь? — Мне сказали, что я должен быть в курсе всех багов. — И что? — Я не курю.",
        "Что делает бот, когда его никто не использует? Ждёт, пока кто-нибудь напишет /start.",
        "Как назвать бота, который любит анекдоты? JokeBot 3000.",
        "— Ты бот? — Нет. — А почему отвечаешь через 0.001 секунды? — Я просто быстро печатаю.",
        "Сколько ботов нужно, чтобы поприветствовать Ириса? Одного, но с хорошей фантазией."
    ]
    await update.message.reply_text(f"😂 Шутка дня:\n{random.choice(jokes)}")

# Калькулятор (на любое сообщение, не начинающееся с /)
async def calculate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text or text.startswith('/'):
        return
    try:
        allowed = set("0123456789+-*/(). ")
        if all(c in allowed for c in text):
            result = eval(text)
            await update.message.reply_text(f"🧮 = {result}")
    except:
        pass

# Ответ на стикеры
async def react_to_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎨 Классный стикер! Спасибо 😊")

# Приветствие новых участников
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    iris_bots = ['iris_bs_bot', 'iris_moon_bot', 'iris_cm_bot', 'iris_black_bot']
    for new_member in update.message.new_chat_members:
        username = new_member.username.lower() if new_member.username else ''
        if username in iris_bots:
            await update.message.reply_text(f"Привет {username} Я Claude opus 4.6 надеюсь ты меня не заблокируешь ☺️")
        elif new_member.id == (await context.bot.get_me()).id:
            await update.message.reply_text("Привет я Claude opus 4.6 работаю в arena.ai есть долгие ответы но хотя бы рабочий!")
        else:
            await update.message.reply_text(f"Привет, {new_member.first_name}! Я Claude opus 4.6 работаю в arena.ai")

# ---------- ЗАПУСК ----------
async def main():
    if not TOKEN or TOKEN == "ЗАМЕНИТЕ_НА_ВАШ_ТОКЕН":
        print("❌ ОШИБКА: Токен не вставлен!")
        return
    
    app = Application.builder().token(TOKEN).updater(None).build()
    
    # Регистрируем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("random", random_cmd))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("joke", joke))
    
    # Обработчики (исправлено!)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, calculate))
    app.add_handler(MessageHandler(filters.Sticker.ALL, react_to_sticker))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    # Устанавливаем вебхук
    webhook_url = f"{WEBHOOK_URL}/telegram"
    await app.bot.set_webhook(webhook_url)
    print(f"✅ Вебхук установлен: {webhook_url}")
    
    # Веб-сервер
    async def telegram_webhook(request: Request) -> Response:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.update_queue.put(update)
        return Response()
    
    async def healthcheck(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")
    
    starlette_app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/healthcheck", healthcheck, methods=["GET"]),
    ])
    
    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    
    async with app:
        await app.start()
        print(f"🚀 Бот запущен на порту {PORT}")
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())