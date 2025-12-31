from decimal import Decimal

from nautilus_trader.core.nautilus_pyo3 import LogColor
import pandas as pd

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model import Bar, BarType, InstrumentId
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.orders import LimitOrder
from nautilus_trader.trading.strategy import Strategy


class PDHLConfig(StrategyConfig, frozen=True):
    """
    Configuration for ``PDHL`` instances.

    parameters
    ----------
    instrument_id: InstrumentId
        The instrument ID for the strategy.
    bar_type: BarType
        The bar type for the strategy.
    trade_size: Decimal
        The position size per trade.
    subscribe_quote_ticks: bool, [default=False]
        If quotes should be subscribed to.
    order_time_in_force: TimeInForce, [default=TimeInForce.DAY]
        The time in force for strategy market orders.
    close_position_on_stop: bool, [default=False]
        If all open positions should be closed on strategy stop.
    """

    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    subscribe_quote_ticks: bool = False
    order_time_in_force: TimeInForce = TimeInForce.DAY
    close_position_on_stop: bool = False


class PDHL(Strategy):
    """
    An ICT strategy using previous day high and low as liquidity.

    When price reach PDHL level and MSS and close inside PDHL level, then enter a position as reversal direction.
    """

    def __init__(self, config: PDHLConfig) -> None:
        super().__init__(config)

        self.instument: Instrument = None

    # Stateful Actions

    def on_start(self) -> None:
        """
        Actions to be performed on strategy start.
        """
        self.instument = self.cache.instument(self.config.instrument_id)
        if self.instument is None:
            self.log.error(f"Could not find instrument for {self.config.instrument_id}")
            self.stop()
            return

        # Get historical data

        # Subscribe to real-time data
        self.subscribe_bars(self.config.bar_type)

    def on_stop(self) -> None:
        """
        Actions to be performed on strategy stop
        """
        if self.config.unsubscribe_data_on_stop:
            self.unsubscribe_bars(self.config.bar_type)

        if self.config.unsubscribe_data_on_stop and self.config.subscribe_quote_ticks:
            self.unsubscribe_quote_ticks(self.config.instrument_id)

    # Data Handling

    def on_bar(self, bar: Bar) -> None:
        self.log.info(repr(bar), LogColor.CYAN)

    # Order Management

    # Submitting Orders

    def buy(self) -> None:
        order: LimitOrder = self.order_factory.limit(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.BUY,
            quantity=0,  # Lot size calculation
            price=0,  # Displacement price
            time_in_force=self.config.order_time_in_force,
            display_qty=True,
        )

        self.submit_order(order)

    def sell(self) -> None:
        order: LimitOrder = self.order_factory.limit(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.SELL,
            quantity=0,  # Lot size calculation
            price=0,  # Displacement price
            time_in_force=self.config.order_time_in_force,
            display_qty=True,
        )

        self.submit_order(order)

    # Position Management

    # Important Level ICT

    def _pdh(self) -> None:
        pass

    def _pdl(self) -> None:
        pass

    def _bsl(self) -> None:
        pass

    def _ssl(self) -> None:
        pass

    def _mss(self) -> None:
        pass

    def _fvg(self) -> None:
        pass
