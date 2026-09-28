"""Паузы между массовыми отправками, чтобы не ловить 429 от Telegram."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram.exceptions import TelegramRetryAfter

logger = logging.getLogger(__name__)

SEND_INTERVAL_SEC = 0.1

T = TypeVar("T")


async def invoke_with_flood_retry(action: Callable[[], Awaitable[T]]) -> T:
    while True:
        try:
            return await action()
        except TelegramRetryAfter as e:
            wait = float(e.retry_after) + 1.0
            logger.warning("Flood limit Telegram, пауза %.1f с", wait)
            await asyncio.sleep(wait)


async def pause_after_send() -> None:
    """Вызывать после каждой успешной отправки в рассылке."""
    await asyncio.sleep(SEND_INTERVAL_SEC)
