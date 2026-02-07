import asyncio
from typing import Any


from adapters.mt5.config import MT5ClientConfig
from adapters.mt5.constants import MT5, MT5_VENUE
from adapters.mt5.client import AsyncMT5RPyCClient
from adapters.mt5.providers import MT5InstrumentProvider
from adapters.mt5.types import MT5_INSTRUMENT_TYPES, MT5Instrument
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock, MessageBus
from nautilus_trader.common.enums import LogColor, LogLevel
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.messages import (
    BatchCancelOrders,
    CancelOrder,
    GenerateFillReports,
    GenerateOrderStatusReport,
    GenerateOrderStatusReports,
    ModifyOrder,
    QueryOrder,
    SubmitOrder,
    SubmitOrderList,
)
from nautilus_trader.execution.reports import (
    FillReport,
    OrderStatusReport,
    PositionStatusReport,
)
from nautilus_trader.live.cancellation import (
    DEFAULT_FUTURE_CANCELLATION_TIMEOUT,
    cancel_tasks_with_timeout,
)
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.model import (
    Currency,
    AccountBalance,
    MarginBalance,
    Money,
    Venue,
    instruments,
)
from nautilus_trader.model.enums import (
    AccountType,
    ContingencyType,
    OmsType,
    OrderStatus,
)
from nautilus_trader.model.events import (
    AccountState,
    OrderCancelRejected,
    OrderModifyRejected,
    OrderRejected,
    OrderUpdated,
)
from nautilus_trader.model.functions import (
    contingency_type_to_pyo3,
    order_side_to_pyo3,
    order_type_to_pyo3,
    time_in_force_to_pyo3,
    trigger_type_to_pyo3,
)
from nautilus_trader.model.identifiers import AccountId, ClientId, ClientOrderId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.orders import Order


