#!/usr/bin/env python3

import pandas as pd
import zipfile
import requests

from decimal import Decimal
from pathlib import Path
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.data.aggregation import ValueBarAggregator
from nautilus_trader.model import BarType, Money, TraderId, Venue
from nautilus_trader.model.enums import AccountType, OmsType, BarAggregation, PriceType
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import BarSpecification
from nautilus_trader.persistence.wranglers import QuoteTickDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.examples.strategies.ema_cross import EMACross, EMACrossConfig


def download(url: str) -> None:
    filename = url.rsplit("/", maxsplit=1)[1]

    with open(filename, "wb") as f:
        f.write(requests.get(url).content)


if __name__ == "__main__":
    # Step 1: Configure and create backtest engine
    engine_config = BacktestEngineConfig(
        trader_id=TraderId("BACKTEST_TRADER-001"),
        logging=LoggingConfig(log_level="INFO"),
    )
    engine = BacktestEngine(config=engine_config)

    # Step 2: Define exchange and add it to the engine
    EXNESS = Venue("exness")
    engine.add_venue(
        venue=EXNESS,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money(1_000_000, USD)],
        base_currency=USD,
        default_leverage=Decimal(1),  # No leverage
    )

    # Step 3: Create instrument definition and add it to the engine
    EURUSD_INSTRUMENT = TestInstrumentProvider.default_fx_ccy(
        symbol="EUR/USD", venue=EXNESS
    )
    engine.add_instrument(EURUSD_INSTRUMENT)

    # Step 3a: Download CSV file
    download(
        "https://ticks.ex2archive.com/ticks/EURUSDc/2025/09/Exness_EURUSDc_2025_09.zip"
    )

    with zipfile.ZipFile("Exness_EURUSDc_2025_09.zip", "r") as zip_ref:
        zip_ref.extractall(Path(__file__).parent)

    # Step 4a: Load bar data from CSV file -> into pandas DataFrame
    csv_file_path = r"Exness_EURUSDc_2025_09.csv"
    df = pd.read_csv(
        csv_file_path,
        index_col=False,
        header=0,
        sep=",",
        decimal=".",
        names=["Exness", "Symbol", "Timestamp", "Bid", "Ask"],
        usecols=["Timestamp", "Bid", "Ask"],
        na_values=["", "NULL", "NaN", "N/A"],
    )

    # Step 4b: Restructur DataFrame into required structure
    # Convert string timestamps into datetime
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="ISO8601")
    # Rename column to required name
    df = df.rename(
        columns={"Timestamp": "timestamp", "Bid": "bid_price", "Ask": "ask_price"}
    )
    # Seet column `Timestamp` as index
    df = df.set_index("timestamp")

    # Step 4c: Process quotes using a wrangler
    wrangler = QuoteTickDataWrangler(instrument=EURUSD_INSTRUMENT)
    ticks = wrangler.process(df)

    handler = []
    bar_spec = BarSpecification(15, BarAggregation.MINUTE, PriceType.BID)
    bar_type = BarType(EURUSD_INSTRUMENT.id, bar_spec)
    aggregator = ValueBarAggregator(
        EURUSD_INSTRUMENT,
        bar_type,
        handler.append,
    )

    for tick in ticks:
        aggregator.handle_quote_tick(tick)

    # Step 4d: Add loaded data to the engine
    engine.add_data(aggregator)

    # Step 5: Create strategy and add it to engine
    config = EMACrossConfig(
        instrument_id=EURUSD_INSTRUMENT.id,
        bar_type=BarType.from_str(f"{EURUSD_INSTRUMENT.id}-15-MINUTE-MID-EXTERNAL"),
        fast_ema_period=10,
        slow_ema_period=20,
        trade_size=Decimal(10_000),
    )

    strategy = EMACross(config=config)
    engine.add_strategy(strategy=strategy)

    # Step 6: Run engine = Run backtest
    engine.run()

    # Step 7: Release system resources
    engine.dispose()
