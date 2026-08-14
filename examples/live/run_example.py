import os
from dotenv import load_dotenv
from decimal import Decimal
from nautilus_mt5.adapters.mt5 import (
    MT5,
    MT5ClientConfig,
    MT5LiveDataClientFactory,
    MT5LiveExecClientFactory,
)
from nautilus_trader.config import (
    InstrumentProviderConfig,
    LiveExecEngineConfig,
    LoggingConfig,
    TradingNodeConfig,
)
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId, TraderId
from nautilus_trader.model.enums import OrderSide
from nautilus_mt5.examples.strategies.periodic_market_order import (
    PeriodicMarketOrderConfig,
    PeriodicMarketOrderStrategy,
)

load_dotenv()

symbol = "EURUSDm"

# Configure the trading node
config_node = TradingNodeConfig(
    trader_id=TraderId("TESTER-001"),
    logging=LoggingConfig(
        log_level="DEBUG",
        use_pyo3=True,
        log_level_file="DEBUG",
        log_directory="./log",
        log_file_format="json",
    ),
    exec_engine=LiveExecEngineConfig(
        reconciliation=False,
    ),
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

# Setup and run the trading node
node = TradingNode(config=config_node)

# Configure the strategy
config = PeriodicMarketOrderConfig(
    instrument_id=InstrumentId.from_str(f"{symbol}.{MT5}"),
    bar_type=BarType.from_str(
        f"{InstrumentId.from_str(f"{symbol}.{MT5}")}-1-MINUTE-BID-EXTERNAL"
    ),
    order_side=OrderSide.SELL,
    order_quantity=Decimal("1000"),
    order_interval_seconds=20,
)

strategy = PeriodicMarketOrderStrategy(config=config)

# Add the strategy to the node
node.trader.add_strategy(strategy=strategy)

# Register the data client factory
node.add_data_client_factory(MT5, MT5LiveDataClientFactory)
node.add_exec_client_factory(MT5, MT5LiveExecClientFactory)
node.build()

# Run the node
try:
    node.run()
except KeyboardInterrupt:
    node.stop()
finally:
    node.dispose()