class MT5ExecutionClient(LiveExecutionClient):
    """
    Provides an execution client for MT5 platform terminal.

    Parameters
    ----------
    loop: asyncio.AbstractEventLoop
        The event loop for the client.
    client:
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        client: AsyncMT5RPyCClient,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
        instrument_provider: MT5InstrumentProvider,
        config: MT5ClientConfig,
        name: str | None,
    ):
        super().__init__(
            loop=loop,
            client_id=ClientId(name or MT5_VENUE.value),
            venue=MT5_VENUE,
            oms_type=OmsType.HEDGING,
            account_type=AccountType.MARGIN,
            base_currency=None,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=instrument_provider,
        )

        # Configuration
        self._client = client
        self._config = config
        self._connected = False
        self._account_info = None

        # Set initial account ID (will be updated with actual account number on connect)
        self._account_id_prefix = name or MT5_VENUE.value
        account_id = AccountId(f"{self._account_id_prefix}-master")
        self._set_account_id(account_id)

        self._account_summary_loaded: asyncio.Event = asyncio.Event()
        self._account_summary: dict[str, dict[str, Any]] = {}

        # TODO:
        # Mapping for tracking orders

    def _log_runtime_error(self, message: str) -> None:
        self._log.error(message, LogColor.RED)
        raise RuntimeError(message)

    @property
    def instrument_provider(self) -> MT5InstrumentProvider:
        return self._instrument_provider  # type: ignore

    def _cache_instruments(self) -> None:
        instruments_pyo3 = self._instrument_provider.instruments_pyo3()  # type: ignore

        for inst in instruments_pyo3:
            self._client.cache_instrument(inst)

        self._log.info("Cached instruments", LogColor.MAGENTA)

    async def _connect(self) -> None:
        # Connect client
        await self._instrument_provider.initialize()
        self._cache_instruments()

        await self._update_account_state()
        await self._await_account_registered()

        self._log.info("MT5 RPyC authenticated", LogColor.GREEN)

        # # Check MT5-Nautilus clock sync
        server_time: int = await self._client.get_server_time()
        self._log.info(f"MT5 server time {server_time} UNIX (ms)")

        nautilus_time: int = self._clock.timestamp_ms()
        self._log.info(f"Nautilus clock time {nautilus_time} UNIX (ms)")

        self._log.info(
            f"Connected to RPyC {self._config.rpyc_host}:{self._config.rpyc_port}"
        )

        try:
            # TODO:
            # await self._client.subscribe_orders()
            # await self._client.subscribe_executions()
            # await self._client.subscribe_positions()
            # await self._client.subscribe_margin()
            # await self._client.subscribe_wallet()
            pass
        except Exception as e:
            self._log.error(f"Failed to subscribe to authenticated channels: {e}")

    async def _update_account_state(self) -> None:
        # First get the margin data to extract the actual account number
        account_number = self._client.account_info().get("login")

        # Update account ID with actual account number from MT5
        if account_number:
            actual_account_id = AccountId(f"{self._account_id_prefix}-{account_number}")
            self._set_account_id(actual_account_id)
            self.pyo3_account_id = nautilus_pyo3.AccountId(actual_account_id.value)
            self._log.info(f"Updated account ID to {actual_account_id}", LogColor.BLUE)

        # Get account state
        pyo3_account_state = self._client.account_info()
        currency = Currency.from_str(pyo3_account_state.get("currency"))
        account_state = {
            "balances": [
                AccountBalance(
                    total=Money(pyo3_account_state.get("balance"), currency),
                    locked=Money(pyo3_account_state.get("margin"), currency),
                    free=Money(pyo3_account_state.get("margin_free"), currency),
                )
            ],
            "margins": [
                MarginBalance(
                    initial=Money(pyo3_account_state.get("margin"), currency),
                    maintenance=Money(
                        pyo3_account_state.get("margin_maintenance"), currency
                    ),
                )
            ],
        }

        self.generate_account_state(
            balances=account_state["balances"],
            margins=account_state["margins"],
            reported=True,
            ts_event=self._clock.timestamp_ns(),
        )

        if account_state["balances"]:
            self._log.info(
                f"Generated account state with {len(account_state["balances"])} balance(s)"
            )

    async def _disconnect(self) -> None:
        # if not self._client.is_closed():
        #     try:
        #         await self._client.unsubscribe_orders()
        #         await self._client.unsubscribe_executions()
        #         await self._client.unsubscribe_positions()
        #         await self._client.unsubscribe_margin()
        #         await self._client.unsubscribe_wallet()
        #     except Exception as e:
        #         self._log.error(f"Failed to unsubscribe from channels: {e}")
        #
        # await asyncio.sleep(1.0)
        #
        # if not self._client.is_closed():
        #     self._log.info("Disconnecting RPyC")
        #
        #     await self._client.close()
        #
        #     self._log.info(
        #         f"Disconnected from {self._config.rpyc_host}:{self._config.rpyc_port}",
        #         LogColor.BLUE,
        #     )

        # TODO:
        # Cancel any pending futures

        await self._client.disconnect()
        self._log.info("MT5 Execution Client disconnected")

    async def _load_account_info(self) -> None:
        pass

    async def _load_initial_state(self) -> None:
        pass

    async def _monitor_account(self) -> None:
        pass

    async def _check_position_updates(self) -> None:
        pass

    async def _check_order_updates(self) -> None:
        pass

    async def _handle_position_update(self, position) -> None:
        pass

    async def _handle_position_closed(self, ticket: str) -> None:
        pass

    async def _handle_order_update(self, order) -> None:
        pass

    async def submit_order(self, command: nautilus_pyo3.LimitOrder) -> None:
        pass

    def _create_mt5_order_request(self, order: Order, command) -> dict:
        pass

    # async def modify_order(self, command: nautilus_pyo3.ModifyOrder) -> None:
    #     pass

    # async def cancel_order(self, command: nautilus_pyo3.CancelOrder) -> None:
    #     pass
