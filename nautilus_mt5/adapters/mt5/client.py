import asyncio
import pandas as pd
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

from nautilus_trader.core import UUID4
from nautilus_trader.execution.reports import FillReport, OrderStatusReport
from nautilus_trader.model.enums import (
    BarAggregation,
    LiquiditySide,
    OrderSide,
    TimeInForce,
    asset_class_from_str,
)
from nautilus_trader.model.instruments import Cfd
from pymt5linux import MetaTrader5
from nautilus_mt5.adapters.mt5.config import MT5ClientConfig
from nautilus_mt5.adapters.mt5.constants import MT5_VENUE
from nautilus_trader.model import (
    Bar,
    BarType,
    Currency,
    InstrumentId,
    Money,
    Price,
    Quantity,
    Symbol,
    TradeId,
    VenueOrderId,
)
from nautilus_trader.model.events import OrderAccepted, OrderFilled, OrderRejected
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
                    self._parse_mt5_symbol_to_cfd(mt5_symbol=mt5_symbols[i])
                )

            return instruments
        except Exception as e:
            self._log.error(f"Failed to get instruments: {e}")

    async def subscribe_bars(self, bar_type: BarType):
        if bar_type in self._subscription:
            return

        self._subscription[bar_type] = asyncio.create_task(
            self._bar_stream_loop(bar_type=bar_type)
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
        timeframe = self._get_timeframe(spec=spec)

        self._log.debug(
            f"Bar request args: {bar_type}, {start}, {end}, {limit}, {partial}"
        )

        try:
            mt5_bars = await loop.run_in_executor(
                self.executor,
                lambda: self.conn.copy_rates_range(
                    symbol=symbol, timeframe=timeframe, date_from=start, date_to=end
                ),
            )

            bars: list[Bar] = []
            for i in range(len(mt5_bars)):
                bars.append(
                    self._parse_mt5_bar(mt5_bar=mt5_bars[i], bar_type=bar_type[i])
                )

            return bars
        except Exception as e:
            self._log.error(f"Failed to request bars: {e}")

    async def subscribe_orders(self):
        self._subscription["orders"] = asyncio.create_task(self._orders_stream_loop())

    async def subscribe_executions(self):
        self._subscription["executions"] = asyncio.create_task(
            self._executions_stream_loop()
        )

    async def unsubscribe_orders(self):
        try:
            self._subscription.pop("orders").cancel()
        except Exception as e:
            self._log.error(f"Failed to unsubscribe orders: {e}")

    async def unsubscribe_executions(self):
        try:
            self._subscription.pop("executions").cancel()
        except Exception as e:
            self._log.error(f"Failed to unsubscribe executions: {e}")

    async def _bar_stream_loop(self, bar_type: BarType):
        loop = asyncio.get_event_loop()

        # Get bar specification
        spec = bar_type.spec
        symbol = bar_type.instrument_id.symbol
        timeframe = self._get_timeframe(spec=spec)
        topic = f"data.bars.{bar_type}"

        try:
            while True:
                mt5_bar = await loop.run_in_executor(
                    self.executor,
                    lambda: self.conn.copy_rates_from_pos(
                        symbol=symbol, timeframe=timeframe, start_pos=0, count=1
                    ),
                )

                bar = self._parse_mt5_bar(mt5_bar=mt5_bar[0], bar_type=bar_type)
                if mt5_bar is not None:
                    self._msgbus.publish(topic, bar)

                await asyncio.sleep(1)
        except Exception as e:
            self._log.error(f"Failed to subscribe bars: {e}")

    async def _orders_stream_loop(self):
        loop = asyncio.get_event_loop()

        topic = f"events.order"

        try:
            while True:
                mt5_orders = await loop.run_in_executor(
                    self.executor, self.conn.orders_get
                )

                if mt5_orders is not None:
                    orders: list = []
                    for i in range(len(mt5_orders)):
                        orders.append(self._parse_mt5_order(mt5_order=mt5_orders[i]))
                    self._msgbus.publish(topic, orders)
        except Exception as e:
            self._log.error(f"Failed to subscribe orders: {e}")

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
                    lambda: self.conn.history_deals_get(
                        date_from=date_from, date_to=date_to
                    ),
                )

                if mt5_deals is not None:
                    deals: list[FillReport] = []
                    for i in range(len(mt5_deals)):
                        deals.append(
                            self._parse_mt5_deals_to_fill_report(mt5_deal=mt5_deals[i])
                        )
                    self._msgbus.publish(topic, deals)

                await asyncio.sleep(1)
        except Exception as e:
            self._log.error(f"Failed to subscribe orders: {e}")

    async def request_order_status_reports(
        self, instrument_id: InstrumentId, open_only, limit
    ) -> list[OrderStatusReport]:
        self._log.debug(
            f"Request_order_status_reports args: {instrument_id}, {open_only}, {limit}"
        )

        try:
            pass
        except Exception as e:
            self._log.error(f"Failed to request order status reports: {e}")

    async def request_fill_reports(
        self, instrument_id: InstrumentId, limit
    ) -> list[FillReport]:
        self._log.debug(f"Request_fill_reports args: {instrument_id}, {limit}")

        try:
            pass
        except Exception as e:
            self._log.error(f"Failed to request fill reports: {e}")

    async def request_position_status_reports(self) -> list:
        try:
            pass
        except Exception as e:
            self._log.error(f"Failed to request position status reports: {e}")

    async def submit_order(
        self,
        command,
        msg_handler,
    ):
        loop = asyncio.get_event_loop()
        price = command.order.price if command.order.has_price else None
        tp_price = command.params.get("take_profit")
        sl_price = command.params.get("stop_loss")

        request = self._parse_order_request(
            instrument_id=command.order.instrument_id,
            order_side=command.order.side,
            order_type=command.order.order_type,
            quantity=command.order.quantity,
            time_in_force=command.order.time_in_force,
            price=price,
            tp_price=tp_price,
            sl_price=sl_price,
        )

        self._log.debug(f"MT5_Order_request args: {request}")

        try:
            mt5_order = await loop.run_in_executor(
                self.executor, lambda: self.conn.order_send(request=request)
            )

            if mt5_order is None:
                code, msg = self.conn.last_error()
                raise RuntimeError(code, msg)

            if mt5_order.retcode not in (
                self.conn.TRADE_RETCODE_DONE,
                self.conn.TRADE_RETCODE_DONE_PARTIAL,
                self.conn.TRADE_RETCODE_PLACED,
            ):
                msg_handler(
                    OrderRejected(
                        trader_id=command.order.trader_id,
                        strategy_id=command.order.strategy_id,
                        instrument_id=command.order.instrument_id,
                        client_order_id=command.order.client_order_id,
                        account_id=command.order.account_id,
                        reason=mt5_order.comment,
                        event_id=UUID4(),
                        ts_event=self._clock.timestamp_ns(),
                        ts_init=self._clock.timestamp_ns(),
                    )
                )

                return
            msg_handler(
                OrderAccepted(
                    trader_id=command.order.trader_id,
                    strategy_id=command.order.strategy_id,
                    instrument_id=command.order.instrument_id,
                    client_order_id=command.order.client_order_id,
                    venue_order_id=VenueOrderId(str(mt5_order.order)),
                    account_id=command.order.account_id,
                    event_id=UUID4(),
                    ts_event=self._clock.timestamp_ns(),
                    ts_init=self._clock.timestamp_ns(),
                )
            )

            if request.get("action") is self.conn.TRADE_ACTION_DEAL:
                msg_handler(
                    OrderFilled(
                        trader_id=command.order.trader_id,
                        strategy_id=command.order.strategy_id,
                        instrument_id=command.order.instrument_id,
                        client_order_id=command.order.client_order_id,
                        venue_order_id=VenueOrderId(str(mt5_order.order)),
                        account_id=command.order.account_id,
                        trade_id=TradeId(str(mt5_order.order)),
                        position_id=None,
                        order_side=command.order.side,
                        order_type=command.order.order_type,
                        last_qty=Quantity(
                            mt5_order.volume
                            * self._cache.instrument(
                                command.order.instrument_id
                            ).lot_size,
                            0,
                        ),
                        last_px=Price(
                            mt5_order.price,
                            self._cache.instrument(
                                command.order.instrument_id
                            ).price_precision,
                        ),
                        currency=self._cache.instrument(
                            command.order.instrument_id
                        ).base_currency,
                        commission=Money(
                            0,
                            self._cache.instrument(
                                command.order.instrument_id
                            ).base_currency,
                        ),
                        liquidity_side=LiquiditySide.TAKER,
                        event_id=UUID4(),
                        ts_event=self._clock.timestamp_ns(),
                        ts_init=self._clock.timestamp_ns(),
                        info=None,
                    )
                )
        except Exception as e:
            self._log.error(f"Failed to submit order: {e}")

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

    def _parse_mt5_symbol_to_cfd(self, mt5_symbol):
        size_precision: int = self._tick_size_to_precision(
            tick_size=mt5_symbol.volume_step
        )
        # unparsed_fields = ("path")
        # info = {f: getattr(mt5_symbol, f) for f in unparsed_fields}

        return Cfd(
            instrument_id=InstrumentId(Symbol(mt5_symbol.name), MT5_VENUE),
            raw_symbol=Symbol(mt5_symbol.name),
            asset_class=asset_class_from_str(
                "Fx"
            ),  # TODO: Sperate indicies and forex soon
            quote_currency=Currency.from_str(mt5_symbol.currency_profit),
            price_precision=mt5_symbol.digits,
            size_precision=size_precision,
            price_increment=Price(mt5_symbol.trade_tick_size, mt5_symbol.digits),
            size_increment=Quantity(mt5_symbol.volume_step, size_precision),
            ts_event=mt5_symbol.time * 1e9,
            ts_init=mt5_symbol.time * 1e9,
            base_currency=Currency.from_str(mt5_symbol.currency_base),
            lot_size=Quantity(mt5_symbol.trade_contract_size, 0),
            max_quantity=Quantity(
                mt5_symbol.trade_contract_size * mt5_symbol.volume_max, size_precision
            ),
            min_quantity=Quantity(
                mt5_symbol.trade_contract_size * mt5_symbol.volume_min, size_precision
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

    def _parse_mt5_bar(self, mt5_bar, bar_type: BarType):
        instrument = self._cache.instrument(bar_type.instrument_id)
        size_precision = instrument.size_precision

        return Bar(
            bar_type=bar_type,
            open=Price(
                mt5_bar["open"].item(),
                instrument.price_precision,
            ),
            high=Price(
                mt5_bar["high"].item(),
                instrument.price_precision,
            ),
            low=Price(
                mt5_bar["low"].item(),
                instrument.price_precision,
            ),
            close=Price(
                mt5_bar["close"].item(),
                instrument.price_precision,
            ),
            volume=Quantity(mt5_bar["tick_volume"].item(), precision=size_precision),
            ts_event=mt5_bar["time"] * 1e9,
            ts_init=mt5_bar["time"] * 1e9,
        )

    def _parse_order_request(
        self,
        instrument_id,
        order_side,
        order_type,
        quantity,
        time_in_force,
        price,
        tp_price,
        sl_price,
    ):
        order_request = {}

        if order_type == 1:  # market order
            order_request["action"] = self.conn.TRADE_ACTION_DEAL
            order_request["type"] = (
                self.conn.ORDER_TYPE_BUY
                if order_side == 1
                else self.conn.ORDER_TYPE_SELL
            )
        if order_type == 2:  # limit order
            order_request["action"] = self.conn.TRADE_ACTION_PENDING
            order_request["type"] = (
                self.conn.ORDER_TYPE_BUY_LIMIT
                if order_side == 1
                else self.conn.ORDER_TYPE_SELL_LIMIT
            )
        if order_type == 3:  # stop market order
            order_request["action"] = self.conn.TRADE_ACTION_PENDING
            order_request["type"] = (
                self.conn.ORDER_TYPE_BUY_STOP
                if order_side == 1
                else self.conn.ORDER_TYPE_SELL_STOP
            )
        if order_type == 4:  # stop limit order
            order_request["action"] = self.conn.TRADE_ACTION_PENDING
            order_request["type"] = (
                self.conn.ORDER_TYPE_BUY_STOP_LIMIT
                if order_side == 1
                else self.conn.ORDER_TYPE_SELL_STOP_LIMIT
            )
        if price is not None:
            order_request["price"] = float(price)
        if tp_price is not None:
            order_request["tp"] = float(tp_price)
        if sl_price is not None:
            order_request["sl"] = float(sl_price)

        order_request["symbol"] = str(instrument_id.symbol)
        order_request["volume"] = float(
            quantity / self._cache.instrument(instrument_id).lot_size
        )
        order_request["expiration"] = self._parse_time_in_force(
            time_inforce=time_in_force
        )

        return order_request

    def _parse_time_in_force(self, time_inforce: TimeInForce):
        if time_inforce is TimeInForce.GTC:
            return self.conn.ORDER_TIME_GTC
        if time_inforce is TimeInForce.DAY:
            return self.conn.ORDER_TIME_DAY
        if time_inforce is TimeInForce.GTD:
            return self.conn.ORDER_TIME_SPECIFIED_DAY

    def _parse_mt5_order(self, mt5_order):
        return

    def _parse_mt5_deals_to_fill_report(self, mt5_deal):
        instrument_id = InstrumentId(Symbol(mt5_deal[15]), MT5_VENUE)
        instrument = self._cache.instrument(instrument_id)
        order_side = OrderSide.BUY if mt5_deal[4] == 0 else OrderSide.SELL

        return FillReport(
            account_id=self._config.account_number,
            instrument_id=instrument_id,
            venue_order_id=mt5_deal[0],
            trade_id=mt5_deal[1],
            order_side=order_side,
            last_qty=Quantity(mt5_deal[9], precision=instrument.size_precision),
            last_px=Money(mt5_deal[10], instrument.quote_currency),
            commission=Money(mt5_deal[11], instrument.quote_currency),
            liquidity_side=LiquiditySide.NO_LIQUIDITY_SIDE,  # TODO: Detect order type
            report_id=UUID4(),
            ts_event=mt5_deal[2] * 1e9,
            ts_init=mt5_deal[2] * 1e9,
            client_order_id=None,
            venue_position_id=mt5_deal[7],
        )

    def account_info(self):
        try:
            account_info = self.conn.account_info()._asdict()

            return account_info

        except Exception as e:
            self._log.error(f"Failed to get account info: {e}")

    def cache_instrument(self, inst):
        self._cache.add_instrument(inst)
