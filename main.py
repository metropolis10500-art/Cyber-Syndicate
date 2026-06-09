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

# Официальная библиотека ЮKassa
from yookassa import Configuration, Payment

# ================= НАСТРОЙКИ (ВВЕДИ СВОИ ДАННЫЕ) =================
BOT_TOKEN = "8727966393:AAENOC9N7CofxMct5WWuZDtpqyrl__Bwea4"
ADMIN_ID = 5494544187  # Твой Telegram ID (для админки)

# Ключи из личного кабинета ЮKassa
Configuration.account_id = "ТВОЙ_SHOP_ID"     # Например: 123456
Configuration.secret_key = "ТВОЙ_SECRET_KEY"  # Секретный ключ API
# =================================================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect('cyber_syndicate.db')
cursor = conn.cursor()

# Таблица игроков
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   username TEXT, 
                   crypto INTEGER DEFAULT 100,      
                   diamonds INTEGER DEFAULT 0,      
                   botnet_lvl INTEGER DEFAULT 1,    
                   vip_until INTEGER DEFAULT 0,     
                   last_login INTEGER)''')

# Таблица для отслеживания платежей ЮKassa
cursor.execute('''CREATE TABLE IF NOT EXISTS invoices
                  (payment_id TEXT PRIMARY KEY,
                   user_id INTEGER,
                   pack_id TEXT)''')
conn.commit()

# ================= МАТЕМАТИКА ИГРЫ =================
def get_upgrade_cost(level):
    return int(100 * (1.15 ** (level - 1)))

def get_income_per_hour(level):
    return int(20 * level * (1.05 ** (level - 1)))

MAX_OFFLINE_HOURS = 24  

# ================= ПАКИ ДОНАТА =================
SHOP_PACKS = {
    "pack_1": {"name": "💎 150 Алмазов", "price": 150.00, "diamonds": 150},
    "pack_2": {"name": "💎 1000 Алмазов (ХИТ)", "price": 890.00, "diamonds": 1000},
    "pack_3": {"name": "💎 5000 Алмазов (МАГНАТ)", "price": 2990.00, "diamonds": 5000},
    "vip_1":  {"name": "👑 VIP Статус (30 дней)", "price": 1490.00, "diamonds": 0} 
}

CASE_PRICE = 50 

class AdminStates(StatesGroup):
    waiting_for_broadcast_text = State()
    waiting_for_give_diamonds = State()

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
        [KeyboardButton(text="💻 Терминал"), KeyboardButton(text="🚀 Апгрейд Сети")],
        [KeyboardButton(text="🎰 Рулетка"), KeyboardButton(text="🏆 Зал Славы")],
        [KeyboardButton(text="ℹ️ База Знаний"), KeyboardButton(text="💎 БАНК (Донат)")]
    ], resize_keyboard=True)

# ================= ХЭНДЛЕРЫ =================

# --- АТМОСФЕРНОЕ ПРИВЕТСТВИЕ ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"Anon_{user_id}"

    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, last_login) VALUES (?, ?, ?)",
                   (user_id, username, int(time.time())))
    conn.commit()

    await message.answer("<i>[SYSTEM INITIALIZING...]</i>\n<i>[BYPASSING FIREWALLS... OK]</i>", parse_mode="HTML")
    await asyncio.sleep(1)
    
    text = (
        "🌐 <b>Подключение установлено. Добро пожаловать, Оператор.</b>\n\n"
        "Вы попали в <b>Cyber Syndicate</b>. Здесь нет законов, есть только вычислительная мощность. "
        "Вы начинаете свой путь в темном гараже с одним старым сервером.\n\n"
        "Ваша цель — взламывать корпорации, майнить Крипту (💠) и расширять свой Ботнет.\n\n"
        "👇 <b>Используйте Терминал ниже для управления сетью.</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

# --- БАЗА ЗНАНИЙ (ОБУЧЕНИЕ) ---
@dp.message(F.text == "ℹ️ База Знаний")
async def info_menu(message: Message):
    text = (
        "📖 <b>СЕКРЕТНЫЕ АРХИВЫ СИНДИКАТА</b>\n\n"
        "💠 <b>Что такое Крипта?</b>\n"
        "Основная валюта. За неё вы прокачиваете Ботнет. Чем выше уровень Ботнета, тем больше Крипты он приносит каждый час.\n\n"
        "💎 <b>Что такое Алмазы?</b>\n"
        "Премиум-ресурс. Их можно обменять на миллионы Крипты, либо тратить в Рулетке для мгновенной прокачки.\n\n"
        "💤 <b>Нужно ли держать телефон включенным?</b>\n"
        "Нет! Ботнет работает автономно <b>до 24 часов</b>. Просто заходите раз в сутки, чтобы собрать намайненное.\n\n"
        "👑 <b>Что дает VIP-статус?</b>\n"
        "VIP удваивает (x2) всю добычу вашей сети. Это самый быстрый путь на 1-е место в Топе!"
    )
    await message.answer(text, parse_mode="HTML")

# --- 1. ПРОФИЛЬ ---
@dp.message(F.text == "💻 Терминал")
async def show_profile(message: Message):
    user_id = message.from_user.id
    income = calculate_offline_income(user_id)
    
    cursor.execute("SELECT crypto, diamonds, botnet_lvl, vip_until FROM users WHERE user_id=?", (user_id,))
    crypto, diamonds, lvl, vip_until = cursor.fetchone()
    
    is_vip = int(time.time()) < vip_until
    vip_status = "🟢 АКТИВЕН (Доход x2)" if is_vip else "🔴 НЕТ"
    hourly_rate = get_income_per_hour(lvl) * (2 if is_vip else 1)

    text = (
        f"👤 <b>Оператор:</b> @{message.from_user.username or 'Anon'}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💠 Крипта: <b>{crypto:,}</b>\n"
        f"💎 Алмазы: <b>{diamonds:,}</b>\n"
        f"👑 VIP Статус: <b>{vip_status}</b>\n\n"
        f"🕸 Уровень Ботнета: <b>{lvl} LVL</b>\n"
        f"📈 Скорость майнинга: <b>{hourly_rate:,} 💠/час</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
    )
    if income > 0:
        text += f"<i>✅ Пока вас не было, сервера добыли: +{income:,} 💠</i>"

    await message.answer(text, parse_mode="HTML")

# --- 2. АПГРЕЙД ---
@dp.message(F.text == "🚀 Апгрейд Сети")
async def upgrade_menu(message: Message):
    user_id = message.from_user.id
    calculate_offline_income(user_id)
    
    cursor.execute("SELECT crypto, botnet_lvl FROM users WHERE user_id=?", (user_id,))
    crypto, lvl = cursor.fetchone()
    cost = get_upgrade_cost(lvl)
    next_income = get_income_per_hour(lvl + 1)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔼 Прокачать до {lvl + 1} LVL ({cost:,} 💠)", callback_data="upgrade_botnet")],
        [InlineKeyboardButton(text=f"💎 Купить Крипту за Алмазы", callback_data="exchange_diamonds")]
    ])
    await message.answer(
        f"🚀 <b>Расширение Сети</b>\n\n"
        f"Текущий уровень: {lvl}\n"
        f"Доход после апгрейда: {next_income:,} 💠/час\n\n"
        f"<i>Уровень не имеет ограничений.</i>", 
        parse_mode="HTML", reply_markup=kb
    )

@dp.callback_query(F.data == "upgrade_botnet")
async def process_upgrade(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT crypto, botnet_lvl FROM users WHERE user_id=?", (user_id,))
    crypto, lvl = cursor.fetchone()
    cost = get_upgrade_cost(lvl)
    
    if crypto < cost:
        await callback.answer("❌ Не хватает Крипты! Зайдите позже или купите Алмазы.", show_alert=True)
        return
        
    cursor.execute("UPDATE users SET crypto = crypto - ?, botnet_lvl = botnet_lvl + 1 WHERE user_id=?", (cost, user_id))
    conn.commit()
    await callback.message.edit_text(f"✅ <b>Успех!</b> Мощность ботнета увеличена до {lvl + 1} уровня!", parse_mode="HTML")

@dp.callback_query(F.data == "exchange_diamonds")
async def exchange_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 10 Алмазов ➡️ 50,000 💠", callback_data="swap_10")]])
    await callback.message.edit_text("🔄 <b>Теневой обменник</b>\nПозволяет мгновенно получить Крипту за Алмазы.", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "swap_10")
async def do_swap(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT diamonds FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone()[0] < 10:
        await callback.answer("❌ Мало Алмазов! Перейдите в раздел БАНК.", show_alert=True)
        return
    cursor.execute("UPDATE users SET diamonds = diamonds - 10, crypto = crypto + 50000 WHERE user_id=?", (user_id,))
    conn.commit()
    await callback.message.edit_text("✅ Обмен совершен! На баланс добавлено +50,000 💠")

# --- 3. РУЛЕТКА ---
@dp.message(F.text == "🎰 Рулетка")
async def roulette_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🎲 Взломать систему ({CASE_PRICE} 💎)", callback_data="spin_roulette")]])
    await message.answer(f"🎰 <b>Даркнет-Рулетка</b>\nШанс выиграть VIP статус или мгновенно получить +5 уровней!\n<i>Цена взлома: {CASE_PRICE} 💎</i>", parse_mode="HTML", reply_markup=kb)

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
        msg = f"💸 Системы безопасности обойдены: <b>+{prize:,} 💠</b>"
    elif roll <= 95:
        bonus_time = 3 * 24 * 3600
        current_time = int(time.time())
        cursor.execute("UPDATE users SET vip_until = MAX(vip_until, ?) + ? WHERE user_id=?", (current_time, bonus_time, user_id))
        msg = f"👑 Выдан админ-доступ: <b>VIP на 3 дня</b>!"
    else:
        cursor.execute("UPDATE users SET botnet_lvl = botnet_lvl + 5 WHERE user_id=?", (user_id,))
        msg = f"🎰 <b>ДЖЕКПОТ!!!</b> Критический взлом! Уровень ботнета: <b>+5 LVL</b>!!!"
        
    conn.commit()
    await callback.message.edit_text(f"🎰 <i>Подбор пароля...</i>\n\n{msg}", parse_mode="HTML")

# --- 4. ТОП ИГРОКОВ ---
@dp.message(F.text == "🏆 Зал Славы")
async def leaderboard(message: Message):
    cursor.execute("SELECT username, botnet_lvl FROM users ORDER BY botnet_lvl DESC LIMIT 5")
    leaders = cursor.fetchall()
    text = "🏆 <b>ВЫСШИЙ СИНДИКАТ</b> 🏆\n<i>Самые могущественные хакеры сети:</i>\n\n"
    for i, leader in enumerate(leaders):
        text += f"{i+1}. {leader[0]} — <b>{leader[1]} LVL</b>\n"
    await message.answer(text, parse_mode="HTML")


# ================= ОФИЦИАЛЬНАЯ ЮKASSA (API) =================

@dp.message(F.text == "💎 БАНК (Донат)")
async def donate_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{SHOP_PACKS['pack_1']['name']} - {SHOP_PACKS['pack_1']['price']}₽", callback_data="buy_pack_1")],
        [InlineKeyboardButton(text=f"{SHOP_PACKS['pack_2']['name']} - {SHOP_PACKS['pack_2']['price']}₽", callback_data="buy_pack_2")],
        [InlineKeyboardButton(text=f"{SHOP_PACKS['pack_3']['name']} - {SHOP_PACKS['pack_3']['price']}₽", callback_data="buy_pack_3")],
        [InlineKeyboardButton(text=f"{SHOP_PACKS['vip_1']['name']} - {SHOP_PACKS['vip_1']['price']}₽", callback_data="buy_vip_1")]
    ])
    await message.answer("💎 <b>Официальный Банк Синдиката</b>\nПриобретайте премиум-ресурсы для доминирования на серверах.", parse_mode="HTML", reply_markup=kb)

# Создание платежа в ЮKassa
@dp.callback_query(F.data.startswith("buy_"))
async def create_yookassa_payment(callback: CallbackQuery):
    pack_id = callback.data.replace("buy_", "")
    pack = SHOP_PACKS[pack_id]
    user_id = callback.from_user.id
    
    # Отправляем сообщение о загрузке, так как запрос к API занимает время
    loading_msg = await callback.message.edit_text("⏳ <i>Создаю защищенное соединение с банком...</i>", parse_mode="HTML")
    
    try:
        idempotence_key = str(uuid.uuid4())
        payment = Payment.create({
            "amount": {
                "value": str(pack["price"]),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/" # Куда вернуть юзера после оплаты
            },
            "capture": True,
            "description": f"Покупка {pack['name']} (ID {user_id})"
        }, idempotence_key)
        
        pay_url = payment.confirmation.confirmation_url
        payment_id = payment.id
        
        # Сохраняем payment_id в базу, чтобы потом проверить статус
        cursor.execute("INSERT OR REPLACE INTO invoices (payment_id, user_id, pack_id) VALUES (?, ?, ?)", 
                       (payment_id, user_id, pack_id))
        conn.commit()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {pack['price']} ₽", url=pay_url)],
            [InlineKeyboardButton(text="🔄 Я оплатил (Проверить)", callback_data=f"chk_{payment_id}")]
        ])
        
        await loading_msg.edit_text(
            f"📦 Товар: <b>{pack['name']}</b>\n"
            f"💰 К оплате: <b>{pack['price']} ₽</b>\n\n"
            "Нажмите кнопку ниже для безопасной оплаты на сайте ЮKassa:", 
            parse_mode="HTML", reply_markup=kb
        )
        
    except Exception as e:
        logging.error(f"Ошибка ЮKassa API: {e}")
        await loading_msg.edit_text("❌ Ошибка соединения с кассой. Проверьте ShopID и SecretKey.")

# Проверка статуса платежа
@dp.callback_query(F.data.startswith("chk_"))
async def check_payment(callback: CallbackQuery):
    payment_id = callback.data.replace("chk_", "")
    
    try:
        payment = Payment.find_one(payment_id)
        
        if payment.status == 'succeeded':
            # Достаем инфу о заказе из БД
            cursor.execute("SELECT user_id, pack_id FROM invoices WHERE payment_id=?", (payment_id,))
            row = cursor.fetchone()
            
            if not row:
                await callback.answer("Заказ уже был выдан ранее.", show_alert=True)
                return
                
            user_id, pack_id = row
            pack = SHOP_PACKS[pack_id]
            
            # Начисляем товар
            if pack_id.startswith("vip"):
                bonus_time = 30 * 24 * 3600
                current_time = int(time.time())
                cursor.execute("UPDATE users SET vip_until = MAX(vip_until, ?) + ? WHERE user_id=?", 
                               (current_time, bonus_time, user_id))
                msg = "👑 <b>Транзакция подтверждена! VIP на 30 дней успешно активирован!</b>"
            else:
                gems = pack["diamonds"]
                cursor.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id=?", (gems, user_id))
                msg = f"💎 <b>Транзакция подтверждена!</b> Начислено {gems} Алмазов. Спасибо за поддержку!"

            # Удаляем инвойс, чтобы не начислили дважды
            cursor.execute("DELETE FROM invoices WHERE payment_id=?", (payment_id,))
            conn.commit()
            
            await callback.message.edit_text(msg, parse_mode="HTML")
            await callback.answer()
            
        elif payment.status == 'canceled':
             await callback.answer("❌ Платеж отменен банком.", show_alert=True)
        else:
             await callback.answer("⏳ Платеж еще в обработке. Если вы оплатили, подождите 30 секунд.", show_alert=True)
             
    except Exception as e:
        logging.error(f"Ошибка проверки платежа: {e}")
        await callback.answer("⚠️ Ошибка связи с ЮKassa.", show_alert=True)


# ================= АДМИН-ПАНЕЛЬ =================
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="💎 Выдать Алмазы", callback_data="admin_give_gems")]
    ])
    await message.answer("👑 <b>Панель Администратора</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(user_id), SUM(crypto), SUM(diamonds) FROM users")
    users_count, total_crypto, total_diamonds = cursor.fetchone()
    text = (
        "📊 <b>Статистика Игры:</b>\n\n"
        f"👥 Всего игроков: <b>{users_count}</b>\n"
        f"💠 Крипты в экономике: <b>{total_crypto or 0:,}</b>\n"
        f"💎 Алмазов на руках: <b>{total_diamonds or 0:,}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("Введите текст для рассылки всем игрокам:")
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.answer()

@dp.message(AdminStates.waiting_for_broadcast_text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    text = message.text
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    success = 0
    await message.answer("📢 Рассылка началась...")
    for user in users:
        try:
            await bot.send_message(user[0], f"📢 <b>Новость от Создателя:</b>\n\n{text}", parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05) 
        except:
            pass 
    await message.answer(f"✅ Рассылка завершена!\nУспешно доставлено: {success} игрокам.")
    await state.clear()

@dp.callback_query(F.data == "admin_give_gems")
async def admin_give_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("Введите ID игрока и количество алмазов через пробел.\nПример: <code>123456789 500</code>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_give_diamonds)
    await callback.answer()

@dp.message(AdminStates.waiting_for_give_diamonds)
async def admin_give_finish(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        target_id, amount = int(parts[0]), int(parts[1])
        cursor.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id=?", (amount, target_id))
        if cursor.rowcount == 0:
            await message.answer("❌ Игрок не найден.")
        else:
            conn.commit()
            await message.answer(f"✅ Выдано {amount} 💎.")
            try: await bot.send_message(target_id, f"🎁 <b>Администратор выдал вам:</b> {amount} 💎!", parse_mode="HTML")
            except: pass
    except:
        await message.answer("❌ Ошибка ввода. Формат: ID СУММА")
    await state.clear()

# ================= ЗАПУСК =================
async def main():
    print("🚀 Cyber Syndicate (Premium YooKassa Edition) ЗАПУЩЕН!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
