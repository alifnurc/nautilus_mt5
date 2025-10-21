import pandas as pd

from decimal import Decimal
from nautilus_trader.common.enums import LogColor
from nautilus_trader.model import Bar, BarType, InstrumentId, Position, QuoteTick
from nautilus_trader.trading.strategy import Strategy, StrategyConfig


class PDHLConfig(StrategyConfig):
    instrument_id: InstrumentId
    risk_per_trade: Decimal


class PDHLStrategy(Strategy):
    def __init__(
        self,
        config: PDHLConfig,
    ):
        super().__init__()

        self.instrument_id = config.instrument_id
        self.risk_per_trade = Decimal(config.risk_per_trade)

        # Trading states
        self.position: Position | None = None
        self.entry_price: float | None = None
        self.pdh: float | None = None
        self.pdl: float | None = None
        self.pdhl_is_taken: bool = False

    def on_start(self):
        # Create 15-minute bars from BID prices (in QuoteTick objects)
        bar_type = BarType.from_str(f"{self.instrument_id}-15-MINUTE-BID-EXTERNAL")

        # Request historical data and subscribe to live data
        self.request_bars(bar_type, start=self.clock.utc_now() - pd.Timedelta(days=1))
        self.subscribe_bars(bar_type)

    def on_stop(self):
        self.log.info("Strategy stopped")

    def on_bar(self, bar: Bar):
        self.log.info(
            f"Received bar - Type: {bar.bar_type}, Instrument: {bar.instrument_id}"
        )
        self.log.info(repr(bar), LogColor.CYAN)
        # if bar.instrument_id != self.instrument_id:
        #     return

        self.log.info(f"Bar: {bar.open}, {bar.high}, {bar.low}, {bar.close}")

    def on_quote_tick(self, tick: QuoteTick):
        self.log.info(f"Received quote tick: {tick}, Instrument: {tick.instrument_id}")

    def on_order_filled(self, filled_order):
        self.position = self.cache.position_for_order(filled_order.client_order_id)

        if self.position:
            self.entry_price = float(self.position.avg_px_open)
            self.log.info(f"Position opened: {self.position}")
