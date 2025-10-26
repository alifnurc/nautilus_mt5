#!/usr/bin/env python3

from decimal import Decimal
from pathlib import Path

import pandas as pd
import zipfile
import requests

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.examples.strategies.ema_cross import EMACross, EMACrossConfig
from nautilus_trader.model import Bar, BarType, Money, TraderId, Venue
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.currencies import USD
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider


def download(url: str) -> None:
    filename = url.rsplit("/", maxsplit=1)[1]

    with open(filename, "wb") as f:
        f.write(requests.get(url).content)


if __name__ == "__main__":
    # Step 1: Configure and create backtest engine
    engine_config = BacktestEngineConfig(
        trader_id=TraderId("BACKTEST_TRADER-001"),
        logging=LoggingConfig(log_level="DEBUG"),
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
    df = pd.read_csv(csv_file_path, sep=",", decimal=".", header=0, index_col=False)

    # Step 4b: Restructure DataFrame into required structure, that can be bassed `BarDataWrangler`
    #   -   5 columns: 'open', 'high', 'low', 'close', 'volume'
    #   -   'timestamp' as index

    # Convert string timestamps into datetime
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="ISO8601")
    # Seet column `timestamp` as index
    df = df.set_index("Timestamp")
    # MID price for OHLC
    df["Mid"] = (df["Bid"] + df["Ask"]) / 2

    ohlc_df = (
        df["Mid"]
        .resample("15min")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    )
    # Add volume
    ohlc_df["volume"] = df.resample("15min").size()

    # Remove volume = 0 (no data tick in that periode)
    ohlc_df_clean = ohlc_df[ohlc_df["volume"] > 0].copy()

    # Step 4c: Define type of loaded bars
    EURUSD_15MIN_BARTYPE = BarType.from_str(
        f"{EURUSD_INSTRUMENT.id}-15-MINUTE-MID-EXTERNAL",
    )

    # Step 4d: `BarDataWrangler` converts each row object of type `Bar`
    wrangler = BarDataWrangler(EURUSD_15MIN_BARTYPE, EURUSD_INSTRUMENT)
    eurusdc_15min_bars_list: list[Bar] = wrangler.process(ohlc_df_clean)

    # Step 4e: Add loaded data to the engine
    engine.add_data(eurusdc_15min_bars_list)

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

    # Generating reports
    engine.trader.generate_account_report(EXNESS)
    engine.trader.generate_order_fills_report()
    engine.trader.generate_positions_report()

    # Step 7: Release system resources
    engine.dispose()
