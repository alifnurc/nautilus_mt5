import asyncio
from typing import Any

from adapters.mt5.config import MT5DataClientConfig
from adapters.mt5.constants import MT5_VENUE
from adapters.mt5.providers import MT5InstrumentProvider
from adapters.mt5.types import MT5_INSTRUMENT_TYPES, MT5Instrument
from nautilus_trader.cache.cache import Cache
from nautilus_trader.cache.transformers import transform_instrument_from_pyo3
from nautilus_trader.common.component import LiveClock, MessageBus
from nautilus_trader.common.enums import LogColor
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.core.datetime import ensure_pydatetime_utc
from nautilus_trader.data.messages import (
    RequestBars,
    RequestInstrument,
    RequestInstruments,
    RequestTradeTicks,
    SubscribeBars,
    SubscribeInstrument,
    SubscribeInstruments,
    SubscribeOrderBook,
    SubscribeQuoteTicks,
    SubscribeTradeTicks,
)
from nautilus_trader.live.cancellation import (
    DEFAULT_FUTURE_CANCELLATION_TIMEOUT,
    cancel_tasks_with_timeout,
)
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.data import (
    Bar,
    FundingRateUpdate,
    TradeTick,
    capsule_to_data,
)
from nautilus_trader.model.enums import (
    AggregationSource,
    BarAggregation,
    BookType,
    PriceType,
    book_type_from_str,
)
from nautilus_trader.model.identifiers import ClientId


class MT5DataClient(LiveMarketDataClient):
    pass
