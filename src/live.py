import os
from dotenv import load_dotenv
from decimal import Decimal
from adapters.mt5 import MT5, MT5ClientConfig, MT5LiveDataClientFactory
from nautilus_trader.config import (
    LiveExecEngineConfig,
    LoggingConfig,
    TradingNodeConfig,
)
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId, TraderId

from strategies.pdhl import PDHL, PDHLConfig

load_dotenv()

symbol = "EURUSD"

# Configure the trading node
config_node = TradingNodeConfig(
    trader_id=TraderId("TESTER-001"),
    logging=LoggingConfig(log_level="INFO", use_pyo3=True),
    exec_engine=LiveExecEngineConfig(
        reconciliation=False,
    ),
    data_clients={
        MT5: MT5ClientConfig(
            account_number=os.getenv("MT5_ACCOUNT"),
            password=os.getenv("MT5_PASSWORD"),
            server=os.getenv("MT5_SERVER"),
            timeout=120000,
            rpyc_host=os.getenv("MT5_RPYC_HOST"),
            rpyc_port=os.getenv("MT5_RPYC_PORT"),
        )
    },
)

# Setup and run the trading node
node = TradingNode(config=config_node)

# Configure the strategy
config_strategy = PDHLConfig(
    instrument_id=InstrumentId.from_str(f"{symbol}.{MT5}"),
    bar_type=BarType.from_str(f"{symbol}.{MT5}-15-MINUTE-LAST-EXTERNAL"),
    trade_size=Decimal(0.01),
)
strategy = PDHL(config=config_strategy)

# Add the strategy to the node
node.trader.add_strategy(strategy=strategy)

# Register the data client factory
node.add_data_client_factory(MT5, MT5LiveDataClientFactory)
node.build()

# Run the node
try:
    node.run()
except KeyboardInterrupt:
    node.stop()
finally:
    node.dispose()
