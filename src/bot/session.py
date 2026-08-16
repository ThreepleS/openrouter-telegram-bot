"""aiogram session that uses system proxy/VPN settings."""

from __future__ import annotations

import asyncio

from aiohttp import ClientSession
from aiohttp.hdrs import USER_AGENT
from aiohttp.http import SERVER_SOFTWARE
from aiogram.__meta__ import __version__
from aiogram.client.session.aiohttp import AiohttpSession


class ProxyAwareSession(AiohttpSession):
    async def create_session(self) -> ClientSession:
        if self._should_reset_connector:
            await self.close()

        if self._session is None or self._session.closed:
            self._session = ClientSession(
                connector=self._connector_type(**self._connector_init),
                headers={
                    USER_AGENT: f"{SERVER_SOFTWARE} aiogram/{__version__}",
                },
                trust_env=True,
            )
            self._should_reset_connector = False

        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            await asyncio.sleep(0.25)
