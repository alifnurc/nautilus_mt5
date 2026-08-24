from decimal import Decimal

from nautilus_trader.core.nautilus_pyo3 import TimeEvent
from nautilus_trader.model import Bar, BarType, Position, Quantity
from nautilus_trader.model.events import OrderAccepted
from nautilus_trader.model.orders import LimitOrder
from nautilus_trader.trading.strategy import StrategyConfig, Strategy
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
import pandas


class LimitOrderConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    request_bars: bool = True
    order_side: OrderSide = OrderSide.BUY
    order_quantity: Decimal = Decimal("1000")


class LimitOrderStrategy(Strategy):
    def __init__(self, config: LimitOrderConfig) -> None:
        super().__init__(config)

        self.instrument_id = config.instrument_id
        self.order_side = config.order_side
        self.order_quantity = Quantity(config.order_quantity, 0)
        self.position: Position | None = None
        self.last_bar: Bar | None = None

    def on_start(self):
        self.instrument = self.cache.instrument(self.config.instrument_id)
        alert_time = self.clock.utc_now() + pandas.Timedelta(seconds=10)
        if self.instrument is None:
            self.log.error(f"Could not find instrument for {self.config.instrument_id}")
            self.stop()
            return

        self.subscribe_bars(self.config.bar_type)

        self.log.info(f"Strategy started. Limit Order will execute on {alert_time}.")

        self.clock.set_time_alert(
            name=f"limit_order",
            alert_time=alert_time,
            callback=self.send_limit_order,
        )

        self.log.info("Time alert successfully")

    def on_bar(self, bar: Bar) -> None:
        if bar.is_single_price():
            self.log.warning("Bar OHLC is single price; implies no market information")

        self.last_bar = bar

    def send_limit_order(self, event: TimeEvent):
        instrument = self.cache.instrument(self.instrument_id)
        if not instrument:
            self.log.error(f"Instrument {self.instrument_id} not found in cache.")
            return

        if self.last_bar is None:
            self.log.error(f"No bar received yet, skip sending order.")
            return

        current_price = self.last_bar.close
        pip_size = instrument.price_increment * 10

        self.log.warning(f"Current price: {current_price}")

        if self.order_side is OrderSide.BUY:
            order_price = current_price - (pip_size * 10)
            tp_price = order_price + (pip_size * 15)
            sl_price = order_price - (pip_size * 5)
        else:
            order_price = current_price + (pip_size * 10)
            tp_price = order_price - (pip_size * 15)
            sl_price = order_price + (pip_size * 5)

        order: LimitOrder = self.order_factory.limit(
            instrument_id=self.instrument_id,
            order_side=self.order_side,
            quantity=self.order_quantity,
            price=instrument.make_price(order_price),
            time_in_force=TimeInForce.DAY,
        )

        self.submit_order(
            order,
            params={"take_profit": tp_price, "stop_loss": sl_price},
        )

        self.log.info(
            f"Submitted order price: {order_price}, TP: {tp_price}, SL: {sl_price}"
        )

    def on_order_accepted(self, event: OrderAccepted) -> None:
        self.log.info(f"Order: {event}")
        self.log.info(f"Open Order: {self.cache.orders()}")

    def on_stop(self):
        self.log.info("Strategy stopped")
