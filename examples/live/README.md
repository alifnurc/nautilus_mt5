# Live Session

NautilusTrader live session example for MetaTrader5 venue.

## What this is?

```bash
examples/live/
├── README.md
└── run_example.py # Live script for executing your strategy in live market

```

# Quick start

After following [initialization](../../README.md), you can moving forward to the next step

### Initialize your instrument symbol

Here, you should use the exact symbol name with your MetaTrader5 trading account, for example i use `EURUSDm` from `Exness standart account`.

```python
symbol "EURUSDm"
```

### Configure the trading node

In the initialization, you should make `.env` file in the root of your project and load them trought `load_dotenv()` function.

```python
config_node = TradingNodeConfig(
    ...
    data_clients={
        MT5: MT5ClientConfig(
            account_number=int(os.getenv("MT5_ACCOUNT")),
            password=str(os.getenv("MT5_PASSWORD")),
            server=str(os.getenv("MT5_SERVER")),
            timeout=120000,
            rpyc_host=str(os.getenv("MT5_RPYC_HOST")),
            rpyc_port=int(os.getenv("MT5_RPYC_PORT")),
            instrument_provider=InstrumentProviderConfig(load_all=True),
        )
    },
    exec_clients={
        MT5: MT5ClientConfig(
            account_number=int(os.getenv("MT5_ACCOUNT")),
            password=str(os.getenv("MT5_PASSWORD")),
            server=str(os.getenv("MT5_SERVER")),
            timeout=120000,
            rpyc_host=str(os.getenv("MT5_RPYC_HOST")),
            rpyc_port=int(os.getenv("MT5_RPYC_PORT")),
            instrument_provider=InstrumentProviderConfig(load_all=True),
        )
    },
)
```

### Order with native TP/SL

We are using native TP/SL. And here is an example if you send order with TP and SL trought oder params.

```python
order: LimitOrder = strategy.order_factory.limit(
    instrument_id=InstrumentId.from_str("EURUSDm.MT5"),
    order_side=OrderSide.BUY,
    quantity=Quantity.from_str("1000"),
    price=Price.from_str("1.16388"),
    params={
        "take_profit": "1.16720",
        "stop_loss": "1.16222",
    },
)
strategy.submit_order(order)
```
