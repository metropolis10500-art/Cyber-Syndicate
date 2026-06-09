import asyncio
import logging
import sqlite3
import time
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from yoomoney import Client

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8727966393:AAENOC9N7CofxMct5WWuZDtpqyrl__Bwea4"
ADMIN_ID = 5494544187  # Твой Telegram ID
ADMIN_USERNAME = "@vladofix28" # Твой юзернейм для вывода

YOOMONEY_WALLET = "4100118935779591"  # Номер кошелька ЮMoney
YOOMONEY_TOKEN = "5133D1719448E2A5E1083A0FC605E369944CBB992B1D4490F13E2D4636C03191"  # API Токен ЮMoney
# =============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ym_client = Client(YOOMONEY_TOKEN)

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect('cyber_earn.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   username TEXT, 
                   crypto INTEGER DEFAULT 0,        -- Валюта для апгрейдов
                   rub_balance REAL DEFAULT 0,      -- Баланс для вывода
                   trust_factor REAL DEFAULT 0,     -- Лимит на вывод (Кэш-поинты)
                   servers INTEGER DEFAULT 1,       -- Доходность
                   referrer_id INTEGER DEFAULT 0,   -- Кто пригласил
                   last_login INTEGER)''')
conn.commit()

# ================= ЭКОНОМИКА =================
MIN_WITHDRAW = 1000 # Минималка на вывод

# Доходность: 1 Сервер приносит 100 Крипты в час. 
# Курс: 10,000 Крипты = 1 Рубль
SERVER_PRICE_RUB = 150 # Базовая цена сервера в рублях
CRYPTO_RATE = 10000    # Курс обмена крипты на рубли

# ================= КЛАВИАТУРЫ =================
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💻 Профиль"), KeyboardButton(text="🚀 Купить Сервер")],
        [KeyboardButton(text="🔄 Обменник"), KeyboardButton(text="👥 Рефералы")],
        [KeyboardButton(text="💳 Пополнить"), KeyboardButton(text="💸 Вывод Средств")]
    ], resize_keyboard=True)

# ================= ФУНКЦИИ =================
def collect_income(user_id):
    cursor.execute("SELECT last_login, servers FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row: return 0
    last_login, servers = row
    current_time = int(time.time())
    
    hours_passed = min((current_time - last_login) / 3600.0, 24) # Максимум 24 часа оффлайн
    income = int(hours_passed * (servers * 100)) # 100 крипты в час с 1 сервера
    
    if income > 0:
        cursor.execute("UPDATE users SET crypto = crypto + ?, last_login = ? WHERE user_id=?", 
                       (income, current_time, user_id))
        conn.commit()
    return income

# ================= ХЭНДЛЕРЫ ИГРОКА =================

# --- СТАРТ И РЕФЕРАЛКА ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    
    # Обработка реферальной ссылки: /start 123456789
    ref_id = 0
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id == user_id: ref_id = 0 # Нельзя быть своим рефералом

    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, last_login, referrer_id) VALUES (?, ?, ?, ?)",
                       (user_id, username, int(time.time()), ref_id))
        conn.commit()
        
        # Уведомляем пригласившего
        if ref_id > 0:
            try:
                await bot.send_message(ref_id, "🎉 <b>По вашей ссылке зарегистрировался новый хакер!</b>\nВы будете получать 10% от его пополнений.", parse_mode="HTML")
            except: pass

    text = (
        "🌐 <b>Добро пожаловать в Cyber Earn!</b>\n\n"
        "Здесь ты можешь заработать реальные деньги. Покупай мощные сервера, майни крипту, "
        "обменивай её на рубли и выводи на карту.\n\n"
        "<i>Чем мощнее твой ботнет, тем больше реальных денег ты получаешь.</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

# --- ПРОФИЛЬ ---
@dp.message(F.text == "💻 Профиль")
async def show_profile(message: Message):
    user_id = message.from_user.id
    income = collect_income(user_id)
    
    cursor.execute("SELECT crypto, rub_balance, trust_factor, servers FROM users WHERE user_id=?", (user_id,))
    crypto, rub, trust, servers = cursor.fetchone()
    
    rub_per_day = (servers * 100 * 24) / CRYPTO_RATE

    text = (
        f"👤 <b>Ваш профиль:</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💰 Баланс: <b>{rub:.2f} ₽</b>\n"
        f"💠 Крипта: <b>{crypto:,}</b>\n"
        f"⚡️ Траст-Фактор (Лимит): <b>{trust:.2f} ₽</b>\n\n"
        f"🖥 Серверов в сети: <b>{servers} шт.</b>\n"
        f"📈 Доходность: <b>~{rub_per_day:.2f} ₽ / день</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"<i>💡 Подсказка: Траст-Фактор нужен для вывода. Приглашайте друзей, чтобы увеличить его!</i>"
    )
    if income > 0: text += f"\n\n<i>✅ Сервера намайнили: +{income:,} 💠</i>"
    await message.answer(text, parse_mode="HTML")

# --- ПОКУПКА СЕРВЕРОВ ---
@dp.message(F.text == "🚀 Купить Сервер")
async def shop_menu(message: Message):
    user_id = message.from_user.id
    collect_income(user_id)
    cursor.execute("SELECT rub_balance, servers FROM users WHERE user_id=?", (user_id,))
    rub, servers = cursor.fetchone()
    
    cost = servers * SERVER_PRICE_RUB
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🖥 Купить за {cost} ₽", callback_data="buy_server")]
    ])
    await message.answer(f"🚀 <b>Рынок Оборудования</b>\n\nТекущие сервера: {servers}\nКаждый новый сервер стоит дороже, но приносит стабильный доход в крипте.\n\n<b>Цена следующего: {cost} ₽</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "buy_server")
async def process_buy_server(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT rub_balance, servers FROM users WHERE user_id=?", (user_id,))
    rub, servers = cursor.fetchone()
    cost = servers * SERVER_PRICE_RUB
    
    if rub < cost:
        await callback.answer("❌ Недостаточно рублей на балансе! Пополните счет.", show_alert=True)
        return
        
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ?, servers = servers + 1 WHERE user_id=?", (cost, user_id))
    conn.commit()
    await callback.message.edit_text("✅ <b>Сервер успешно куплен!</b> Ваш пассивный доход вырос.", parse_mode="HTML")

# --- ОБМЕННИК ---
@dp.message(F.text == "🔄 Обменник")
async def exchange_menu(message: Message):
    user_id = message.from_user.id
    collect_income(user_id)
    cursor.execute("SELECT crypto FROM users WHERE user_id=?", (user_id,))
    crypto = cursor.fetchone()[0]
    
    possible_rub = crypto / CRYPTO_RATE
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обменять всю Крипту", callback_data="exchange_all")]
    ])
    await message.answer(f"🔄 <b>Системный Обменник</b>\n\nКурс: {CRYPTO_RATE} 💠 = 1 ₽\n\nУ вас: <b>{crypto:,} 💠</b>\nВы получите: <b>{possible_rub:.2f} ₽</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "exchange_all")
async def process_exchange(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT crypto FROM users WHERE user_id=?", (user_id,))
    crypto = cursor.fetchone()[0]
    
    if crypto < CRYPTO_RATE:
        await callback.answer("❌ Минимальная сумма обмена: 10,000 Крипты.", show_alert=True)
        return
        
    rub_to_add = crypto / CRYPTO_RATE
    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, crypto = 0 WHERE user_id=?", (rub_to_add, user_id))
    conn.commit()
    await callback.message.edit_text(f"✅ Обмен успешен! Вы получили <b>{rub_to_add:.2f} ₽</b> на баланс.", parse_mode="HTML")

# --- РЕФЕРАЛКА ---
@dp.message(F.text == "👥 Рефералы")
async def ref_menu(message: Message):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (user_id,))
    refs_count = cursor.fetchone()[0]
    
    text = (
        f"👥 <b>Партнерская программа</b>\n\n"
        f"Вы получаете <b>10%</b> от суммы пополнения ваших рефералов на баланс и <b>+10% Траст-Фактора</b>!\n\n"
        f"🔗 Ваша ссылка:\n<code>{ref_link}</code>\n\n"
        f"Приглашено хакеров: <b>{refs_count}</b>"
    )
    await message.answer(text, parse_mode="HTML")


# ================= ПОПОЛНЕНИЕ (ЮМАНИ) =================
@dp.message(F.text == "💳 Пополнить")
async def deposit_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="500 ₽", callback_data="dep_500"), InlineKeyboardButton(text="1000 ₽", callback_data="dep_1000")],
        [InlineKeyboardButton(text="5000 ₽ (VIP-Множитель)", callback_data="dep_5000")]
    ])
    await message.answer("💳 <b>Пополнение баланса</b>\nПри пополнении вы получаете 30% Траст-Фактора от суммы.\nВыберите сумму:", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("dep_"))
async def create_deposit(callback: CallbackQuery):
    amount = int(callback.data.replace("dep_", ""))
    user_id = callback.from_user.id
    label = f"dep_{amount}_{user_id}_{int(time.time())}"
    
    pay_url = (f"https://yoomoney.ru/quickpay/confirm.xml?"
               f"receiver={YOOMONEY_WALLET}&quickpay-form=shop&targets=Пополнение баланса&paymentType=AC&sum={amount}&label={label}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"chkdep_{label}")]
    ])
    await callback.message.edit_text(f"Вы пополняете баланс на <b>{amount} ₽</b>.\nПерейдите по ссылке:", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("chkdep_"))
async def check_deposit(callback: CallbackQuery):
    label = callback.data.replace("chkdep_", "")
    parts = label.split("_")
    amount = int(parts[0])
    user_id = int(parts[1])
    
    try:
        history = ym_client.operation_history(label=label)
        for operation in history.operations:
            if operation.status == 'success':
                # Защита: проверяем, не выдали ли уже (для простоты - меняем текст)
                
                # 1. Начисляем юзеру Баланс и 30% Траст-фактора
                trust_gain = amount * 0.30
                cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, trust_factor = trust_factor + ? WHERE user_id=?", 
                               (amount, trust_gain, user_id))
                
                # 2. Начисляем Рефереру (если есть) 10% Баланса и 10% Траст-фактора
                cursor.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
                ref_id = cursor.fetchone()[0]
                if ref_id > 0:
                    ref_bonus = amount * 0.10
                    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, trust_factor = trust_factor + ? WHERE user_id=?", 
                                   (ref_bonus, ref_bonus, ref_id))
                    try:
                        await bot.send_message(ref_id, f"🎉 <b>Реферальный бонус!</b>\nВаш реферал пополнил счет. Вы получили <b>{ref_bonus} ₽</b> и Траст-Фактор!", parse_mode="HTML")
                    except: pass
                
                conn.commit()
                await callback.message.edit_text(f"✅ <b>Успешно!</b>\nНачислено {amount} ₽ и {trust_gain} Траст-Фактора.", parse_mode="HTML")
                return

        await callback.answer("❌ Оплата еще не найдена. Ждите.", show_alert=True)
    except:
        await callback.answer("⚠️ Ошибка проверки ЮMoney.", show_alert=True)


# ================= ВЫВОД СРЕДСТВ =================
@dp.message(F.text == "💸 Вывод Средств")
async def withdraw_request(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT rub_balance, trust_factor FROM users WHERE user_id=?", (user_id,))
    rub, trust = cursor.fetchone()
    
    if rub < MIN_WITHDRAW:
        await message.answer(f"❌ Минимальная сумма вывода: <b>{MIN_WITHDRAW} ₽</b>\nУ вас: {rub:.2f} ₽", parse_mode="HTML")
        return
        
    if trust < MIN_WITHDRAW:
        await message.answer(f"❌ Недостаточно <b>Траст-Фактора (Лимита)</b> для вывода {MIN_WITHDRAW} ₽.\n\nУ вас лимита: {trust:.2f} ⚡️\n\n<i>Приглашайте активных рефералов, чтобы повысить лимит вывода.</i>", parse_mode="HTML")
        return
        
    # Формируем заявку
    req_code = f"WD-{user_id}-{int(time.time())}"
    
    # Списываем баланс и траст
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ?, trust_factor = trust_factor - ? WHERE user_id=?", 
                   (MIN_WITHDRAW, MIN_WITHDRAW, user_id))
    conn.commit()
    
    text = (
        f"✅ <b>Заявка на вывод {MIN_WITHDRAW} ₽ сформирована!</b>\n\n"
        f"Код вашей заявки: <code>{req_code}</code>\n\n"
        f"Сумма и лимит списаны с вашего аккаунта.\n\n"
        f"⚠️ <b>ЧТОБЫ ПОЛУЧИТЬ ДЕНЬГИ:</b>\n"
        f"Напишите администратору {ADMIN_USERNAME} в личные сообщения.\n"
        f"Отправьте ему Код Заявки и номер вашей карты/кошелька."
    )
    await message.answer(text, parse_mode="HTML")
    
    # Уведомляем тебя как админа
    await bot.send_message(ADMIN_ID, f"💰 <b>НОВАЯ ЗАЯВКА НА ВЫВОД!</b>\n\nЮзер: @{message.from_user.username}\nID: {user_id}\nСумма: {MIN_WITHDRAW} ₽\nКод: {req_code}", parse_mode="HTML")


# ================= АДМИН ПАНЕЛЬ =================
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Выдать Рубли", callback_data="admin_give_rub")],
        [InlineKeyboardButton(text="⚡️ Выдать Траст", callback_data="admin_give_trust")]
    ])
    await message.answer("👑 <b>Секретная Админка Проекта</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(*), SUM(rub_balance), SUM(trust_factor) FROM users")
    users_count, total_rub, total_trust = cursor.fetchone()
    text = f"📊 <b>Статистика:</b>\n👥 Игроков: {users_count}\n💰 Рублей на балансах: {total_rub or 0:.2f} ₽\n⚡️ Доступно к выводу игроками: {total_trust or 0:.2f} ₽ (Ваш максимальный риск)"
    await callback.message.edit_text(text, parse_mode="HTML")


async def main():
    print("🚀 Cyber Earn (Play-To-Earn) ЗАПУЩЕН!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
