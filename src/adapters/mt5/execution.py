import asyncio
from typing import Any

from adapters.mt5.config import MT5ExecClientConfig
from adapters.mt5.constants import MT5_VENUE
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
    pass
