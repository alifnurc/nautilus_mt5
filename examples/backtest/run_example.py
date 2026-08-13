import datetime
from pathlib import Path

from nautilus_trader.config import (
    BacktestEngineConfig,
    LoggingConfig,
)
from nautilus_trader.analysis import create_tearsheet
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.model import Money, TraderId
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from strategies.asia_killzone import AsiaKillZone, AsiaKillZoneConfig
import pytz

if __name__ == "__main__":
    CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog"
    catalog = ParquetDataCatalog(CATALOG_PATH)
    instrument = catalog.instruments()[0]  # EURUSDm.MT5

    timezone = pytz.timezone("UTC")
    start = datetime.datetime(2025, 3, 1, tzinfo=timezone)
    end = datetime.datetime(2025, 3, 31, 23, 59, tzinfo=timezone)

    bid_bars = catalog.bars(
        bar_types=[f"{instrument.id}-1-MINUTE-BID-EXTERNAL"], start=start, end=end
    )
    ask_bars = catalog.bars(
        bar_types=[f"{instrument.id}-1-MINUTE-ASK-EXTERNAL"], start=start, end=end
    )

    engine_config = BacktestEngineConfig(
        trader_id=TraderId("BACKTEST_TRADER-001"),
        logging=LoggingConfig(
            log_level="DEBUG",
            log_component_levels={
                "OrderMatchingEngine(MT5)": "INFO",
            },
        ),
    )
    engine = BacktestEngine(config=engine_config)

    engine.add_venue(
        venue=instrument.id.venue,
        oms_type=OmsType.HEDGING,
        account_type=AccountType.MARGIN,
        base_currency=USD,
        starting_balances=[Money(10_000, USD)],
    )

    engine.add_instrument(instrument)
    engine.add_data(bid_bars)
    engine.add_data(ask_bars)

    strategy_config = AsiaKillZoneConfig(
        instrument_id=instrument.id, close_position_on_stop=True
    )
    strategy = AsiaKillZone(config=strategy_config)
    engine.add_strategy(strategy)

    engine.run()

    RESULT_DIR = CATALOG_PATH / "backtest_results.html"
    create_tearsheet(engine=engine, output_path=RESULT_DIR)
    engine.dispose()
