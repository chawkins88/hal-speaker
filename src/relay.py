"""
Relay: sends transcribed speech to the OpenClaw gateway (Hal) and returns the response.

Uses the OpenClaw internal messaging API to inject a message into the voice session
and poll for Hal's reply.
"""

import asyncio
import logging
import time

import aiohttp

log = logging.getLogger("relay")


class HalRelay:
    def __init__(self, config):
        self.config = config
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.relay_timeout)
            )
        return self._session

    async def send(self, text: str) -> str:
        """
        Send text to Hal via OpenClaw gateway and return the response.

        This posts to the OpenClaw gateway's internal /api/sessions/send endpoint,
        targeting the voice session, and polls for the reply.
        """
        session = await self._get_session()
        base_url = self.config.openclaw_url.rstrip("/")

        payload = {
            "message": text,
            "channel": self.config.openclaw_channel,
            "sessionKey": self.config.openclaw_session_key or None,
        }

        log.debug("Relaying to Hal: %r", text)

        try:
            async with session.post(
                f"{base_url}/api/voice/message",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    log.error("Relay HTTP %d: %s", resp.status, body[:200])
                    raise RuntimeError(f"Gateway returned HTTP {resp.status}")

                data = await resp.json()
                response_text = data.get("response") or data.get("text") or ""
                log.debug("Hal replied: %r", response_text[:120])
                return response_text

        except aiohttp.ClientConnectorError as e:
            log.error("Cannot connect to OpenClaw gateway at %s: %s", base_url, e)
            raise RuntimeError(f"Cannot reach gateway: {e}") from e

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
