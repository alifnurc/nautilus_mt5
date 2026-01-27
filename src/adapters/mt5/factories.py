import asyncio
from functools import lru_cache

from adapters.mt5.client import AsyncMT5RPyCClient
from adapters.mt5.config import MT5ClientConfig
from adapters.mt5.data import MT5DataClient
from adapters.mt5.execution import MT5ExecutionClient
from adapters.mt5.providers import MT5InstrumentProvider
from nautilus_trader.common.component import LiveClock, MessageBus
from nautilus_trader.cache.cache import Cache
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.live.factories import (
    LiveDataClientFactory,
    LiveExecClientFactory,
)


@lru_cache(maxsize=1)
def get_mt5_rpyc_client(config: MT5ClientConfig) -> AsyncMT5RPyCClient:
    return AsyncMT5RPyCClient().initialize(config=config)


@lru_cache(maxsize=1)
def get_mt5_instrument_provider(
    client: AsyncMT5RPyCClient, active_only: bool, config: InstrumentProviderConfig
) -> MT5InstrumentProvider:
    return MT5InstrumentProvider(client=client, active_only=active_only, config=config)


class MT5LiveDataClientFactory(LiveDataClientFactory):
    """
    Provides a MT5 live data client factory.
    """

    @staticmethod
    def create(
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: MT5ClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> MT5DataClient:
        client = get_mt5_rpyc_client(config)

        provider = get_mt5_instrument_provider(
            client=client, active_only=True, config=config.instrument_provider
        )

        return MT5DataClient(
            loop=loop,
            client=client,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=provider,
            config=config,
            name=name,
        )


class MT5LiveExecClientFactory(LiveExecClientFactory):
    """
    Provides a MT5 live execution client factory.
    """

    @staticmethod
    def create(
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: MT5ClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> MT5ExecutionClient:
        client = get_mt5_rpyc_client(config)

        provider = get_mt5_instrument_provider(
            client=client, active_only=True, config=config.instrument_provider
        )

        return MT5ExecutionClient(
            loop=loop,
            client=client,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=provider,
            config=config,
            name=name,
        )
