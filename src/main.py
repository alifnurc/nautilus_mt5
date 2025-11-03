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

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def download(url: str, save_dir: Path | str, filename: str | None = None) -> Path:
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = url.rsplit("/", maxsplit=1)[1]

    save_path = save_dir / filename

    response = requests.get(url)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        f.write(requests.get(url).content)

    return save_path


if __name__ == "__main__":
    # Step 1: Download the datatick
    url = (
        "https://ticks.ex2archive.com/ticks/EURUSDc/2025/09/Exness_EURUSDc_2025_09.zip"
    )
    save_path = DATA_DIR / "dataticks"
    download(url, save_path)

    # Step 2: Extract downloaded datatick
    with zipfile.ZipFile(save_path / "Exness_EURUSDc_2025_09.zip", "r") as zip_ref:
        zip_ref.extractall(save_path)

    # Step 3: Configure and create backtest engine
    engine_config = BacktestEngineConfig(
        trader_id=TraderId("BACKTEST_TRADER-001"),
        logging=LoggingConfig(log_level="DEBUG"),
    )
    engine = BacktestEngine(config=engine_config)

    # Step 4: Define exchange and add it to the engine
    EXNESS = Venue("exness")
    engine.add_venue(
        venue=EXNESS,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money(1_000_000, USD)],
        base_currency=USD,
        default_leverage=Decimal(1),  # No leverage
    )

    # Step 5: Create instrument definition and add it to the engine
    EURUSD_INSTRUMENT = TestInstrumentProvider.default_fx_ccy(
        symbol="EUR/USD", venue=EXNESS
    )
    engine.add_instrument(EURUSD_INSTRUMENT)

    # Step 6a: Load bar data from CSV file -> into pandas DataFrame
    csv_file_path = save_path / r"Exness_EURUSDc_2025_09.csv"
    df = pd.read_csv(csv_file_path, sep=",", decimal=".", header=0, index_col=False)

    # Step 6b: Restructure DataFrame into required structure, that can be bassed `BarDataWrangler`
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

    # Step 6c: Define type of loaded bars
    EURUSD_15MIN_BARTYPE = BarType.from_str(
        f"{EURUSD_INSTRUMENT.id}-15-MINUTE-MID-EXTERNAL",
    )

    # Step 6d: `BarDataWrangler` converts each row object of type `Bar`
    wrangler = BarDataWrangler(EURUSD_15MIN_BARTYPE, EURUSD_INSTRUMENT)
    eurusdc_15min_bars_list: list[Bar] = wrangler.process(ohlc_df_clean)

    # Step 6e: Add loaded data to the engine
    engine.add_data(eurusdc_15min_bars_list)

    # Step 7: Create strategy and add it to engine
    config = EMACrossConfig(
        instrument_id=EURUSD_INSTRUMENT.id,
        bar_type=BarType.from_str(f"{EURUSD_INSTRUMENT.id}-15-MINUTE-MID-EXTERNAL"),
        fast_ema_period=10,
        slow_ema_period=20,
        trade_size=Decimal(10_000),
    )

    strategy = EMACross(config=config)
    engine.add_strategy(strategy=strategy)

    # Step 8: Run engine = Run backtest
    engine.run()

    # Generating reports
    engine.trader.generate_account_report(EXNESS)
    engine.trader.generate_order_fills_report()
    engine.trader.generate_positions_report()

    # Step 9: Release system resources
    engine.dispose()
