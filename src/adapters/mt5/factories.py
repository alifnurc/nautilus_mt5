import asyncio
from functools import lru_cache

from adapters.mt5.config import MT5ClientConfig
from adapters.mt5.data import MT5DataClient
from adapters.mt5.providers import MT5InstrumentProvider
from nautilus_trader.common.component import LiveClock, MessageBus
from nautilus_trader.cache.cache import Cache
from nautilus_trader.config import InstrumentProviderConfig, LiveExecClientConfig
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.live.factories import (
    LiveDataClientFactory,
    LiveExecClientFactory,
)


@lru_cache(maxsize=1)
def get_mt5_instrument_provider() -> MT5InstrumentProvider:
    return MT5InstrumentProvider(client=client, config=config)


class MT5LiveDataClientFactory(LiveDataClientFactory):
    """
    Provides a MT5 live data client factory.
    """

    pass


class MT5LiveExecClientFactory(LiveExecClientConfig):
    """
    Provides a MT5 live execution client factory.
    """

    pass
