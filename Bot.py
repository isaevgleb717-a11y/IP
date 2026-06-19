import asyncio
import random
import os
import time
import re
import requests
from bs4 import BeautifulSoup
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import uvicorn
import json
import hashlib
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from groq import Groq

# ===== НАСТРОЙКИ (из переменных окружения) =====
TOKEN = os.environ.get("TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not TOKEN:
    raise ValueError("Переменная окружения TOKEN не задана!")
if not GROQ_API_KEY:
    raise ValueError("Переменная окружения GROQ_API_KEY не задана!")
# ===============================================

PORT = int(os.environ.get("PORT", 8000))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")
if not WEBHOOK_URL:
    print("❌ RENDER_EXTERNAL_URL не задан")
    exit(1)

# ===== ИНИЦИАЛИЗАЦИЯ =====
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
groq_client = Groq(api_key=GROQ_API_KEY)

# Глобальные базы данных
news_db = None
code_db = None
dialog_db = None
url_db = None

# История диалогов
chat_histories = {}

# Флаг активности бота
bot_active = True

# ===== ФУНКЦИИ ПАРСИНГА =====
def parse_tass_news(keyword=None):
    try:
        url = "https://tass.ru/"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = []
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href and '/article/' in href:
                title = link.get_text(strip=True)
                if title and len(title) > 10:
                    if not keyword or keyword.lower() in title.lower():
                        articles.append({
                            'title': title,
                            'url': f"https://tass.ru{href}"
                        })
        return articles[:10]
    except Exception as e:
        print(f"Ошибка парсинга ТАСС: {e}")
        return []

def parse_code_sites(query=None):
    try:
        if query:
            url = f"https://api.github.com/search/code?q={query}&per_page=5"
            headers = {'Accept': 'application/vnd.github.v3+json'}
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            results = []
            for item in data.get('items', []):
                results.append({
                    'name': item.get('name', ''),
                    'url': item.get('html_url', ''),
                    'description': item.get('path', '')
                })
            return results
        return []
    except Exception as e:
        print(f"Ошибка парсинга кода: {e}")
        return []

def parse_url_content(url):
    try:
        response = requests.get(url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines[:200])
        return content
    except Exception as e:
        print(f"Ошибка парсинга URL: {e}")
        return None

def get_crypto_price(coin_id, vs_currencies=['usd','eur','rub','gbp','jpy']):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={','.join(vs_currencies)}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if coin_id in data:
            return data[coin_id]
        return None
    except Exception as e:
        print(f"Ошибка получения курса: {e}")
        return None

def get_fiat_rates(base='USD', targets=['USD','EUR','RUB','GBP','JPY']):
    try:
        url = f"https://api.exchangerate.host/latest?base={base}&symbols={','.join(targets)}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get('success'):
            return data['rates']
        return None
    except Exception as e:
        print(f"Ошибка получения курсов фиата: {e}")
        return None

# ===== RAG =====
def create_vector_db(documents, db_type='news'):
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        texts = []
        for doc in documents:
            if isinstance(doc, dict):
                text = doc.get('title', '') + ". " + doc.get('description', '')
                texts.append(text)
            else:
                texts.append(str(doc))
        chunks = text_splitter.create_documents(texts)
        collection_name = f"{db_type}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        db = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            collection_name=collection_name
        )
        return db
    except Exception as e:
        print(f"Ошибка создания БД: {e}")
        return None

def search_db(db, query, top_k=3):
    if not db:
        return []
    try:
        return db.similarity_search(query, k=top_k)
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return []

