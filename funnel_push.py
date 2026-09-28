import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot_links import get_target_url
from broadcast_throttle import invoke_with_flood_retry, pause_after_send
from config import CHECKER_ID
from lexicon import lexicon
from stats_db import list_all_users

logger = logging.getLogger(__name__)

VPN_BUTTON_TEXT = "Подключить ВПН"


@dataclass(frozen=True)
class PushStage:
    window_start: int
    window_end: int
    lexicon_key: str


# Окна в минутах после первого /start (крон каждые 30 мин, как в Zoomer).
# Отличие от Zoomer: второй пуш через 12 ч (720–750), без ветки «не подключён».
FUNNEL_STAGES: tuple[PushStage, ...] = (
    PushStage(30, 60, "push_not_subscribed_30m"),
    PushStage(720, 750, "push_not_subscribed_12h"),
    PushStage(1410, 1440, "push_not_subscribed_day2_0h"),
    PushStage(2130, 2160, "push_not_subscribed_day2_12h"),
    PushStage(2850, 2880, "push_not_subscribed_day3_0h"),
    PushStage(4290, 4320, "push_not_subscribed_day4_0h"),
    PushStage(5730, 5760, "push_not_subscribed_day5_0h"),
    PushStage(7170, 7200, "push_not_subscribed_day6_0h"),
    PushStage(8610, 8640, "push_not_subscribed_day7_0h"),
)


def _find_stage(offset_minutes: int) -> Optional[PushStage]:
    for stage in FUNNEL_STAGES:
        if stage.window_start <= offset_minutes <= stage.window_end:
            return stage
    return None


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


async def _send_stage(bot: Bot, user_id: int, stage: PushStage, bot_username: str | None) -> None:
    text = lexicon[stage.lexicon_key]
    reply_markup = _vpn_keyboard(bot_username)
    await invoke_with_flood_retry(
        lambda: bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    )


async def send_funnel_push_cron(bot: Bot) -> None:
    """Рассылка по этапам всем, кто хотя бы раз зашёл в бота (без проверки подписки/VPN)."""
    try:
        me = await bot.get_me()
        bot_username = me.username

        users = await asyncio.to_thread(list_all_users)
        if not users:
            logger.info("Автоворонка: нет пользователей")
            return

        now = datetime.now(timezone.utc)
        sent_count = 0
        failed_count = 0

        for user in users:
            minutes_diff = int((now - user.joined_at).total_seconds() / 60)
            stage = _find_stage(minutes_diff)
            if stage is None:
                continue

            try:
                await _send_stage(bot, user.user_id, stage, bot_username)
                sent_count += 1
                logger.info(
                    "Автоворонка: %s → user %s",
                    stage.lexicon_key,
                    user.user_id,
                )
                await pause_after_send()
            except Exception as e:
                failed_count += 1
                logger.debug("Автоворонка: не отправлено user %s: %s", user.user_id, e)

        if CHECKER_ID is not None:
            try:
                await bot.send_message(
                    chat_id=CHECKER_ID,
                    text=(
                        "📊 Отчёт автоворонки:\n\n"
                        f"✅ Отправлено: {sent_count}\n"
                        f"❌ Ошибки: {failed_count}\n"
                        f"⏰ {now.astimezone().strftime('%H:%M:%S %d.%m.%Y')}"
                    ),
                )
            except Exception as e:
                logger.error("Автоворонка: не удалось отправить отчёт: %s", e)

    except Exception as e:
        logger.error("Критическая ошибка автоворонки: %s", e)
