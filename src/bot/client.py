"""Telegram bot factory."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.bot.session import ProxyAwareSession
from src.config import Settings


def create_bot(settings: Settings) -> Bot:
    session = ProxyAwareSession(proxy=settings.proxy) if settings.proxy else ProxyAwareSession()
    return Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    return Dispatcher(storage=MemoryStorage())
