# Backtest Session

NautilusTrader backtest using your own broker data.

## What this is?

```bash
examples/backtest/
├── fetch_data.py # Download script for fetch data throught MetaTrader5 API
├── README.md
└── run_example.py # Backtest script for testing your strategy

```

# Quick start

After following [initialization](../../README.md), you can moving forward to the next step

### Fetch data using `fetch_data.py`

You can use data directly from your own broker for backtesting trought MetaTrader5 API using this script.

```python
CATALOG_PATH = Path(__file__).resolve().parent / "data" / "catalog"
catalog = ParquetDataCatalog(CATALOG_PATH)

...
# Parse MetaTrader5 instrument symbol to Cfd object
instrument = _parse_mt5_symbol_to_cfd(mt5.symbol_info(symbol), mt5.account_info())

# Parse MetaTrader5 bar OHLC to bar object
bid_bars: list[Bar] = []
ask_bars: list[Bar] = []
for i in range(len(rates)):
    bid_bars.append(
        _parse_mt5_bar(
            mt5_bar=rates[i],
            price_precision=instrument.price_precision,
            size_precision=size_precision,
            bar_type=BarType.from_str(f"{symbol}.MT5-1-MINUTE-BID-EXTERNAL"),
        )
    )
    ask_bars.append(
        _parse_mt5_bar_ask(
            mt5_bar=rates[i],
            price_precision=instrument.price_precision,
            size_precision=size_precision,
            price_increment=float(instrument.price_increment),
            bar_type=BarType.from_str(f"{symbol}.MT5-1-MINUTE-ASK-EXTERNAL"),
        )
    )

# And then, save to parquet data catalog
catalog.write_data([instrument])
catalog.write_data(bid_bars)
catalog.write_data(ask_bars)

```

### Load data from parquet

```python
CATALOG_PATH = Path(__file__).resolve().parent / "data" / "catalog"
catalog = ParquetDataCatalog(CATALOG_PATH)
instrument = catalog.instruments()[0]  # EURUSDm.MT5

# Load bar bid and ask
bid_bars = catalog.bars(
    bar_types=[f"{instrument.id}-1-MINUTE-BID-EXTERNAL"], start=start, end=end
)
ask_bars = catalog.bars(
    bar_types=[f"{instrument.id}-1-MINUTE-ASK-EXTERNAL"], start=start, end=end
)
```
