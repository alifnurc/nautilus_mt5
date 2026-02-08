import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

from nautilus_trader.model.enums import BarAggregation, asset_class_from_str
from nautilus_trader.model.instruments import Cfd
from pymt5linux import MetaTrader5
from adapters.mt5.config import MT5ClientConfig
from adapters.mt5.constants import MT5_VENUE
from nautilus_trader.model import (
    Bar,
    BarType,
    Currency,
    InstrumentId,
    Price,
    Quantity,
    Symbol,
)
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
        self._cache = {}
        self._subscription = {}

    def initialize(self, config: MT5ClientConfig, msgbus: MessageBus, clock: LiveClock):
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
                size_precision: int = self._tick_size_to_precision(
                    mt5_symbols[i].volume_step
                )
                instruments.append(
                    Cfd(
                        instrument_id=InstrumentId(
                            Symbol(mt5_symbols[i][-3]), MT5_VENUE
                        ),
                        raw_symbol=Symbol(mt5_symbols[i].name),
                        asset_class=asset_class_from_str(
                            "Fx"
                        ),  # TODO: Sperate indicies and forex soon
                        quote_currency=Currency.from_str(
                            mt5_symbols[i].currency_profit
                        ),
                        price_precision=mt5_symbols[i].digits,
                        size_precision=size_precision,
                        price_increment=Price(
                            mt5_symbols[i].trade_tick_size, mt5_symbols[i].digits
                        ),
                        size_increment=Quantity(
                            mt5_symbols[i].volume_step, size_precision
                        ),
                        ts_event=mt5_symbols[i].time * 1e9,
                        ts_init=mt5_symbols[i].time * 1e9,
                        base_currency=Currency.from_str(mt5_symbols[i].currency_base),
                        lot_size=None,
                        max_quantity=Quantity(
                            mt5_symbols[i].volume_max, size_precision
                        ),
                        min_quantity=Quantity(
                            mt5_symbols[i].volume_min, size_precision
                        ),
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
                )

            return instruments
        except Exception as e:
            self._log.error(f"Failed to get instruments: {e}")

    async def subscribe_bars(self, bar_type: BarType):
        try:
            if bar_type in self._subscription:
                return

            self._subscription[bar_type] = asyncio.create_task(
                self._bar_stream_loop(bar_type)
            )

        except Exception as e:
            self._log.error(f"Failed to subscribe bars: {e}")

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
                    Bar(
                        bar_type=bar_type,
                        open=Price(
                            mt5_bars[i]["open"].item(),
                            self._cache[symbol].price_precision,
                        ),
                        high=Price(
                            mt5_bars[i]["high"].item(),
                            self._cache[symbol].price_precision,
                        ),
                        low=Price(
                            mt5_bars[i]["low"].item(),
                            self._cache[symbol].price_precision,
                        ),
                        close=Price(
                            mt5_bars[i]["close"].item(),
                            self._cache[symbol].price_precision,
                        ),
                        volume=Quantity(mt5_bars[i]["tick_volume"].item(), precision=0),
                        ts_event=mt5_bars[i]["time"] * 1e9,
                        ts_init=mt5_bars[i]["time"] * 1e9,
                    )
                )

            return bars
        except Exception as e:
            self._log.error(f"Failed to request bars: {e}")

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

                bar = Bar(
                    bar_type=bar_type,
                    open=Price(
                        mt5_bar[0]["open"].item(),
                        self._cache[symbol].price_precision,
                    ),
                    high=Price(
                        mt5_bar[0]["high"].item(),
                        self._cache[symbol].price_precision,
                    ),
                    low=Price(
                        mt5_bar[0]["low"].item(),
                        self._cache[symbol].price_precision,
                    ),
                    close=Price(
                        mt5_bar[0]["close"].item(),
                        self._cache[symbol].price_precision,
                    ),
                    volume=Quantity(mt5_bar[0]["tick_volume"].item(), precision=0),
                    ts_event=mt5_bar[0]["time"] * 1e9,
                    ts_init=mt5_bar[0]["time"] * 1e9,
                )
                if mt5_bar is not None:
                    self._msgbus.publish(topic, bar)

                await asyncio.sleep(1)
        except Exception as e:
            self._log.error(f"Failed to stream bar: {e}")

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

    def account_info(self):
        try:
            account_info = self.conn.account_info()._asdict()

            return account_info

        except Exception as e:
            self._log.error(f"Failed to get account info: {e}")

    def cache_instrument(self, inst: Cfd):
        self._cache[inst.raw_symbol] = inst
