import asyncio
import pandas as pd
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import FillReport
from nautilus_trader.model.enums import (
    BarAggregation,
    LiquiditySide,
    OrderSide,
    asset_class_from_str,
)
from nautilus_trader.model.instruments import Cfd
from pymt5linux import MetaTrader5
from adapters.mt5.config import MT5ClientConfig
from adapters.mt5.constants import MT5_VENUE
from nautilus_trader.model import (
    Bar,
    BarType,
    Currency,
    InstrumentId,
    Money,
    Price,
    Quantity,
    Symbol,
)
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock, Logger, MessageBus
from nautilus_trader.common.enums import LogColor


class AsyncMT5RPyCClient:
    """
    Async wrapper for MT5RPyCClient integration with asyncio NautilusTrader
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
                cls._instance._config = None
            return cls._instance

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._log = Logger("MT5_Client")
        self._subscription = {}

    def initialize(
        self,
        config: MT5ClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ):
        try:
            self._log.info(
                f"Connecting to RPyC server at {config.rpyc_host}:{config.rpyc_port}",
                LogColor.BLUE,
            )
            self.conn = MetaTrader5(host=config.rpyc_host, port=config.rpyc_port)

            # Initialize MT5 terminal
            initialized = self.conn.initialize(
                login=config.account_number,
                password=config.password,
                server=config.server,
                timeout=config.timeout,
            )

            if not initialized:
                error = self.conn.last_error()
                self._log.error(f"MT5 initialize failed: {error}")

            self._initialized = True
            self._config = config
            self._msgbus = msgbus
            self._cache = cache
            self._clock = clock
            self._log.info(
                f"Connected to MT5 via RPyC. Account: {config.account_number}"
            )

            # TODO:
            # Start heartbeat thread
            # self._start_heartbeat()

            return self
        except Exception as e:
            self._log.error(f"Connection failed: {e}")
            # self.disconnect()
            return self

    def is_initialized(self):
        return self._initialized

    def shutdown(self):
        if self.is_initialized():
            self.conn.shutdown()
        return self

    async def disconnect(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.shutdown,
        )

    async def get_server_time(self) -> int:
        loop = asyncio.get_event_loop()
        try:
            symbol_info_tick = await loop.run_in_executor(
                self.executor, lambda: self.conn.symbol_info_tick("EURUSD")
            )

            return symbol_info_tick.time * 1000
        except Exception as e:
            self._log.error(f"Failed to get server time: {e}")

    async def request_instruments(self, active_only) -> Cfd:
        loop = asyncio.get_event_loop()
        try:
            mt5_symbols = await loop.run_in_executor(
                self.executor,
                lambda: self.conn.symbols_get(),
            )

            instruments: list[Cfd] = []
            for i in range(len(mt5_symbols)):
                instruments.append(
                    self._parse_mt5_symbol_to_cfd(mt5_symbol=mt5_symbols, index=i)
                )

            return instruments
        except Exception as e:
            self._log.error(f"Failed to get instruments: {e}")

    async def subscribe_bars(self, bar_type: BarType):
        if bar_type in self._subscription:
            return

        self._subscription[bar_type] = asyncio.create_task(
            self._bar_stream_loop(bar_type)
        )

    async def unsubscribe_bars(self, bar_type: BarType):
        try:
            if bar_type not in self._subscription:
                return

            self._subscription.pop(bar_type).cancel()
        except Exception as e:
            self._log.error(f"Failed to unsubscribe bars: {e}")

    async def request_bars(self, bar_type, start, end, limit, partial) -> list[Bar]:
        loop = asyncio.get_event_loop()

        # TODO:
        # handle limit and partial condition
        # naive datetime

        # Get bar request specification
        spec = bar_type.spec
        symbol = bar_type.instrument_id.symbol
        timeframe = self._get_timeframe(spec)

        self._log.debug(
            f"Bar request args: {bar_type}, {start}, {end}, {limit}, {partial}"
        )

        try:
            mt5_bars = await loop.run_in_executor(
                self.executor,
                lambda: self.conn.copy_rates_range(symbol, timeframe, start, end),
            )

            bars: list[Bar] = []
            for i in range(len(mt5_bars)):
                bars.append(
                    self._parse_mt5_bar(mt5_bar=mt5_bars, bar_type=bar_type, index=i)
                )

            return bars
        except Exception as e:
            self._log.error(f"Failed to request bars: {e}")

    async def subscribe_executions(self):
        self._subscription["orders"] = asyncio.create_task(
            self._executions_stream_loop()
        )

    async def unsubscribe_executions(self):
        try:
            self._subscription.pop("orders").cancel()

        except Exception as e:
            self._log.error(f"Failed to unsubscribe orders: {e}")

    async def _bar_stream_loop(self, bar_type: BarType):
        loop = asyncio.get_event_loop()

        # Get bar specification
        spec = bar_type.spec
        symbol = bar_type.instrument_id.symbol
        timeframe = self._get_timeframe(spec)
        topic = f"data.bars.{bar_type}"

        try:
            while True:
                mt5_bar = await loop.run_in_executor(
                    self.executor,
                    lambda: self.conn.copy_rates_from_pos(symbol, timeframe, 0, 1),
                )

                bar = self._parse_mt5_bar(mt5_bar=mt5_bar, bar_type=bar_type)
                if mt5_bar is not None:
                    self._msgbus.publish(topic, bar)

                await asyncio.sleep(1)
        except Exception as e:
            self._log.error(f"Failed to subscribe bars: {e}")

    async def _executions_stream_loop(self):
        loop = asyncio.get_event_loop()

        topic = f"events.order"

        try:
            while True:
                # For now, I don't have any idea
                # about using latest week history
                date_to = datetime.now(tz=timezone.utc)
                date_from = date_to - pd.Timedelta(days=7)

                mt5_deals = await loop.run_in_executor(
                    self.executor,
                    lambda: self.conn.history_deals_get(date_from, date_to),
                )

                if mt5_deals is not None:
                    for i in range(len(mt5_deals)):
                        deal = self._parse_mt5_deals_to_fill_report(
                            mt5_deal=mt5_deals, index=i
                        )
                        self._msgbus.publish(topic, deal)

                await asyncio.sleep(1)
        except Exception as e:
            self._log.error(f"Failed to subscribe orders: {e}")

    def _get_broker_offset_time(self, symbol):
        tick = self.conn.symbol_info_tick(symbol)
        server_epoch = tick.time
        utc_epoch = int(self._clock.timestamp())

        offset_sec = server_epoch - utc_epoch

        # Snap to closest hours (DST-safe enough)
        offset_sec = round(offset_sec / 3600) * 3600
        return offset_sec

    def _get_broker_timezone(self, symbol):
        tick = self.conn.symbol_info_tick(symbol)
        server_dt = datetime.fromtimestamp(tick.time, tz=timezone.utc)
        utc_now = self._clock.utc_now()

        offset_hours = round((server_dt - utc_now).total_seconds() / 3600)

        if offset_hours == 0:
            return "UTC"
        elif offset_hours in (2, 3):
            return "Europe/EET"
        else:
            raise ValueError(f"Unknown broker timezone offset: {offset_hours}")

    def _get_timeframe(self, spec):
        step = spec.step
        aggregation = spec.aggregation

        timeframe_minutes = {
            self.conn.TIMEFRAME_M1: 1,
            self.conn.TIMEFRAME_M2: 2,
            self.conn.TIMEFRAME_M3: 3,
            self.conn.TIMEFRAME_M4: 4,
            self.conn.TIMEFRAME_M5: 5,
            self.conn.TIMEFRAME_M6: 6,
            self.conn.TIMEFRAME_M10: 10,
            self.conn.TIMEFRAME_M12: 12,
            self.conn.TIMEFRAME_M15: 15,
            self.conn.TIMEFRAME_M20: 20,
            self.conn.TIMEFRAME_M30: 30,
            self.conn.TIMEFRAME_H1: 60,
            self.conn.TIMEFRAME_H2: 120,
            self.conn.TIMEFRAME_H3: 180,
            self.conn.TIMEFRAME_H4: 240,
            self.conn.TIMEFRAME_H6: 360,
            self.conn.TIMEFRAME_H8: 480,
            self.conn.TIMEFRAME_H12: 720,
            self.conn.TIMEFRAME_D1: 1440,
        }

        if aggregation == BarAggregation.MINUTE:
            return timeframe_minutes[step]
        if aggregation == BarAggregation.HOUR:
            return timeframe_minutes[step * 60]
        if aggregation == BarAggregation.DAY:
            return timeframe_minutes[step * 24 * 60]

    def _tick_size_to_precision(self, tick_size: float | Decimal) -> int:
        tick_size_str = f"{tick_size:.10f}"
        return len(tick_size_str.partition(".")[2].rstrip("0"))

    def _parse_mt5_symbol_to_cfd(self, mt5_symbol, index=0):
        size_precision: int = self._tick_size_to_precision(
            mt5_symbol[index].volume_step
        )

        return Cfd(
            instrument_id=InstrumentId(Symbol(mt5_symbol[index][-3]), MT5_VENUE),
            raw_symbol=Symbol(mt5_symbol[index].name),
            asset_class=asset_class_from_str(
                "Fx"
            ),  # TODO: Sperate indicies and forex soon
            quote_currency=Currency.from_str(mt5_symbol[index].currency_profit),
            price_precision=mt5_symbol[index].digits,
            size_precision=size_precision,
            price_increment=Price(
                mt5_symbol[index].trade_tick_size, mt5_symbol[index].digits
            ),
            size_increment=Quantity(mt5_symbol[index].volume_step, size_precision),
            ts_event=mt5_symbol[index].time * 1e9,
            ts_init=mt5_symbol[index].time * 1e9,
            base_currency=Currency.from_str(mt5_symbol[index].currency_base),
            lot_size=None,
            max_quantity=Quantity(mt5_symbol[index].volume_max, size_precision),
            min_quantity=Quantity(mt5_symbol[index].volume_min, size_precision),
            max_notional=None,
            min_notional=None,
            max_price=None,
            min_price=None,
            margin_init=Decimal(0),
            margin_maint=Decimal(0),
            maker_fee=Decimal(0),
            taker_fee=Decimal(0),
            tick_scheme_name=None,
            info=None,
        )

    def _parse_mt5_bar(self, mt5_bar, bar_type: BarType, index=0):
        instrument = self._cache.instrument(bar_type.instrument_id)

        return Bar(
            bar_type=bar_type,
            open=Price(
                mt5_bar[index]["open"].item(),
                instrument.price_precision,
            ),
            high=Price(
                mt5_bar[index]["high"].item(),
                instrument.price_precision,
            ),
            low=Price(
                mt5_bar[index]["low"].item(),
                instrument.price_precision,
            ),
            close=Price(
                mt5_bar[index]["close"].item(),
                instrument.price_precision,
            ),
            volume=Quantity(mt5_bar[index]["tick_volume"].item(), precision=0),
            ts_event=mt5_bar[index]["time"] * 1e9,
            ts_init=mt5_bar[index]["time"] * 1e9,
        )

    def _parse_mt5_deals_to_fill_report(self, mt5_deal, index=0):
        instrument_id = InstrumentId(Symbol(mt5_deal[index][15]), MT5_VENUE)
        instrument = self._cache.instrument(instrument_id)
        order_side = OrderSide.BUY if mt5_deal[index][4] == 0 else OrderSide.SELL

        return FillReport(
            account_id=self._config.account_number,
            instrument_id=instrument_id,
            venue_order_id=mt5_deal[index][0],
            trade_id=mt5_deal[index][1],
            order_side=order_side,
            last_qty=Quantity(mt5_deal[index][9], precision=instrument.size_precision),
            last_px=Money(mt5_deal[index][10], instrument.quote_currency),
            commission=Money(mt5_deal[index][11], instrument.quote_currency),
            liquidity_side=LiquiditySide.NO_LIQUIDITY_SIDE,  # TODO: Detect order type
            report_id=UUID4(),
            ts_event=mt5_deal[index][2] * 1e9,
            ts_init=mt5_deal[index][2] * 1e9,
            client_order_id=None,
            venue_position_id=mt5_deal[index][7],
        )

    def account_info(self):
        try:
            account_info = self.conn.account_info()._asdict()

            return account_info

        except Exception as e:
            self._log.error(f"Failed to get account info: {e}")

    def cache_instrument(self, inst):
        self._cache.add_instrument(inst)
