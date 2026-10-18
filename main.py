import os
import asyncio
from decimal import Decimal

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

WALLET = "UQCR9_V1Nhsytays7yAJaegVJAl6oaAH_RB4vHsZYsx3hXBi"
SUPPORT = "@wacyz"

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

orders = {}
counter = 0


class Buy(StatesGroup):
    amount = State()
    recipient = State()
    payment = State()
    tx = State()


def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⭐ Купить Stars",
            callback_data="buy"
        )],
        [InlineKeyboardButton(
            text="💎 Telegram Premium",
            url="https://t.me/wacyz"
        )],
        [InlineKeyboardButton(
            text="🆘 Поддержка",
            url="https://t.me/wacyz"
        )]
    ])


def payments():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="TON",
            callback_data="TON"
        )],
        [InlineKeyboardButton(
            text="USDT (сеть TON)",
            callback_data="USDT"
        )]
    ])


def admin_buttons(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"ok:{order_id}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"no:{order_id}"
            )
        ]
    ])


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "👋 <b>AKN SHOP</b>\n\n"
        "⭐ Покупай Telegram Stars!\n\n"
        "Ты сам указываешь количество, "
        "а бот автоматически считает цену.\n\n"
        "💰 Оплата: TON или USDT в сети TON.\n"
        f"🆘 Поддержка: {SUPPORT}",
        reply_markup=menu()
    )


@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery, state: FSMContext):
    await state.set_state(Buy.amount)

    await call.message.answer(
        "⭐ <b>Сколько Stars хочешь купить?</b>\n\n"
        "Напиши количество числом.\n"
        "Например: 100, 250, 500, 1000 или 1000000.\n\n"
        "Минимум — 50 Stars.\n"
        "Максимум — 1000000 Stars.\n\n"
        "50 Stars = 0.75 TON или 1 USDT."
    )

    await call.answer()


@dp.message(Buy.amount)
async def amount(message: Message, state: FSMContext):
    try:
        number = int((message.text or "").strip())
    except ValueError:
        await message.answer("Напиши количество только цифрами.")
        return

    if number < 50 or number > 1000000:
        await message.answer(
            "Можно заказать от 50 до 1000000 Stars."
        )
        return

    ton = Decimal(number) * Decimal("0.015")
    usdt = Decimal(number) * Decimal("0.02")

    await state.update_data(
        amount=number,
        ton=str(ton),
        usdt=str(usdt)
    )

    await state.set_state(Buy.recipient)

    await message.answer(
        f"⭐ Количество: <b>{number:,} Stars</b>\n\n"
        f"💎 Цена: <b>{ton.normalize()} TON</b>\n"
        f"💵 Или <b>{usdt.normalize()} USDT</b>\n\n"
        "Теперь напиши @username получателя Stars."
    )


@dp.message(Buy.recipient)
async def recipient(message: Message, state: FSMContext):
    username = (message.text or "").strip().lstrip("@")

    if not username or not username.replace("_", "").isalnum():
        await message.answer("Напиши корректный Telegram username.")
        return

    username = "@" + username

    await state.update_data(recipient=username)
    await state.set_state(Buy.payment)

    await message.answer(
        f"👤 Получатель: <b>{username}</b>\n\n"
        "Выбери способ оплаты:",
        reply_markup=payments()
    )


@dp.callback_query(Buy.payment, F.data.in_(["TON", "USDT"]))
async def payment(call: CallbackQuery, state: FSMContext):
    global counter

    data = await state.get_data()
    currency = call.data
    price = data["ton"] if currency == "TON" else data["usdt"]

    counter += 1
    order_id = counter

    orders[order_id] = {
        "user_id": call.from_user.id,
        "amount": data["amount"],
        "recipient": data["recipient"],
        "currency": currency,
        "price": price,
        "status": "waiting"
    }

    await state.update_data(order_id=order_id)
    await state.set_state(Buy.tx)

    network = (
        "TON"
        if currency == "TON"
        else "USDT в сети TON"
    )

    await call.message.answer(
        f"🧾 <b>Заказ №{order_id}</b>\n\n"
        f"⭐ Stars: <b>{data['amount']:,}</b>\n"
        f"👤 Получатель: <b>{data['recipient']}</b>\n"
        f"💰 К оплате: <b>{price} {currency}</b>\n\n"
        f"Переведи деньги на кошелёк:\n"
        f"<code>{WALLET}</code>\n\n"
        f"Сеть: <b>{network}</b>\n\n"
        "После оплаты отправь сюда хеш транзакции (TX hash).\n\n"
        "⚠️ USDT отправляй только в сети TON."
    )

    await call.answer()


@dp.message(Buy.tx)
async def transaction(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    order = orders.get(order_id)

    if not order:
        await state.clear()
        await message.answer("Заказ не найден. Напиши /start.")
        return

    tx = (message.text or "").strip()

    if len(tx) < 10:
        await message.answer("Пришли корректный TX hash.")
        return

    order["tx"] = tx
    order["status"] = "checking"

    await state.clear()

    await message.answer(
        f"✅ Хеш получен!\n"
        f"Заказ №{order_id} отправлен на проверку.\n\n"
        "После проверки оплаты ты получишь уведомление."
    )

    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            f"🆕 <b>Заказ №{order_id}</b>\n\n"
            f"Покупатель ID: <code>{order['user_id']}</code>\n"
            f"Stars: {order['amount']:,}\n"
            f"Получатель: {order['recipient']}\n"
            f"Оплата: {order['price']} {order['currency']}\n"
            f"TX: <code>{tx}</code>\n\n"
            "Проверь транзакцию вручную!",
            reply_markup=admin_buttons(order_id)
        )


@dp.callback_query(F.data.startswith("ok:"))
async def approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Нет доступа!", show_alert=True)
        return

    order_id = int(call.data.split(":")[1])
    order = orders.get(order_id)

    if not order:
        await call.answer("Заказ не найден.")
        return

    order["status"] = "approved"

    await bot.send_message(
        order["user_id"],
        f"✅ Заказ №{order_id} подтверждён!\n\n"
        "Администратор должен отправить Stars вручную."
    )

    await call.message.answer(
        f"Заказ №{order_id} подтверждён."
    )
    await call.answer("Готово!")


@dp.callback_query(F.data.startswith("no:"))
async def reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Нет доступа!", show_alert=True)
        return

    order_id = int(call.data.split(":")[1])
    order = orders.get(order_id)

    if not order:
        await call.answer("Заказ не найден.")
        return

    order["status"] = "rejected"

    await bot.send_message(
        order["user_id"],
        f"❌ Заказ №{order_id} отклонён.\n"
        f"Если возникла ошибка, напиши {SUPPORT}."
    )

    await call.message.answer(
        f"Заказ №{order_id} отклонён."
    )
    await call.answer("Готово!")


async def main():
    if not TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN")

    await dp.start_polling(bot)


if name == "main":
    asyncio.run(main())
