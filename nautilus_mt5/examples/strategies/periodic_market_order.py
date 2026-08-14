from datetime import timedelta
from decimal import Decimal
from nautilus_trader.common.enums import LogColor
from nautilus_trader.core import Event
from nautilus_trader.model import Bar, BarType, Position, Price
from nautilus_trader.model.enums import OrderSide, PositionSide
from nautilus_trader.model.events import PositionClosed, PositionOpened
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy, StrategyConfig


class PeriodicMarketOrderConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    request_bars: bool = True
    order_side: OrderSide = OrderSide.BUY
    order_quantity: Decimal = Decimal("0.01")
    order_interval_seconds: int = 10


class PeriodicMarketOrderStrategy(Strategy):
    def __init__(self, config: PeriodicMarketOrderConfig):
        super().__init__(config)

        self.instrument_id = config.instrument_id
        self.order_side = (
            OrderSide.BUY if config.order_side is OrderSide.BUY else OrderSide.SELL
        )
        self.order_quantity = Quantity(config.order_quantity, 0)
        self.order_interval_seconds = config.order_interval_seconds
        self.position: Position | None = None

    def on_start(self):
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Could not find instrument for {self.config.instrument_id}")
            self.stop()
            return

        self.subscribe_bars(self.config.bar_type)

        self.log.info(
            f"Strategy started. Send order for every {self.order_interval_seconds} seconds."
        )

        self.clock.set_timer(
            name=f"periodic_order_timer",
            interval=timedelta(seconds=self.order_interval_seconds),
            callback=self.send_market_order,
        )

    def on_instrument(self, instrument: Instrument):
        self.log.info(
            f"Instrument: {instrument} and self.instrument: {self.instrument}",
            LogColor.BLUE,
        )

    def on_bar(self, bar: Bar) -> None:
        if bar.is_single_price():
            self.log.warning("Bar OHLC is single price; implies no market information")

        self.last_bar = bar

    def on_event(self, event: Event):
        if isinstance(event, PositionOpened):
            self.position = self.cache.position(event.position_id)
            self.log.info(
                f"Position opened: {self.position.side} @ {self.position.avg_px_open}"
            )

            # Place stop-loss and take-profit
            self.place_exit_orders()
        elif isinstance(event, PositionClosed):
            if self.position and self.position.id == event.position_id:
                pnl = self.position.realized_pnl
                self.log.info(f"Position closed with PnL: {pnl}")

                # Cancel any remaining exit orders

    def send_market_order(self, timestamp_ns: int):
        instrument = self.cache.instrument(self.instrument_id)
        if not instrument:
            self.log.error(f"Instrument {self.instrument_id} not found in cache.")
            return

        current_price = self.last_bar.close
        pip_size = instrument.price_increment * 10

        tp_price = current_price + (pip_size * 15)
        sl_price = current_price - (pip_size * 5)

        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=self.order_side,
            quantity=self.order_quantity,
        )

        self.submit_order(
            order,
            params={"take_profit": tp_price, "stop_loss": sl_price},
        )

        self.log.info(
            f"Submitted order price: {current_price}, TP: {tp_price} and SL: {sl_price}"
        )

    def place_exit_orders(self):
        if not self.position:
            return

        entry_price = float(self.position.avg_px_open)
        pip_value = 0.0001

        if self.position.side == PositionSide.LONG:
            stop_price = entry_price - (10 * pip_value)
            target_price = entry_price + (20 * pip_value)

            stop_loss = self.order_factory.stop_market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=self.order_quantity,
                trigger_price=Price.from_str(f"{stop_price:.5f}"),
            )
            self.submit_order(stop_loss)

            take_profit = self.order_factory.limit(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=self.order_quantity,
                trigger_price=Price.from_str(f"{stop_price:.5f}"),
            )
            self.submit_order(take_profit)

            self.log.info(
                f"Placed LONG exit orders - Stop: {stop_price:.5f}, Target: {target_price:.5f}"
            )

    def on_stop(self):
        self.clock.cancel_timer("periodic_order_timer")
        self.log.info("Strategy stopped.")
