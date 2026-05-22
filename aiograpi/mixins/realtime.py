from typing import Any, Callable

from aiograpi.realtime import RealtimeClient


class RealtimeMixin:
    realtime = None

    def realtime_client(self, transport=None) -> RealtimeClient:
        return RealtimeClient(self, transport=transport)

    async def realtime_connect(self, transport=None) -> RealtimeClient:
        if self.realtime is None:
            self.realtime = self.realtime_client(transport=transport)
        elif transport is not None:
            self.realtime.transport = transport
        await self.realtime.connect()
        return self.realtime

    async def realtime_disconnect(self) -> None:
        if self.realtime is None:
            return
        await self.realtime.disconnect()
        self.realtime = None

    def realtime_on(self, event: str, handler: Callable[[Any], Any]) -> None:
        if self.realtime is None:
            self.realtime = self.realtime_client()
        self.realtime.on(event, handler)

    async def realtime_read_once(self) -> Any:
        if self.realtime is None:
            raise RuntimeError("Realtime client is not connected")
        return await self.realtime.read_once()