def generate_answer(query, context_docs, is_code=False):
    if not context_docs:
        if is_code:
            return "🔍 Не найдено подходящих примеров."
        return "🔍 Не найдено информации."
    context = "\n\n".join([doc.page_content for doc in context_docs[:3]])
    try:
        prompt = f"""
        Используй следующий контекст для ответа на вопрос.
        Если в контексте нет информации, скажи об этом честно.

        Контекст:
        {context}

        Вопрос: {query}

        Ответ:
        """
        response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка Groq: {e}")
        return "⚠️ Не удалось сгенерировать ответ. Вот найденные материалы:\n\n" + "\n".join([doc.page_content[:200] for doc in context_docs[:2]])

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    bot_active = True
    await update.message.reply_text(
        "🧠 *Huminis Opus 4.6*\n"
        "Я работаю с помощью API HC (Huminis Corporation).\n\n"
        "Используй /help для списка команд.",
        parse_mode='Markdown'
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    bot_active = False
    await update.message.reply_text("⏸️ Бот остановлен. Для запуска используйте /start.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🧠 *Huminis Opus 4.6 RAG — Команды*

📰 *Новости:*
`/news [слово]` — найти новости по ключевому слову
`/learn_news` — обучить бота на текущих новостях

💻 *Код:*
`/code [запрос]` — найти примеры кода
`/learn_code` — обучить бота на коде

🔗 *Сайты и ссылки:*
`/open_url <url>` — прочитать и запомнить содержимое страницы
`/learn_dialog` — запомнить последние 20 сообщений в чате

💰 *Курсы валют:*
`/moneycursu <BTC|ETH|USD|EUR|RUB>` — показать курс в разных валютах

🔍 *Общие запросы:*
`/query [вопрос]` — задать вопрос по изученному материалу

📋 *Управление:*
`/start` — запустить бота (если остановлен)
`/stop` — остановить бота (не отвечает)
`/help` — эта справка
`/info` — информация о модели

🎲 *Развлечения:*
`/random` — случайная фраза
`/joke` — шутка
"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🧠 *Huminis Opus 4.6 (≈750B)*\n"
        "📅 Дата выпуска: 4 июня 2026\n"
        "🏗️ Архитектура: CGH3+ (20% Claude, 20% GPT, 60% Huminis)\n"
        "⚡ Активных параметров: ≈300B на токен\n"
        "📚 Контекст: 320 000 токенов\n"
        "🎯 Точность: 99.1% MMLU, 99.8% TruthfulQA\n"
        "🌍 Коллективный интеллект: активен\n"
        "🔮 Квантовое ускорение: доступно\n"
        "🤖 Работаю с помощью API HC (Huminis Corporation).\n\n"
        "_Синергия, честность, эволюция._"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phrases = [
        "🧠 Коллективный интеллект говорит: сегодня твой день!",
        "⚡ Квантовое ускорение активировано!",
        "🤖 Я — Huminis Opus 4.6 RAG на Groq.",
        "🌟 Синергия с человечеством — наша цель.",
        "🔮 Предсказание: ты сделаешь что-то важное сегодня."
    ]
    await update.message.reply_text(random.choice(phrases))

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "Почему RAG лучше дообучения? Потому что не нужно переучивать 750 миллиардов параметров!",
        "Сколько нейронов нужно, чтобы заменить лампочку? RAG знает ответ!",
        "— Ты ИИ? — Нет, я RAG-бот на Groq. — А почему отвечаешь так быстро? — Потому что Groq быстрый!"
    ]
    await update.message.reply_text(f"🧠 {random.choice(jokes)}")

# ===== RAG-КОМАНДЫ =====
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    keyword = " ".join(args) if args else ""
    await update.message.reply_text("🔍 Ищу новости...")
    articles = parse_tass_news(keyword)
    if not articles:
        await update.message.reply_text("❌ Не найдено новостей.")
        return
    response = "📰 *Новости:*\n\n"
    for i, article in enumerate(articles[:5], 1):
        response += f"{i}. [{article['title']}]({article['url']})\n"
    await update.message.reply_text(response, parse_mode='Markdown')

async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Напишите запрос после /code, например:\n`/code python sort array`", parse_mode='Markdown')
        return
    query = " ".join(args)
    await update.message.reply_text("💻 Ищу примеры кода...")
    results = parse_code_sites(query)
    if not results:
        await update.message.reply_text("❌ Не найдено примеров кода.")
        return
    response = "💻 *Примеры кода:*\n\n"
    for i, item in enumerate(results[:5], 1):
        response += f"{i}. [{item['name']}]({item['url']})\n"
        if item.get('description'):
            response += f"   _{item['description']}_\n"
    await update.message.reply_text(response, parse_mode='Markdown')

async def learn_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global news_db
    await update.message.reply_text("📖 Обучаюсь на новостях ТАСС... Подождите.")
    articles = parse_tass_news()
    if not articles:
        await update.message.reply_text("❌ Не удалось получить новости.")
        return
    news_db = create_vector_db(articles, 'news')
    if news_db:
        await update.message.reply_text(f"✅ Обучено на {len(articles)} статьях!")
    else:
        await update.message.reply_text("❌ Не удалось создать базу знаний.")

async def learn_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global code_db
    args = context.args
    query = " ".join(args) if args else "python"
    await update.message.reply_text(f"💻 Обучаюсь на коде по запросу '{query}'...")
    results = parse_code_sites(query)
    if not results:
        await update.message.reply_text("❌ Не удалось получить код.")
        return
    code_db = create_vector_db(results, 'code')
    if code_db:
        await update.message.reply_text(f"✅ Обучено на {len(results)} примерах!")
    else:
        await update.message.reply_text("❌ Не удалось создать базу знаний.")

async def query_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Напишите вопрос после /query", parse_mode='Markdown')
        return
    query = " ".join(args)
    await update.message.reply_text("🔍 Ищу ответ...")
    news_results = search_db(news_db, query)
    code_results = search_db(code_db, query)
    dialog_results = search_db(dialog_db, query)
    url_results = search_db(url_db, query)
    all_results = news_results + code_results + dialog_results + url_results
    if not all_results:
        await update.message.reply_text(
            "❌ Я не нашёл информации.\n\n"
            "💡 Попробуйте:\n"
            "• Обучить меня на новостях: /learn_news\n"
            "• Обучить меня на коде: /learn_code\n"
            "• Запомнить диалог: /learn_dialog\n"
            "• Добавить сайт: /open_url <url>"
        )
        return
    answer = generate_answer(query, all_results, bool(code_results))
    await update.message.reply_text(answer)

# ===== НОВЫЕ КОМАНДЫ =====
# 1. Обучение диалогам
async def learn_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global dialog_db
    chat_id = update.effective_chat.id
    if chat_id not in chat_histories or len(chat_histories[chat_id]) < 2:
        await update.message.reply_text("❌ Недостаточно сообщений в чате для обучения. Нужно хотя бы 2 сообщения.")
        return
    history = chat_histories[chat_id][-20:]
    dialog_text = "\n".join(history)
    await update.message.reply_text("📖 Обучаюсь на диалогах...")
    db = create_vector_db([dialog_text], 'dialog')
    if db:
        dialog_db = db
        await update.message.reply_text(f"✅ Обучено на {len(history)} сообщениях.")
    else:
        await update.message.reply_text("❌ Не удалось создать базу знаний.")

# 2. Просмотр сайта по ссылке
async def open_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global url_db
    args = context.args
    if not args:
        await update.message.reply_text("❌ Укажите ссылку после /open_url, например:\n`/open_url https://example.com`", parse_mode='Markdown')
        return
    url = args[0]
    if not url.startswith('http'):
        url = 'http://' + url
    await update.message.reply_text(f"🔗 Открываю {url}...")
    content = parse_url_content(url)
    if not content:
        await update.message.reply_text("❌ Не удалось прочитать страницу.")
        return
    db = create_vector_db([{'title': f'Страница: {url}', 'description': content[:1000]}], 'url')
    if db:
        url_db = db
        await update.message.reply_text(f"✅ Страница сохранена в память. (Извлечено {len(content)} символов)")
    else:
        await update.message.reply_text("❌ Не удалось сохранить страницу.")

# 3. Курс валют и криптовалют
async def moneycursu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Укажите валюту, например:\n`/moneycursu BTC`\n`/moneycursu USD`", parse_mode='Markdown')
        return
    symbol = args[0].upper()
    crypto_map = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'USDT': 'tether',
        'BNB': 'binancecoin',
        'SOL': 'solana',
        'XRP': 'ripple',
        'ADA': 'cardano',
        'DOGE': 'dogecoin',
        'DOT': 'polkadot',
        'LINK': 'chainlink'
    }
    fiat_currencies = ['USD', 'EUR', 'RUB', 'GBP', 'JPY', 'CNY', 'CHF', 'CAD', 'AUD', 'NZD']
    if symbol in crypto_map:
        coin_id = crypto_map[symbol]
        prices = get_crypto_price(coin_id, vs_currencies=['usd','eur','rub','gbp','jpy','cny','chf','cad','aud','nzd'])
        if prices:
            text = f"💰 *Курс {symbol}*\n\n"
            for curr, val in prices.items():
                text += f"• {curr.upper()}: {val:.2f}\n"
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Не удалось получить курс. Проверьте правильность символа.")
    elif symbol in fiat_currencies:
        rates = get_fiat_rates(base=symbol)
        if rates:
            text = f"💰 *Курс {symbol}*\n\n"
            for curr, val in rates.items():
                if curr != symbol:
                    text += f"• {curr}: {val:.4f}\n"
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Не удалось получить курс. Возможно, API временно недоступен.")
    else:
        await update.message.reply_text(
            f"❌ Неизвестная валюта. Поддерживаемые: {', '.join(list(crypto_map.keys()) + fiat_currencies)}"
        )

