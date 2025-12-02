import asyncio
from functools import lru_cache

from adapters.mt5.config import MT5DataClientConfig, MT5ExecClientConfig
from adapters.mt5.data import MT5DataClient
from adapters.mt5.execution import MT5ExecClientConfig
from adapters.mt5.providers import MT5InstrumentProvider
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock, Messagebus
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.live.factories import LiveDataClientConfig, LiveExecClientFactory


@lru_cache(maxsize=1)
def get_mt5_api_client():
    pass
