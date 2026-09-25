import asyncio
import logging
import secrets
from dataclasses import dataclass

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot_links import get_target_url
from config import ADMIN_IDS
from stats_db import count_users, list_all_users

logger = logging.getLogger(__name__)
router = Router()

VPN_BUTTON_TEXT = "Подключить ВПН"
PROGRESS_EVERY = 1000
_SEND_BATCH_SIZE = 25
_SEND_BATCH_PAUSE_SEC = 1.0


class PushStates(StatesGroup):
    waiting_content = State()


@dataclass
class PushCampaign:
    admin_id: int
    from_chat_id: int
    message_id: int


_pending: dict[str, PushCampaign] = {}


def _vpn_keyboard(bot_username: str | None) -> InlineKeyboardMarkup | None:
    if not bot_username:
        return None
    target_url = get_target_url(bot_username)
    if not target_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=VPN_BUTTON_TEXT, url=target_url)]
        ]
    )


def _is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in ADMIN_IDS


async def _ask_push_confirm(message: Message, source: Message) -> None:
    if not message.from_user:
        return

    total = await asyncio.to_thread(count_users)
    token = secrets.token_hex(8)
    _pending[token] = PushCampaign(
        admin_id=message.from_user.id,
        from_chat_id=source.chat.id,
        message_id=source.message_id,
    )

    confirm_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data=f"push:yes:{token}"),
                InlineKeyboardButton(text="Нет", callback_data=f"push:no:{token}"),
            ]
        ]
    )
    await message.answer(
        f"Сообщение будет отправлено {total} пользователям.\n\nОтправить?",
        reply_markup=confirm_kb,
    )


async def _start_push_flow(
    message: Message,
    bot: Bot,
    source: Message,
    *,
    preview_with_copy: bool = True,
) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    if preview_with_copy:
        me = await bot.get_me()
        keyboard = _vpn_keyboard(me.username)
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=source.chat.id,
            message_id=source.message_id,
            reply_markup=keyboard,
        )

    await _ask_push_confirm(message, source)


@router.message(Command(commands=["push"]))
async def cmd_push(message: Message, bot: Bot, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer("❌ Эта команда доступна только администраторам.")
        return

    if message.reply_to_message:
        await state.clear()
        await _start_push_flow(message, bot, message.reply_to_message)
        return

    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            await state.clear()
            me = await bot.get_me()
            preview_source = await message.answer(
                parts[1].strip(),
                reply_markup=_vpn_keyboard(me.username),
            )
            await _start_push_flow(message, bot, preview_source, preview_with_copy=False)
            return

    await state.set_state(PushStates.waiting_content)
    await message.answer(
        "Отправьте сообщение для рассылки (текст, фото, видео и т.д.) "
        "или ответьте командой /push на нужное сообщение."
    )


@router.message(PushStates.waiting_content)
async def push_waiting_content(message: Message, bot: Bot, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await state.clear()
        return

    await state.clear()
    await _start_push_flow(message, bot, message)


def _pop_campaign(token: str, admin_id: int) -> PushCampaign | None:
    campaign = _pending.pop(token, None)
    if campaign is None or campaign.admin_id != admin_id:
        if campaign is not None:
            _pending[token] = campaign
        return None
    return campaign


@router.callback_query(F.data.startswith("push:yes:"))
async def push_confirm_yes(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    token = callback.data.removeprefix("push:yes:")
    campaign = _pop_campaign(token, callback.from_user.id)
    if campaign is None:
        await callback.answer("Рассылка недоступна или уже обработана.", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await bot.send_message(campaign.admin_id, "Рассылка началась...")

    me = await bot.get_me()
    keyboard = _vpn_keyboard(me.username)
    users = await asyncio.to_thread(list_all_users)
    total = len(users)
    ok = 0
    fail = 0

    for i, user in enumerate(users, 1):
        try:
            await bot.copy_message(
                chat_id=user.user_id,
                from_chat_id=campaign.from_chat_id,
                message_id=campaign.message_id,
                reply_markup=keyboard,
            )
            ok += 1
        except Exception as e:
            fail += 1
            logger.debug("Push to %s failed: %s", user.user_id, e)

        if i % PROGRESS_EVERY == 0:
            await bot.send_message(
                campaign.admin_id,
                f"Отправлено {i} из {total} пользователей.",
            )

        if i % _SEND_BATCH_SIZE == 0:
            await asyncio.sleep(_SEND_BATCH_PAUSE_SEC)

    await bot.send_message(
        campaign.admin_id,
        "Рассылка завершена.\n"
        f"Успешно: {ok}\n"
        f"Ошибки: {fail}\n"
        f"Всего в базе: {total}",
    )
    logger.info(
        "Админ %s завершил рассылку: ok=%s fail=%s total=%s",
        campaign.admin_id,
        ok,
        fail,
        total,
    )


@router.callback_query(F.data.startswith("push:no:"))
async def push_confirm_no(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    token = callback.data.removeprefix("push:no:")
    campaign = _pop_campaign(token, callback.from_user.id)
    if campaign is None:
        await callback.answer("Рассылка недоступна или уже обработана.", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await bot.send_message(campaign.admin_id, "Рассылка отменена")
