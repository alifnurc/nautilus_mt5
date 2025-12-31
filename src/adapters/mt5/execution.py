import asyncio
from typing import Any

from nautilus_trader.model import Venue

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
        clock: LiveClock,
        logger: None,  # Log for nautilus_trader
        config: MT5ClientConfig,
        account_type=nautilus_pyo3.AccountType.MARGIN,
    ):
        super().__init__(
            loop=loop,
            client_id=None,
            venue=MT5_VENUE,
            account_type=account_type,
            base_currency=None,
            msgbus=None,
            cache=None,
            clock=clock,
            logger=logger,
        )

        self.config = config
        self.client = AsyncMT5RPyCClient(config)
        self._connected = False
        self._account_info = None

        # TODO:
        # Mapping for tracking orders

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

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
