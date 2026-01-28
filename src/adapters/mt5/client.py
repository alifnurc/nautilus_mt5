import asyncio
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

from pymt5linux import MetaTrader5
from adapters.mt5.config import MT5ClientConfig
from adapters.mt5.constants import MT5_VENUE
from nautilus_trader.model import InstrumentId, Symbol
from nautilus_trader.common.component import Logger
from nautilus_trader.common.enums import LogColor


class AsyncMT5RPyCClient:
    """
    Async wrapper for MT5RPyCClient integration with asyncio NautilusTrader
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
                cls._instance._config = None
            return cls._instance

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._log = Logger("MT5_Client")

    def initialize(self, config: MT5ClientConfig):
        try:
            self._log.info(
                f"Connecting to RPyC server at {config.rpyc_host}:{config.rpyc_port}",
                LogColor.BLUE,
            )
            self.conn = MetaTrader5(host=config.rpyc_host, port=config.rpyc_port)

            # Initialize MT5 terminal
            initialized = self.conn.initialize(
                login=config.account_number,
                password=config.password,
                server=config.server,
                timeout=config.timeout,
            )

            if not initialized:
                error = self.conn.last_error()
                self._log.error(f"MT5 initialize failed: {error}")

            self._initialized = True
            self._config = config
            self._log.info(
                f"Connected to MT5 via RPyC. Account: {config.account_number}"
            )

            # TODO:
            # Start heartbeat thread
            # self._start_heartbeat()

            return self
        except Exception as e:
            self._log.error(f"Connection failed: {e}")
            # self.disconnect()
            return self

    def is_initialized(self):
        return self._initialized

    def shutdown(self):
        if self.is_initialized():
            self.conn.shutdown()
        return self

    async def disconnect(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.shutdown,
        )

    async def request_instruments(self, active_only):
        loop = asyncio.get_event_loop()
        try:
            mt5_symbols = await loop.run_in_executor(
                self.executor,
                lambda: self.conn.symbols_get(),
            )

            instruments = []
            for i in range(len(mt5_symbols)):
                instruments.append(InstrumentId(Symbol(mt5_symbols[i][-3]), MT5_VENUE))

            return instruments
        except Exception as e:
            self._log.error(f"Failed to get instruments: {e}")

    def account_info(self):
        try:
            account_info = self.conn.account_info()._asdict()

            return account_info

        except Exception as e:
            self._log.error(f"Failed to get account info: {e}")
