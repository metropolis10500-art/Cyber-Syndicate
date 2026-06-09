import asyncio
import logging
import sqlite3
import time
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, PreCheckoutQuery, ContentType
)
from aiogram.filters import Command

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8727966393:AAENOC9N7CofxMct5WWuZDtpqyrl__Bwea4"

# Токен, который выдаст BotFather в разделе Payments -> YooKassa
YOOKASSA_TOKEN = "ТВОЙ_PROVIDER_TOKEN_ОТ_БОТФАЗЕРА" 
# =============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect('cyber_syndicate.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   username TEXT, 
                   crypto INTEGER DEFAULT 100,      
                   diamonds INTEGER DEFAULT 0,      
                   botnet_lvl INTEGER DEFAULT 1,    
                   vip_until INTEGER DEFAULT 0,     
                   last_login INTEGER)''')
conn.commit()

# ================= МАТЕМАТИКА =================
def get_upgrade_cost(level):
    return int(100 * (1.15 ** (level - 1)))

def get_income_per_hour(level):
    return int(20 * level * (1.05 ** (level - 1)))

MAX_OFFLINE_HOURS = 24  

# ================= ПАКИ ЮKASSA =================
SHOP_PACKS = {
    "pack_1": {"name": "💎 150 Алмазов", "price": 150, "diamonds": 150},
    "pack_2": {"name": "💎 1000 Алмазов (ХИТ)", "price": 890, "diamonds": 1000},
    "pack_3": {"name": "💎 5000 Алмазов", "price": 2990, "diamonds": 5000},
    "vip_1":  {"name": "👑 VIP Статус (30 дней)", "price": 1490, "diamonds": 0} 
}

CASE_PRICE = 50 

# ================= ФУНКЦИИ =================
def calculate_offline_income(user_id):
    cursor.execute("SELECT last_login, botnet_lvl, vip_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row: return 0
    
    last_login, lvl, vip_until = row
    current_time = int(time.time())
    
    hours_passed = min((current_time - last_login) / 3600.0, MAX_OFFLINE_HOURS)
    multiplier = 2 if current_time < vip_until else 1 
    
    income = int(hours_passed * get_income_per_hour(lvl) * multiplier)
    
    if income > 0:
        cursor.execute("UPDATE users SET crypto = crypto + ?, last_login = ? WHERE user_id=?", 
                       (income, current_time, user_id))
        conn.commit()
    return income

def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💻 Терминал (Профиль)"), KeyboardButton(text="🚀 Апгрейд Сети")],
        [KeyboardButton(text="🎰 Даркнет-Рулетка"), KeyboardButton(text="🏆 Топ Игроков")],
        [KeyboardButton(text="💎 БАНК (Донат ЮKassa)")]
    ], resize_keyboard=True)

# ================= ХЭНДЛЕРЫ =================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, last_login) VALUES (?, ?, ?)",
                   (user_id, username, int(time.time())))
    conn.commit()

    text = (
        "🌐 <b>Добро пожаловать в Cyber Syndicate</b>\n\n"
        "Ты — хакер. Твоя цель — взламывать серверы, майнить крипту и подмять под себя весь даркнет.\n\n"
        "<i>Чем больше сеть, тем больше денег. Улучшай ботнет и вырывайся в Топ-1.</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

# --- 1. ПРОФИЛЬ ---
@dp.message(F.text == "💻 Терминал (Профиль)")
async def show_profile(message: Message):
    user_id = message.from_user.id
    income = calculate_offline_income(user_id)
    
    cursor.execute("SELECT crypto, diamonds, botnet_lvl, vip_until FROM users WHERE user_id=?", (user_id,))
    crypto, diamonds, lvl, vip_until = cursor.fetchone()
    
    is_vip = int(time.time()) < vip_until
    vip_status = "🟢 АКТИВЕН (Доход x2)" if is_vip else "🔴 НЕТ"
    hourly_rate = get_income_per_hour(lvl) * (2 if is_vip else 1)

    text = (
        f"👤 <b>Хакер:</b> @{message.from_user.username or 'Anon'}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💠 Крипта: <b>{crypto:,}</b>\n"
        f"💎 Алмазы: <b>{diamonds:,}</b>\n"
        f"👑 VIP: <b>{vip_status}</b>\n\n"
        f"🕸 Уровень Ботнета: <b>{lvl} LVL</b>\n"
        f"📈 Майнинг: <b>{hourly_rate:,} крипты/час</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
    )
    if income > 0:
        text += f"<i>✅ Оффлайн доход: +{income:,} 💠</i>"

    await message.answer(text, parse_mode="HTML")

# --- 2. АПГРЕЙД ---
@dp.message(F.text == "🚀 Апгрейд Сети")
async def upgrade_menu(message: Message):
    user_id = message.from_user.id
    calculate_offline_income(user_id)
    
    cursor.execute("SELECT crypto, botnet_lvl FROM users WHERE user_id=?", (user_id,))
    crypto, lvl = cursor.fetchone()
    
    cost = get_upgrade_cost(lvl)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔼 Прокачать до {lvl + 1} LVL ({cost:,} 💠)", callback_data="upgrade_botnet")],
        [InlineKeyboardButton(text=f"💎 Купить Крипту за Алмазы", callback_data="exchange_diamonds")]
    ])
    await message.answer(f"🚀 <b>Улучшение Ботнета</b>\n\nТекущий уровень: {lvl}\n<i>Качайся бесконечно!</i>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "upgrade_botnet")
async def process_upgrade(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT crypto, botnet_lvl FROM users WHERE user_id=?", (user_id,))
    crypto, lvl = cursor.fetchone()
    cost = get_upgrade_cost(lvl)
    
    if crypto < cost:
        await callback.answer("❌ Не хватает Крипты!", show_alert=True)
        return
        
    cursor.execute("UPDATE users SET crypto = crypto - ?, botnet_lvl = botnet_lvl + 1 WHERE user_id=?", (cost, user_id))
    conn.commit()
    await callback.message.edit_text(f"✅ <b>Успех!</b> Ботнет улучшен до {lvl + 1} уровня!", parse_mode="HTML")

@dp.callback_query(F.data == "exchange_diamonds")
async def exchange_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 10 Алмазов ➡️ 50,000 💠", callback_data="swap_10")]])
    await callback.message.edit_text("🔄 <b>Теневой обменник</b>\nКонвертируй донат в игровую крипту!", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "swap_10")
async def do_swap(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT diamonds FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone()[0] < 10:
        await callback.answer("❌ Мало Алмазов! Иди в БАНК.", show_alert=True)
        return
    cursor.execute("UPDATE users SET diamonds = diamonds - 10, crypto = crypto + 50000 WHERE user_id=?", (user_id,))
    conn.commit()
    await callback.message.edit_text("✅ Обмен совершен! +50,000 💠")

# --- 3. РУЛЕТКА ---
@dp.message(F.text == "🎰 Даркнет-Рулетка")
async def roulette_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🎲 Крутить ({CASE_PRICE} 💎)", callback_data="spin_roulette")]])
    await message.answer(f"🎰 <b>Даркнет-Рулетка</b>\nШанс выиграть VIP или +5 уровней!\n<i>Цена: {CASE_PRICE} 💎</i>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "spin_roulette")
async def spin_roulette(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT diamonds, botnet_lvl FROM users WHERE user_id=?", (user_id,))
    diamonds, lvl = cursor.fetchone()
    
    if diamonds < CASE_PRICE:
        await callback.answer("❌ Не хватает Алмазов!", show_alert=True)
        return
        
    cursor.execute("UPDATE users SET diamonds = diamonds - ? WHERE user_id=?", (CASE_PRICE, user_id))
    roll = random.randint(1, 100)
    
    if roll <= 75:
        prize = get_upgrade_cost(lvl) * 2
        cursor.execute("UPDATE users SET crypto = crypto + ? WHERE user_id=?", (prize, user_id))
        msg = f"💸 Выпало: <b>+{prize:,} 💠</b>"
    elif roll <= 95:
        bonus_time = 3 * 24 * 3600
        current_time = int(time.time())
        cursor.execute("UPDATE users SET vip_until = MAX(vip_until, ?) + ? WHERE user_id=?", (current_time, bonus_time, user_id))
        msg = f"👑 Выпал <b>VIP на 3 дня</b>!"
    else:
        cursor.execute("UPDATE users SET botnet_lvl = botnet_lvl + 5 WHERE user_id=?", (user_id,))
        msg = f"🎰 <b>ДЖЕКПОТ!!!</b> Уровень повышен на <b>+5 LVL</b>!!!"
        
    conn.commit()
    await callback.message.edit_text(f"🎰 Результат...\n\n{msg}", parse_mode="HTML")

# --- 4. ТОП ---
@dp.message(F.text == "🏆 Топ Игроков")
async def leaderboard(message: Message):
    cursor.execute("SELECT username, botnet_lvl FROM users ORDER BY botnet_lvl DESC LIMIT 5")
    leaders = cursor.fetchall()
    text = "🏆 <b>МИРОВОЙ ЗАЛ СЛАВЫ</b> 🏆\n\n"
    for i, leader in enumerate(leaders):
        text += f"{i+1}. {leader[0]} — <b>{leader[1]} LVL</b>\n"
    await message.answer(text, parse_mode="HTML")

# ================= ЮKASSA (НАТИВНАЯ ИНТЕГРАЦИЯ) =================

@dp.message(F.text == "💎 БАНК (Донат ЮKassa)")
async def donate_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{SHOP_PACKS['pack_1']['name']} - {SHOP_PACKS['pack_1']['price']}₽", callback_data="buy_pack_1")],
        [InlineKeyboardButton(text=f"{SHOP_PACKS['pack_2']['name']} - {SHOP_PACKS['pack_2']['price']}₽", callback_data="buy_pack_2")],
        [InlineKeyboardButton(text=f"{SHOP_PACKS['pack_3']['name']} - {SHOP_PACKS['pack_3']['price']}₽", callback_data="buy_pack_3")],
        [InlineKeyboardButton(text=f"{SHOP_PACKS['vip_1']['name']} - {SHOP_PACKS['vip_1']['price']}₽", callback_data="buy_vip_1")]
    ])
    await message.answer("💎 <b>Официальный Банк (Нативные платежи)</b>\nВыберите товар:", parse_mode="HTML", reply_markup=kb)

# Создаем счет (Invoice) внутри Telegram
@dp.callback_query(F.data.startswith("buy_"))
async def send_invoice(callback: CallbackQuery):
    pack_id = callback.data.replace("buy_", "")
    pack = SHOP_PACKS[pack_id]
    
    # В Telegram цены указываются в копейках, поэтому цена в рублях умножается на 100
    prices = [LabeledPrice(label=pack["name"], amount=pack["price"] * 100)]
    
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=pack["name"],
        description="Покупка цифрового товара для игры Cyber Syndicate",
        payload=pack_id,                # Скрытая метка (чтобы понять, что купили)
        provider_token=YOOKASSA_TOKEN,  # Тот самый токен из BotFather
        currency="RUB",
        prices=prices,
        start_parameter="cyber-payment"
    )
    await callback.answer()

# Шаг проверки от Telegram перед списанием денег
@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Шаг УСПЕШНОЙ ОПЛАТЫ (Выдача товара)
@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    pack_id = message.successful_payment.invoice_payload
    pack = SHOP_PACKS[pack_id]
    user_id = message.from_user.id
    
    if pack_id.startswith("vip"):
        bonus_time = 30 * 24 * 3600
        current_time = int(time.time())
        cursor.execute("UPDATE users SET vip_until = MAX(vip_until, ?) + ? WHERE user_id=?", 
                       (current_time, bonus_time, user_id))
        msg = "👑 <b>Оплата прошла! VIP на 30 дней успешно активирован!</b>"
    else:
        gems = pack["diamonds"]
        cursor.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id=?", (gems, user_id))
        msg = f"💎 <b>Оплата прошла!</b> Начислено {gems} Алмазов. Спасибо за поддержку!"

    conn.commit()
    await message.answer(msg, parse_mode="HTML")


# ================= ЗАПУСК =================
async def main():
    print("🚀 Cyber Syndicate (Нативная ЮKassa) ЗАПУЩЕН!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
