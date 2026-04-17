import asyncio
import json
import random
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import uvicorn

# ===== ВСТАВЬТЕ ВАШ ТОКЕН СЮДА =====
TOKEN = ""
# ====================================

PORT = 8000

# Получаем URL от Render (автоматически)
import os
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://localhost")
if WEBHOOK_URL == "https://localhost":
    print("⚠️ ВНИМАНИЕ: RENDER_EXTERNAL_URL не задан! Вебхук не установится.")

# ---------- ВСЕ ВАШИ КОМАНДЫ ----------
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

async def calculate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        allowed = set("0123456789+-*/(). ")
        if all(c in allowed for c in text):
            result = eval(text)
            await update.message.reply_text(f"🧮 = {result}")
    except:
        pass

async def react_to_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎨 Классный стикер! Спасибо 😊")

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

# ---------- ЗАПУСК ВЕБХУКА ----------
async def main():
    if not TOKEN:
        print("❌ ОШИБКА: Токен не вставлен! Откройте файл bot.py и вставьте токен в кавычки.")
        return
    
    # Создаём приложение Telegram
    app = Application.builder().token(TOKEN).updater(None).build()
    
    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("random", random_cmd))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("calc", calculate))  # Если хотите отдельную команду
    
    # Обработчик для математики в любом сообщении
    async def auto_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message and update.message.text and any(op in update.message.text for op in '+-*/'):
            if not update.message.text.startswith('/'):
                await calculate(update, context)
    app.add_handler(auto_calc)
    
    # Обработчик стикеров
    async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message and update.message.sticker:
            await react_to_sticker(update, context)
    app.add_handler(sticker_handler)
    
    # Обработчик новых участников
    app.add_handler(CommandHandler("new_chat_members", welcome_new_member))
    
    # Устанавливаем вебхук
    webhook_url = f"{WEBHOOK_URL}/telegram"
    if WEBHOOK_URL != "https://localhost":
        await app.bot.set_webhook(webhook_url)
        print(f"✅ Вебхук установлен: {webhook_url}")
    else:
        print("❌ Вебхук НЕ установлен: RENDER_EXTERNAL_URL не задан")
    
    # Настраиваем веб-сервер Starlette
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
    
    # Запускаем сервер
    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    
    async with app:
        await app.start()
        print(f"🚀 Бот запущен на порту {PORT}")
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())