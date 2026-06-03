from aiograpi.realtime import FbnsClient, FbnsDeviceAuth, RealtimeClient


class RealtimeMixin:
    realtime = None
    fbns = None

    def realtime_client(self, transport=None) -> RealtimeClient:
        return RealtimeClient(self, transport=transport)

    async def realtime_connect(self, transport=None) -> RealtimeClient:
        if not self.realtime:
            self.realtime = self.realtime_client(transport=transport)
        elif transport is not None:
            self.realtime.transport = transport
        await self.realtime.connect()
        return self.realtime

    async def realtime_disconnect(self) -> None:
        if self.realtime:
            await self.realtime.disconnect()
            self.realtime = None

    def realtime_on(self, event: str, handler) -> None:
        if not self.realtime:
            self.realtime = self.realtime_client()
        self.realtime.on(event, handler)

    async def realtime_read_once(self):
        if not self.realtime:
            raise RuntimeError("Realtime client is not connected")
        return await self.realtime.read_once()

    async def realtime_ping(self) -> bool:
        if not self.realtime:
            raise RuntimeError("Realtime client is not connected")
        return await self.realtime.ping()

    def fbns_client(self, transport=None, auth: FbnsDeviceAuth | None = None) -> FbnsClient:
        return FbnsClient(self, transport=transport, auth=auth)

    async def fbns_connect(
        self, transport=None, auth: FbnsDeviceAuth | None = None, register: bool = True
    ) -> FbnsClient:
        if not self.fbns:
            self.fbns = self.fbns_client(transport=transport, auth=auth)
        else:
            if transport is not None:
                self.fbns.transport = transport
            if auth is not None:
                self.fbns.auth = auth
        await self.fbns.connect(register=register)
        return self.fbns

    async def fbns_disconnect(self) -> None:
        if self.fbns:
            await self.fbns.disconnect()
            self.fbns = None

    def fbns_on(self, event: str, handler) -> None:
        if not self.fbns:
            self.fbns = self.fbns_client()
        self.fbns.on(event, handler)

    async def fbns_read_once(self):
        if not self.fbns:
            raise RuntimeError("FBNS client is not connected")
        return await self.fbns.read_once()

    async def fbns_ping(self) -> bool:
        if not self.fbns:
            raise RuntimeError("FBNS client is not connected")
        return await self.fbns.ping()
