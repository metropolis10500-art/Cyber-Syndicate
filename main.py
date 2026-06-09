import asyncio
import logging
import sqlite3
import time
import random
import uuid
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from yookassa import Configuration, Payment

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8727966393:AAENOC9N7CofxMct5WWuZDtpqyrl__Bwea4"
ADMIN_ID = 5494544187  # Твой ID

Configuration.account_id = "ТВОЙ_SHOP_ID"     
Configuration.secret_key = "ТВОЙ_SECRET_KEY"  
# =============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect('cyber_syndicate.db')
cursor = conn.cursor()

# База игроков (Добавлены стрики и время бонуса)
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   username TEXT, 
                   crypto INTEGER DEFAULT 100,      
                   diamonds INTEGER DEFAULT 0,      
                   botnet_lvl INTEGER DEFAULT 1,    
                   vip_until INTEGER DEFAULT 0,     
                   last_login INTEGER,
                   daily_streak INTEGER DEFAULT 0,
                   last_daily INTEGER DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS invoices
                  (payment_id TEXT PRIMARY KEY, user_id INTEGER, pack_id TEXT)''')

# База промокодов
cursor.execute('''CREATE TABLE IF NOT EXISTS promocodes
                  (code TEXT PRIMARY KEY, reward_type TEXT, reward_amount INTEGER, activations_left INTEGER)''')
# База использованных промокодов (чтобы 1 игрок не ввел дважды)
cursor.execute('''CREATE TABLE IF NOT EXISTS used_promos
                  (user_id INTEGER, code TEXT, UNIQUE(user_id, code))''')
conn.commit()

# ================= МАТЕМАТИКА =================
def get_upgrade_cost(level): return int(100 * (1.15 ** (level - 1)))
def get_income_per_hour(level): return int(20 * level * (1.05 ** (level - 1)))
MAX_OFFLINE_HOURS = 24  
CASE_PRICE = 50 

SHOP_PACKS = {
    "pack_1": {"name": "💎 150 Алмазов", "price": 150.00, "diamonds": 150},
    "pack_2": {"name": "💎 1000 Алмазов (ХИТ)", "price": 890.00, "diamonds": 1000},
    "pack_3": {"name": "💎 5000 Алмазов (МАГНАТ)", "price": 2990.00, "diamonds": 5000},
    "vip_1":  {"name": "👑 VIP Статус (30 дней)", "price": 1490.00, "diamonds": 0} 
}

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_promo = State()

# ================= КЛАВИАТУРЫ =================
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💻 Терминал"), KeyboardButton(text="🚀 Апгрейд Сети")],
        [KeyboardButton(text="🎁 Ежедневный Бонус"), KeyboardButton(text="🎰 Рулетка")],
        [KeyboardButton(text="🏆 Зал Славы"), KeyboardButton(text="💎 БАНК (Донат)")]
    ], resize_keyboard=True)

# ================= ОФФЛАЙН ДОХОД И СЛУЧАЙНЫЕ СОБЫТИЯ =================
def calculate_offline_income_and_events(user_id):
    cursor.execute("SELECT last_login, botnet_lvl, vip_until, crypto FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row: return 0, ""
    
    last_login, lvl, vip_until, current_crypto = row
    current_time = int(time.time())
    
    hours_passed = min((current_time - last_login) / 3600.0, MAX_OFFLINE_HOURS)
    if hours_passed < 0.1: return 0, "" # Слишком часто заходит
    
    multiplier = 2 if current_time < vip_until else 1 
    income = int(hours_passed * get_income_per_hour(lvl) * multiplier)
    
    event_msg = ""
    # 20% шанс на случайное событие, если человека не было хотя бы 1 час
    if hours_passed >= 1 and random.randint(1, 100) <= 20:
        event_type = random.choice(["good_crypto", "good_gems", "bad_ddos"])
        
        if event_type == "good_crypto":
            bonus = int(income * 0.5)
            income += bonus
            event_msg = f"\n\n🍀 <b>УДАЧА:</b> Вы нашли уязвимость в банке! Дополнительно добыто +{bonus:,} 💠!"
        elif event_type == "good_gems":
            cursor.execute("UPDATE users SET diamonds = diamonds + 15 WHERE user_id=?", (user_id,))
            event_msg = f"\n\n🍀 <b>ДЖЕКПОТ:</b> В одной из взломанных баз лежал тайник. Вы получили +15 💎!"
        elif event_type == "bad_ddos" and current_crypto > 0:
            loss = int(current_crypto * 0.05) # Потеря 5% баланса
            cursor.execute("UPDATE users SET crypto = crypto - ? WHERE user_id=?", (loss, user_id))
            event_msg = f"\n\n⚠️ <b>ТРЕВОГА:</b> Конкуренты устроили DDoS-атаку! Вы потеряли {loss:,} 💠 баланса."

    if income > 0:
        cursor.execute("UPDATE users SET crypto = crypto + ?, last_login = ? WHERE user_id=?", 
                       (income, current_time, user_id))
        conn.commit()
    return income, event_msg

# ================= ХЭНДЛЕРЫ ИГРОКА =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"Anon_{user_id}"

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, last_login) VALUES (?, ?, ?)",
                   (user_id, username, int(time.time())))
    conn.commit()
    await message.answer("🌐 <b>Добро пожаловать в Cyber Syndicate.</b>\nСтрой ботнет, майни крипту, стань номером один.", parse_mode="HTML", reply_markup=get_main_keyboard())

# --- ПРОФИЛЬ И СОБЫТИЯ ---
@dp.message(F.text == "💻 Терминал")
async def show_profile(message: Message):
    user_id = message.from_user.id
    income, event_msg = calculate_offline_income_and_events(user_id)
    
    cursor.execute("SELECT crypto, diamonds, botnet_lvl, vip_until FROM users WHERE user_id=?", (user_id,))
    crypto, diamonds, lvl, vip_until = cursor.fetchone()
    
    is_vip = int(time.time()) < vip_until
    vip_status = "🟢 АКТИВЕН (x2)" if is_vip else "🔴 НЕТ"

    text = (
        f"👤 <b>Оператор:</b> @{message.from_user.username or 'Anon'}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💠 Крипта: <b>{crypto:,}</b>\n"
        f"💎 Алмазы: <b>{diamonds:,}</b>\n"
        f"👑 VIP Статус: <b>{vip_status}</b>\n\n"
        f"🕸 Уровень Ботнета: <b>{lvl} LVL</b>\n"
        f"📈 Майнинг: <b>{get_income_per_hour(lvl) * (2 if is_vip else 1):,} 💠/час</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖"
    )
    if income > 0: text += f"\n<i>✅ Оффлайн добыча: +{income:,} 💠</i>"
    if event_msg: text += event_msg

    await message.answer(text, parse_mode="HTML")

# --- ЕЖЕДНЕВНЫЙ БОНУС (RETENTION) ---
@dp.message(F.text == "🎁 Ежедневный Бонус")
async def daily_bonus(message: Message):
    user_id = message.from_user.id
    current_time = int(time.time())
    
    cursor.execute("SELECT last_daily, daily_streak, botnet_lvl FROM users WHERE user_id=?", (user_id,))
    last_daily, streak, lvl = cursor.fetchone()
    
    hours_passed = (current_time - last_daily) / 3600.0
    
    if hours_passed < 24:
        wait_hours = 24 - hours_passed
        await message.answer(f"⏳ Вы уже забирали бонус! Следующий будет доступен через <b>{int(wait_hours)} ч.</b>", parse_mode="HTML")
        return
        
    # Если прошло больше 48 часов, стрик сгорает
    if hours_passed > 48:
        streak = 1
        msg_streak = "⚠️ Вы пропустили день! Ваш стрик сброшен до 1."
    else:
        streak += 1
        msg_streak = f"🔥 Стрик поддерживается! День: {streak}."

    # Награды в зависимости от дня
    if streak % 7 == 0: # Каждый 7-й день - Супер приз (Алмазы)
        reward_gems = 50
        cursor.execute("UPDATE users SET diamonds = diamonds + ?, daily_streak = ?, last_daily = ? WHERE user_id=?", 
                       (reward_gems, streak, current_time, user_id))
        reward_text = f"💎 <b>МЕГА-БОНУС 7 ДНЯ:</b> +{reward_gems} Алмазов!"
    else:
        reward_crypto = get_income_per_hour(lvl) * 5 # Крипта, равная 5 часам дохода
        cursor.execute("UPDATE users SET crypto = crypto + ?, daily_streak = ?, last_daily = ? WHERE user_id=?", 
                       (reward_crypto, streak, current_time, user_id))
        reward_text = f"💠 <b>Награда:</b> +{reward_crypto:,} Крипты!"

    conn.commit()
    await message.answer(f"🎁 <b>Ежедневная поставка</b>\n\n{msg_streak}\n{reward_text}\n\n<i>Заходите завтра, чтобы награда росла!</i>", parse_mode="HTML")

# --- ВВОД ПРОМОКОДА ---
@dp.message(Command("promo"))
async def enter_promo(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Использование: `/promo ВАШ_КОД`", parse_mode="Markdown")
        return
    
    code = args[1].upper()
    user_id = message.from_user.id
    
    # Проверка, не вводил ли юзер этот код
    cursor.execute("SELECT * FROM used_promos WHERE user_id=? AND code=?", (user_id, code))
    if cursor.fetchone():
        await message.answer("❌ Вы уже активировали этот промокод!")
        return
        
    cursor.execute("SELECT reward_type, reward_amount, activations_left FROM promocodes WHERE code=?", (code,))
    promo = cursor.fetchone()
    
    if not promo:
        await message.answer("❌ Неверный или несуществующий код.")
        return
        
    r_type, r_amount, left = promo
    if left <= 0:
        await message.answer("❌ Количество активаций этого кода исчерпано.")
        return
        
    # Выдача награды
    if r_type == "diamonds":
        cursor.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id=?", (r_amount, user_id))
        msg = f"💎 Вы получили <b>{r_amount} Алмазов</b>!"
    else:
        cursor.execute("UPDATE users SET crypto = crypto + ? WHERE user_id=?", (r_amount, user_id))
        msg = f"💠 Вы получили <b>{r_amount:,} Крипты</b>!"
        
    # Уменьшаем кол-во активаций и записываем юзера
    cursor.execute("UPDATE promocodes SET activations_left = activations_left - 1 WHERE code=?", (code,))
    cursor.execute("INSERT INTO used_promos (user_id, code) VALUES (?, ?)", (user_id, code))
    conn.commit()
    
    await message.answer(f"✅ <b>Промокод активирован!</b>\n{msg}", parse_mode="HTML")

# --- ОСТАЛЬНЫЕ МЕНЮ (КРАТКО) ---
@dp.message(F.text == "🚀 Апгрейд Сети")
async def upgrade_menu(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT botnet_lvl FROM users WHERE user_id=?", (user_id,))
    lvl = cursor.fetchone()[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔼 Прокачать ({get_upgrade_cost(lvl):,} 💠)", callback_data="upgrade_botnet")],
        [InlineKeyboardButton(text=f"💎 Купить Крипту", callback_data="exchange_diamonds")]
    ])
    await message.answer(f"🚀 Текущий уровень: {lvl}", reply_markup=kb)

@dp.callback_query(F.data == "upgrade_botnet")
async def process_upgrade(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT crypto, botnet_lvl FROM users WHERE user_id=?", (user_id,))
    crypto, lvl = cursor.fetchone()
    cost = get_upgrade_cost(lvl)
    if crypto < cost: return await callback.answer("❌ Мало Крипты!", show_alert=True)
    cursor.execute("UPDATE users SET crypto = crypto - ?, botnet_lvl = botnet_lvl + 1 WHERE user_id=?", (cost, user_id))
    conn.commit()
    await callback.message.edit_text(f"✅ Ботнет улучшен до {lvl + 1} уровня!")

@dp.message(F.text == "🎰 Рулетка")
async def roulette_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🎲 Взломать ({CASE_PRICE} 💎)", callback_data="spin_roulette")]])
    await message.answer(f"🎰 <b>Даркнет-Рулетка</b>\nШанс на VIP или +5 LVL!\n<i>Цена: {CASE_PRICE} 💎</i>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "spin_roulette")
async def spin_roulette(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT diamonds, botnet_lvl FROM users WHERE user_id=?", (user_id,))
    diamonds, lvl = cursor.fetchone()
    if diamonds < CASE_PRICE: return await callback.answer("❌ Мало Алмазов!", show_alert=True)
    cursor.execute("UPDATE users SET diamonds = diamonds - ? WHERE user_id=?", (CASE_PRICE, user_id))
    roll = random.randint(1, 100)
    if roll <= 75:
        prize = get_upgrade_cost(lvl) * 2
        cursor.execute("UPDATE users SET crypto = crypto + ? WHERE user_id=?", (prize, user_id))
        msg = f"💸 Выпало: <b>+{prize:,} 💠</b>"
    elif roll <= 95:
        cursor.execute("UPDATE users SET vip_until = MAX(vip_until, ?) + ? WHERE user_id=?", (int(time.time()), 3*24*3600, user_id))
        msg = f"👑 Выпал <b>VIP на 3 дня</b>!"
    else:
        cursor.execute("UPDATE users SET botnet_lvl = botnet_lvl + 5 WHERE user_id=?", (user_id,))
        msg = f"🎰 <b>ДЖЕКПОТ!!! +5 LVL</b>"
    conn.commit()
    await callback.message.edit_text(f"🎰 Результат:\n\n{msg}", parse_mode="HTML")

@dp.message(F.text == "🏆 Зал Славы")
async def leaderboard(message: Message):
    cursor.execute("SELECT username, botnet_lvl FROM users ORDER BY botnet_lvl DESC LIMIT 5")
    leaders = cursor.fetchall()
    text = "🏆 <b>ВЫСШИЙ СИНДИКАТ</b> 🏆\n\n"
    for i, l in enumerate(leaders): text += f"{i+1}. {l[0]} — <b>{l[1]} LVL</b>\n"
    await message.answer(text, parse_mode="HTML")

# ================= ЮKASSA =================
@dp.message(F.text == "💎 БАНК (Донат)")
async def donate_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} - {p['price']}₽", callback_data=f"buy_{k}")] for k, p in SHOP_PACKS.items()
    ])
    await message.answer("💎 <b>Официальный Банк</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_"))
async def create_yookassa_payment(callback: CallbackQuery):
    pack_id = callback.data.replace("buy_", "")
    pack = SHOP_PACKS[pack_id]
    loading_msg = await callback.message.edit_text("⏳ <i>Подключение к банку...</i>", parse_mode="HTML")
    try:
        payment = Payment.create({
            "amount": {"value": str(pack["price"]), "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": "https://t.me/"},
            "capture": True, "description": f"Покупка {pack['name']}"
        }, str(uuid.uuid4()))
        cursor.execute("INSERT OR REPLACE INTO invoices VALUES (?, ?, ?)", (payment.id, callback.from_user.id, pack_id))
        conn.commit()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {pack['price']} ₽", url=payment.confirmation.confirmation_url)],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"chk_{payment.id}")]
        ])
        await loading_msg.edit_text(f"📦 <b>{pack['name']}</b>\n💰 <b>{pack['price']} ₽</b>", parse_mode="HTML", reply_markup=kb)
    except: await loading_msg.edit_text("❌ Ошибка соединения.")

@dp.callback_query(F.data.startswith("chk_"))
async def check_payment(callback: CallbackQuery):
    payment_id = callback.data.replace("chk_", "")
    try:
        payment = Payment.find_one(payment_id)
        if payment.status == 'succeeded':
            cursor.execute("SELECT user_id, pack_id FROM invoices WHERE payment_id=?", (payment_id,))
            row = cursor.fetchone()
            if not row: return await callback.answer("Уже выдано.", show_alert=True)
            u_id, p_id = row
            if p_id.startswith("vip"):
                cursor.execute("UPDATE users SET vip_until = MAX(vip_until, ?) + ? WHERE user_id=?", (int(time.time()), 30*24*3600, u_id))
                msg = "👑 <b>VIP на 30 дней активирован!</b>"
            else:
                cursor.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id=?", (SHOP_PACKS[p_id]["diamonds"], u_id))
                msg = f"💎 <b>Начислено {SHOP_PACKS[p_id]['diamonds']} Алмазов!</b>"
            cursor.execute("DELETE FROM invoices WHERE payment_id=?", (payment_id,))
            conn.commit()
            await callback.message.edit_text(msg, parse_mode="HTML")
        elif payment.status == 'canceled': await callback.answer("❌ Отменено.", show_alert=True)
        else: await callback.answer("⏳ В обработке. Ждите.", show_alert=True)
    except: await callback.answer("⚠️ Ошибка.", show_alert=True)

# ================= АДМИНКА (Добавлено создание промокодов) =================
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎟 Создать Промокод", callback_data="admin_promo")]
    ])
    await message.answer("👑 <b>Админка</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "admin_promo")
async def create_promo_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("Формат создания промокода:\n<code>КОД ТИП(diamonds/crypto) СУММА КОЛ-ВО_ИСПОЛЬЗОВАНИЙ</code>\n\nПример: <code>GIFT2024 diamonds 100 50</code>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_promo)

@dp.message(AdminStates.waiting_for_promo)
async def create_promo_finish(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        code, r_type, r_amount, acts = parts[0].upper(), parts[1], int(parts[2]), int(parts[3])
        cursor.execute("INSERT INTO promocodes VALUES (?, ?, ?, ?)", (code, r_type, r_amount, acts))
        conn.commit()
        await message.answer(f"✅ Промокод <b>{code}</b> создан!\nЛюди должны ввести: <code>/promo {code}</code>", parse_mode="HTML")
    except: await message.answer("❌ Ошибка формата.")
    await state.clear()

async def main():
    print("🚀 Cyber Syndicate (ULTIMATE) ЗАПУЩЕН!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
