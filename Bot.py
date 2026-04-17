import asyncio
import random
import os
import time
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import uvicorn

# ===== НАСТРОЙКИ =====
TOKEN = "8217623337:AAE0jHhy6QLjQuF8t4VBfyjsxfJG5x3CX84"  # ЗАМЕНИТЕ НА ВАШ ТОКЕН ПОСЛЕ /revoke
CREATOR_ID = 7474885162      # ВАШ TELEGRAM ID (узнаётся командой /id)
# =====================

PORT = int(os.environ.get("PORT", 8000))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
if not WEBHOOK_URL:
    print("❌ RENDER_EXTERNAL_URL не задан")
    exit(1)

# ---------- КОМАНДЫ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я Claude opus 4.6 работаю в arena.ai!")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я бот через arena.ai, спасибо что пользуешься!")

async def random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phrases = ["🍀 Сегодня твой день!", "🎲 Выпало 6!", "🤖 Я бот, а ты?", "🌟 Всё будет хорошо!", "🐱 Мяу?", "⚡ Ответ: 42"]
    await update.message.reply_text(random.choice(phrases))

async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает ID пользователя и чата"""
    user = update.effective_user
    chat = update.effective_chat
    
    user_id = user.id
    chat_id = chat.id
    username = user.username or "нет username"
    first_name = user.first_name or ""
    
    text = (
        f"👤 *Ваши данные:*\n\n"
        f"🆔 *Ваш ID:* `{user_id}`\n"
        f"💬 *ID чата:* `{chat_id}`\n"
        f"📛 *Username:* @{username}\n"
        f"👋 *Имя:* {first_name}\n\n"
        f"🔑 *Скопируйте ваш ID:* `{user_id}`"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Почему программисты путают Хэллоуин и Рождество? 31 Oct = 25 Dec.",
        "Что говорит один стринг другому? — Ты мне не равен!",
        "— Ты бот? — Нет. — А почему отвечаешь за 0.001 сек? — Быстро печатаю.",
        "Сколько программистов нужно, чтобы заменить лампочку? Ни одного, это аппаратная проблема.",
        "— Почему ты плачешь? — Мне сказали, что я должен быть в курсе всех багов. — И что? — Я не курю."
    ]
    await update.message.reply_text(f"😂 {random.choice(jokes)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
📋 *Команды бота:*

/start — Приветствие
/info — О боте
/help — Справка
/random — Случайная фраза
/id — Показать ваш ID
/joke — Случайная шутка
/request [текст] — Отправить запрос создателю

🎲 *Дополнительные возможности:*
• Напишите пример (2+2) — бот посчитает
• Пришлите стикер — бот ответит
• Добавьте бота в группу — поприветствует всех
"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет запрос создателю бота"""
    args = context.args
    if not args:
        await update.message.reply_text("❌ Напишите: `/request Ваш вопрос`", parse_mode='Markdown')
        return
    
    user_request = " ".join(args)
    user_name = update.effective_user.first_name
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else "нет username"
    user_id = update.effective_user.id
    
    try:
        await context.bot.send_message(
            chat_id=CREATOR_ID,
            text=f"📨 *НОВЫЙ ЗАПРОС!*\n\n"
                 f"👤 От: {user_name} {user_username}\n"
                 f"🆔 ID: `{user_id}`\n"
                 f"📝 Запрос: {user_request}",
            parse_mode='Markdown'
        )
        await update.message.reply_text("✅ Запрос отправлен создателю!")
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        await update.message.reply_text("❌ Не удалось отправить запрос. Попробуйте позже.")

# ---------- ОБРАБОТЧИКИ ----------
async def calculate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Калькулятор для любых математических выражений"""
    text = update.message.text
    if not text or text.startswith('/'):
        return
    try:
        if all(c in "0123456789+-*/(). " for c in text):
            result = eval(text)
            await update.message.reply_text(f"🧮 = {result}")
    except:
        pass

async def sticker_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ на стикеры"""
    await update.message.reply_text("🎨 Классный стикер! Спасибо 😊")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие новых участников с картинкой"""
    iris_bots = ['iris_bs_bot', 'iris_moon_bot', 'iris_cm_bot', 'iris_black_bot']
    image_url = "https://drive.google.com/uc?export=view&id=1GNFE3jnEHb9abzKmA7ZDmYg9Exj4EZr6"
    
    for new_member in update.message.new_chat_members:
        username = new_member.username.lower() if new_member.username else ''
        name = new_member.first_name
        
        if username in iris_bots:
            text = f"Привет {username}! Надеюсь не заблокируешь ☺️"
        elif new_member.id == (await context.bot.get_me()).id:
            text = "Привет! Я Claude opus 4.6 работаю в arena.ai!"
        else:
            text = f"Привет, {name}! Я Claude opus 4.6"
        
        try:
            await update.message.reply_photo(photo=image_url, caption=text)
        except:
            await update.message.reply_text(text)

# ---------- KEEP-ALIVE (чтобы бот не уснул) ----------
async def keep_alive():
    """Каждые 4 минуты создаёт активность, чтобы Render не усыпил бота"""
    while True:
        try:
            # Лёгкие вычисления для нагрузки
            for i in range(50000):
                _ = i * i
            print(f"💓 Бот активен, время: {time.strftime('%H:%M:%S')}")
            await asyncio.sleep(240)  # 4 минуты
        except Exception as e:
            print(f"Keep-alive ошибка: {e}")
            await asyncio.sleep(60)

# ---------- ЗАПУСК ----------
async def main():
    app = Application.builder().token(TOKEN).updater(None).build()
    
    # Регистрация команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("random", random_cmd))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("request", request_command))
    
    # Регистрация обработчиков
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, calculate))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_reply))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    # Настройка вебхука
    webhook_url = f"{WEBHOOK_URL}/telegram"
    await app.bot.set_webhook(webhook_url)
    print(f"✅ Вебхук установлен: {webhook_url}")
    
    # Веб-сервер для обработки запросов
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
        # Запускаем фоновую задачу keep-alive
        asyncio.create_task(keep_alive())
        print(f"🚀 Бот запущен на порту {PORT}")
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())