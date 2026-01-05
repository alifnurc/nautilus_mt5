import asyncio
import threading
import time
import pandas as pd
from typing import Callable

from nautilus_trader.model import Bar, Price, Quantity
from pymt5linux import MetaTrader5, rpyc
from adapters.mt5.config import MT5ClientConfig
from nautilus_trader.common.component import Logger
from nautilus_trader.model import BarType
from nautilus_trader.common.enums import LogColor
from nautilus_trader.core import nautilus_pyo3

from adapters.mt5.constants import MT5_VENUE


class MT5RPyCClient:
    """
    RPyC Client for MT5 server side adapter.
    """

    def __init__(self, config: MT5ClientConfig):
        self.conn = None
        self._config = config
        self._connected = False
        self._callbacks = []
        self._subscriptions = {}
        self._log = Logger("MT5_Client")

    def connect(self) -> bool:
        try:
            self._log.info(
                f"Connecting to RPyC server at {self._config.rpyc_host}:{self._config.rpyc_port}",
                LogColor.BLUE,
            )
            self.conn = MetaTrader5(
                host=self._config.rpyc_host, port=self._config.rpyc_port
            )

            # Initialize MT5 terminal
            initialized = self.conn.initialize(
                login=self._config.account_number,
                password=self._config.password,
                server=self._config.server,
                timeout=self._config.timeout,
            )

            if not initialized:
                error = self.conn.last_error()
                self._log.error(f"MT5 initialize failed: {error}")
                return False

            self._connected = True
            self._log.info(
                f"Connected to MT5 via RPyC. Account: {self._config.account_number}"
            )

            # Start heartbeat thread
            self._start_heartbeat()

            return True
        except Exception as e:
            self._log.error(f"Connection failed: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        if self.conn:
            self.conn.shutdown()

        self._connected = False
        self.conn = None

    def _start_heartbeat(self):
        def heartbeat():
            while self._connected:
                try:
                    time.sleep(30)
                    connection = rpyc.connect(
                        self._config.rpyc_host, self._config.rpyc_port
                    )
                    if connection:
                        # Simple thing for checking connection
                        connection.ping()
                except:
                    self._log.warning("Heartbeat failed, reconecting...")
                    self.reconnect()

        thread = threading.Thread(target=heartbeat(), daemon=True)
        thread.start()

    def reconnect(self) -> bool:
        self.disconnect()
        time.sleep(1)
        return self.connect()

    def subscribe_bars(self, bar_type: nautilus_pyo3.BarType):
        try:
            symbol = bar_type.instrument_id.symbol
            rates = self.conn.copy_rates_from_pos(
                symbol=symbol,
                timeframe=self.conn.TIMEFRAME_M15,
                start_pos=0,
                count=1,
            )

            if rates is not None and len(rates) > 0:
                # Create InstrumentId
                instrument = TestInstrumentProvider.default_fx_ccy(
                    symbol=symbol, venue=MT5_VENUE
                )

                # Create BarType
                bar_type = BarType.from_str(f"{instrument.id}-15-MINUTE-BID-EXTERNAL")

                # Symbol digits as precision
                digits = self.conn.symbol_info(symbol).digits

                # Create Bar Object
                bar = Bar(
                    bar_type=bar_type,
                    open=Price(float(rates[0]["open"]), precision=digits),
                    high=Price(float(rates[0]["high"]), precision=digits),
                    low=Price(float(rates[0]["low"]), precision=digits),
                    close=Price(float(rates[0]["close"]), precision=digits),
                    volume=Quantity(int(rates[0]["tick_volume"]), precision=0),
                    ts_event=int(str(rates[0]["time"])) * 1e9,
                    ts_init=pd.Timestamp.now(tz="utc").timestamp() * 1e9,
                )

                return bar
        except Exception as e:
            self._log.error(f"Connection failed: {e}")
            self.disconnect()

    def unsubscribe_bars(self, bar_type: nautilus_pyo3.BarType):
        pass

    def request_bars(self, bar_type: nautilus_pyo3.BarType, start, end, limit, partial):
        pass

    def request_instruments(self, active_only):
        pass


class AsyncMT5RPyCClient:
    """
    Async wrapper for MT5RPyCClient integration with asyncio NautilusTrader
    """

    def __init__(self, config: MT5ClientConfig):
        self.sync_client = MT5RPyCClient(config)
        self.executor = None

    async def connect(self) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.sync_client.connect(),
        )

    async def disconnect(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.sync_client.disconnect(),
        )

    async def subscribe_bars(self, bar_type):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.sync_client.subscribe_bars(bar_type)
        )

    async def unsubscribe_bars(self, bar_type):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.sync_client.unsubscribe_bars(bar_type)
        )

    async def request_bars(self, bar_type, start, end, limit, partial):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.sync_client.request_bars(bar_type, start, end, limit, partial)
        )

    async def request_instruments(self, active_only):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.sync_client.request_instruments(active_only)
        )
