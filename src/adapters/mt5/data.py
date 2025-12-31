import asyncio
from typing import Any, List, Optional, Set

from adapters.mt5.client import AsyncMT5RPyCClient
from adapters.mt5.config import MT5ClientConfig
from adapters.mt5.constants import MT5_VENUE
from adapters.mt5.providers import MT5InstrumentProvider
from adapters.mt5.types import MT5_INSTRUMENT_TYPES, MT5Instrument
from nautilus_trader.cache.cache import Cache
from nautilus_trader.cache.transformers import transform_instrument_from_pyo3
from nautilus_trader.common.component import LiveClock, MessageBus
from nautilus_trader.common.enums import LogColor
from nautilus_trader.core import Request, nautilus_pyo3
from nautilus_trader.core.datetime import ensure_pydatetime_utc
from nautilus_trader.data.messages import (
    RequestBars,
    SubscribeBars,
    UnsubscribeBars,
)
from nautilus_trader.live.cancellation import (
    DEFAULT_FUTURE_CANCELLATION_TIMEOUT,
    cancel_tasks_with_timeout,
)
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model import BarType, InstrumentId, QuoteTick
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import (
    AggregationSource,
    BarAggregation,
    PriceType,
)
from nautilus_trader.model.identifiers import ClientId


class MT5DataClient(LiveMarketDataClient):
    """
    Provides a data client for the MT5 platform.

    Parameters
    ----------
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        client: AsyncMT5RPyCClient,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
        instrument_provider: MT5InstrumentProvider,
        config: MT5ClientConfig,
        name: str | None,
    ) -> None:
        super().__init__(
            loop=loop,
            client_id=ClientId(name or MT5_VENUE.value),
            venue=MT5_VENUE,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=instrument_provider,
        )

        # Configuration
        self.client = client
        self.config = config
        self._connected = False
        self._subscriptions: Set[InstrumentId] = set()
        self._instuments_loaded = False
        self._polling_task: Optional[asyncio.Task] = None
        self._polling_interval = 0.1  # 100ms
        self._active_only = True  # Always use active instruments for live clients

        # TODO:
        # Set logging

    @property
    def instrument_provider(self) -> MT5InstrumentProvider:
        return self._instrument_provider  # type: ignore

    async def _connect(self) -> None:
        try:
            # Connect client
            self.log.info("Connecting to MT5 Data Client...")

            success = await self.client.connect(
                self.config.account_number,
                self.config.password,
                self.config.server,
                self.config.timeout,
                self.config.rpyc_host,
                self.config.rpyc_port,
            )
            if not success:
                raise ConnectionError("Failed to connect to MT5 via RPyC")

            self._connected = True

            # Load instruments based on config
            await self.instrument_provider.initialize()
            for instrument in self._instrument_provider.list_all():
                self._handle_data(instrument)

            self.log.info("MT5 Data Client connected successfully")
        except Exception as e:
            self.log.error(f"Failed to connect: {e}")
            raise

    async def _disconnect(self) -> None:
        await self.client.disconnect()
        self._connected = False
        self.log.info("MT5 Data Client disconnected")

    async def _subscribe_bars(self, command: SubscribeBars) -> None:
        pyo3_bar_type = nautilus_pyo3.BarType.from_str(str(command.bar_type))
        await self.client.subscribe_bars(pyo3_bar_type)

    async def _unsubscribe_bars(self, command: UnsubscribeBars) -> None:
        pyo3_bar_type = nautilus_pyo3.BarType.from_str(str(command.bar_type))
        await self.client.unsubscribe_bars(pyo3_bar_type)

    async def _request_bars(self, request: RequestBars) -> None:
        bar_type = request.bar_type

        if (
            bar_type.is_internally_aggregated()
            or bar_type.aggregation_source != AggregationSource.EXTERNAL
        ):
            self.log.error(
                f"Cannot request {bar_type} bars: MT5 only provides EXTERNAL aggregation",
            )
            return

        spec = bar_type.spec
        supported = spec.price_type == PriceType.BID and (
            (spec.aggregation == BarAggregation.MINUTE and spec.step in (1, 5))
            or (spec.aggregation == BarAggregation.HOUR and spec.step == 1)
            or (spec.aggregation == BarAggregation.DAY and spec.step == 1)
        )
        if not supported:
            self.log.error(
                f"Cannot request {bar_type} bars: unsupported MT5 specification",
            )
            return

        limit = request.limit or None
        if limit is not None and limit > 1000:
            self.log.warning(
                f"MT5 bar limit {limit} exceeds maximum of 1000, clamping",
            )
            limit = 1000

        partial = False

        if isinstance(request.params, dict):
            partial = bool(request.params.get("partial", False))

        pyo3_bar_type = nautilus_pyo3.BarType.from_str(str(bar_type))
        start = ensure_pydatetime_utc(request.start) if request.start else None
        end = ensure_pydatetime_utc(request.end) if request.end else None

        try:
            pyo3_bars = await self.client.request_bars(
                bar_type=pyo3_bar_type,
                start=start,
                end=end,
                limit=limit,
                partial=partial,
            )
        except Exception as e:  # pragma: no cover - network failures
            self.log.exception(f"Failed to request bars for {bar_type}", e)
            return

        bars = Bar.from_pyo3_list(pyo3_bars)

        self._handle_bars(
            bar_type,
            bars,
            request.id,
            request.start,
            request.end,
            request.params,
        )