# ===== ОБРАБОТЧИК ТЕКСТА (запись истории и простые ответы) =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if not bot_active:
        return
    text = update.message.text
    if not text or text.startswith('/'):
        return
    chat_id = update.effective_chat.id
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    chat_histories[chat_id].append(f"{update.effective_user.first_name}: {text}")
    if len(chat_histories[chat_id]) > 100:
        chat_histories[chat_id] = chat_histories[chat_id][-100:]
    lower_text = text.lower()
    if lower_text in ['привет', 'здравствуй', 'хай', 'салам']:
        await update.message.reply_text("Привет! Чем могу помочь?")
        return
    if 'как дела' in lower_text:
        await update.message.reply_text("У меня всё отлично! А у тебя?")
        return

# ===== ОБРАБОТЧИК СТИКЕРОВ =====
async def sticker_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_active:
        return
    await update.message.reply_text(random.choice([
        "🎨 Классный стикер!",
        "🧠 Коллективный интеллект одобряет.",
        "⚡ Groq заметил твой стикер!"
    ]))

# ===== ПРИВЕТСТВИЕ НОВЫХ УЧАСТНИКОВ (обновлено) =====
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    iris_bots = ['iris_bs_bot', 'iris_moon_bot', 'iris_cm_bot', 'iris_black_bot']
    # Новая ссылка на изображение
    image_url = "https://drive.google.com/uc?export=view&id=1NJ3tFi7LVC1O_SKXcf6CnL1J0rvDMeIf"
    for new_member in update.message.new_chat_members:
        username = new_member.username.lower() if new_member.username else ''
        name = new_member.first_name
        if username in iris_bots:
            text = f"🧠 Привет {username}! Я Huminis Opus 4.6, работаю с помощью API HC (Huminis Corporation)."
        elif new_member.id == (await context.bot.get_me()).id:
            text = "🧠 Привет! Я Huminis Opus 4.6, работаю с помощью API HC (Huminis Corporation)."
        else:
            text = f"🧠 Привет, {name}! Я Huminis Opus 4.6, работаю с помощью API HC (Huminis Corporation)."
        try:
            await update.message.reply_photo(photo=image_url, caption=text)
        except:
            await update.message.reply_text(text)

