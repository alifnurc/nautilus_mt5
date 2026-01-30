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
        self._client = client
        self._config = config
        self._active_only = True  # Always use active instruments for live clients

        # Periodic updates
        self._update_instruments_interval_mins: int | None = (
            config._update_instruments_interval_mins
        )
        self._update_instruments_task: asyncio.Task | None = None

    @property
    def instrument_provider(self) -> MT5InstrumentProvider:
        return self._instrument_provider  # type: ignore

    async def _connect(self) -> None:
        # Connect client
        await self._instrument_provider.initialize()
        self._cache_instruments()
        self._send_all_instruments_to_data_engine()

        # instruments = self.instrument_provider.instruments_pyo3()

        self._log.info(
            f"Connected to RPyC {self._config.rpyc_host}:{self._config.rpyc_port}",
            LogColor.BLUE,
        )

        # Start periodic instrument updates if configured
        if self._update_instruments_interval_mins:
            self._update_instruments_task = self.create_task(
                self._update_instruments(self._update_instruments_interval_mins),
            )

    def _cache_instruments(self) -> None:
        # Ensures instrument definitions are available for correct
        # price and size precisions when parsing responses
        instruments_pyo3 = self.instrument_provider.instruments_pyo3()

        for inst in instruments_pyo3:
            self._client.cache_instrument(inst)

        self._log.debug("Cached instruments", LogColor.MAGENTA)

    def _send_all_instruments_to_data_engine(self) -> None:
        for instrument in self._instrument_provider.get_all().values():
            self._handle_data(instrument)

        for currency in self._instrument_provider.currencies().values():
            self._cache.add_currency(currency)

    async def _update_instruments(self, interval_mins: int) -> None:
        while True:
            try:
                self._log.debug(
                    f"Scheduled task 'update_instruments' to run in {interval_mins} minutes",
                )
                await asyncio.sleep(interval_mins * 60)
                await self._instrument_provider.initialize(reload=True)
                self._send_all_instruments_to_data_engine()
            except asyncio.CancelledError:
                self._log.debug("Canceled task 'update_instruments'")
            except Exception as e:
                self._log.error(f"Error updating instruments: {e}")

    async def _disconnect(self) -> None:
        await self._client.disconnect()
        self._log.info("MT5 Data Client disconnected")

    async def _subscribe_bars(self, command: SubscribeBars) -> None:
        pyo3_bar_type = nautilus_pyo3.BarType.from_str(str(command.bar_type))
        await self._client.subscribe_bars(pyo3_bar_type)

    async def _unsubscribe_bars(self, command: UnsubscribeBars) -> None:
        pyo3_bar_type = nautilus_pyo3.BarType.from_str(str(command.bar_type))
        await self._client.unsubscribe_bars(pyo3_bar_type)

    async def _request_bars(self, request: RequestBars) -> None:
        bar_type = request.bar_type

        if (
            bar_type.is_internally_aggregated()
            or bar_type.aggregation_source != AggregationSource.EXTERNAL
        ):
            self._log.error(
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
            self._log.error(
                f"Cannot request {bar_type} bars: unsupported MT5 specification",
            )
            return

        limit = request.limit or None
        if limit is not None and limit > 1000:
            self._log.warning(
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
            pyo3_bars = await self._client.request_bars(
                bar_type=pyo3_bar_type,
                start=start,
                end=end,
                limit=limit,
                partial=partial,
            )
        except Exception as e:  # pragma: no cover - network failures
            self._log.exception(f"Failed to request bars for {bar_type}", e)
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
