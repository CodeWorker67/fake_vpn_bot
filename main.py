import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

from bot_links import get_target_url
from handlers_export import router as export_router
from stats_db import init_db, record_start_user

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("Укажите BOT_TOKEN в файле .env")
    sys.exit(1)

START_TEXT = (
    "🔐 Безопасный и стабильный доступ к зарубежным сайтам и приложениям.\n\n"
    "🌍 20+ стран\n"
    "⚡️ Высокая скорость без ограничений\n"
    '🔥 Сервер "Антиглушилка" для обхода белых списков \n'
    "🎁 Бесплатный триал\n\n"
    "👇 Нажмите «Открыть», чтобы получить персональный ключ доступа."
)

dp = Dispatcher()
dp.include_router(export_router)


@dp.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    if message.from_user:
        user = message.from_user
        await asyncio.to_thread(
            record_start_user,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_premium=bool(user.is_premium),
        )

    me = await bot.get_me()
    username = me.username or ""
    target_url = get_target_url(username)

    keyboard = None
    if target_url:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть бота", url=target_url)]
            ]
        )

    await message.answer(START_TEXT, reply_markup=keyboard)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await asyncio.to_thread(init_db)
    bot = Bot(token=BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