# ===== KEEP-ALIVE =====
async def keep_alive():
    while True:
        try:
            for i in range(50000):
                _ = i * i
            print(f"🧠 Huminis Opus 4.6 RAG активен, время: {time.strftime('%H:%M:%S')}")
            await asyncio.sleep(240)
        except:
            await asyncio.sleep(60)

# ===== ЗАПУСК =====
async def main():
    app = Application.builder().token(TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("random", random_cmd))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("code", code_command))
    app.add_handler(CommandHandler("learn_news", learn_news))
    app.add_handler(CommandHandler("learn_code", learn_code))
    app.add_handler(CommandHandler("query", query_command))
    app.add_handler(CommandHandler("learn_dialog", learn_dialog))
    app.add_handler(CommandHandler("open_url", open_url))
    app.add_handler(CommandHandler("moneycursu", moneycursu))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    webhook_url = f"{WEBHOOK_URL}/telegram"
    await app.bot.set_webhook(webhook_url)
    print(f"✅ Вебхук: {webhook_url}")

    async def webhook(request: Request) -> Response:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.update_queue.put(update)
        return Response()

    async def health(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    starlette_app = Starlette(routes=[
        Route("/telegram", webhook, methods=["POST"]),
        Route("/healthcheck", health, methods=["GET"]),
    ])

    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)

    async with app:
        await app.start()
        asyncio.create_task(keep_alive())
        print(f"🧠 Huminis Opus 4.6 RAG запущен на порту {PORT}")
        await server.serve()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())