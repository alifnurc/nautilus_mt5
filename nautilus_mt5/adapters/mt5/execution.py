import asyncio
from typing import Any

from nautilus_mt5.adapters.mt5.config import MT5ClientConfig
from nautilus_mt5.adapters.mt5.constants import MT5_VENUE
from nautilus_mt5.adapters.mt5.client import AsyncMT5RPyCClient
from nautilus_mt5.adapters.mt5.providers import MT5InstrumentProvider
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock, MessageBus
from nautilus_trader.common.enums import LogColor, LogLevel
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.messages import (
    GenerateFillReports,
    GenerateOrderStatusReport,
    GenerateOrderStatusReports,
    GeneratePositionStatusReports,
    SubmitOrder,
    SubmitOrderList,
)
from nautilus_trader.execution.reports import (
    FillReport,
    OrderStatusReport,
    PositionStatusReport,
)
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.model import (
    Currency,
    AccountBalance,
    MarginBalance,
    Money,
    OrderListId,
    Price,
)
from nautilus_trader.model.enums import (
    AccountType,
    ContingencyType,
    OmsType,
    contingency_type_from_str,
    trigger_type_from_str,
)
from nautilus_trader.model.events import (
    OrderAccepted,
    OrderCanceled,
    OrderExpired,
    OrderFilled,
    OrderRejected,
)
from nautilus_trader.model.identifiers import AccountId, ClientId
from nautilus_trader.model.objects import Quantity


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

        self._log.info(
            f"Connected to RPyC {self._config.rpyc_host}:{self._config.rpyc_port}"
        )

        try:
            # TODO:
            await self._client.subscribe_orders(msg_handler=self._handle_order_msg)
            # await self._client.subscribe_executions()
            # await self._client.subscribe_positions()
            # await self._client.subscribe_margin()
            # await self._client.subscribe_wallet()
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
                    total=Money(pyo3_account_state.get("equity"), currency),
                    locked=Money(pyo3_account_state.get("profit"), currency),
                    free=Money(pyo3_account_state.get("balance"), currency),
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
        try:
            await self._client.unsubscribe_orders()
            # await self._client.unsubscribe_executions()
            # await self._client.unsubscribe_positions()
            # await self._client.unsubscribe_margin()
            # await self._client.unsubscribe_wallet()
        except Exception as e:
            self._log.error(f"Failed to unsubscribe from channels: {e}")

        await asyncio.sleep(1.0)

        # TODO:
        # Cancel any pending futures

        await self._client.disconnect()
        self._log.info("MT5 Execution Client disconnected")

    async def generate_order_status_reports(
        self, command: GenerateOrderStatusReports
    ) -> list[OrderStatusReport]:
        try:
            dict_reports = await self._client.request_order_status_reports(
                instrument_id=command.instrument_id,
                open_only=command.open_only,
                limit=None,
            )

            reports: list[OrderStatusReport] = []

            for dict_report in dict_reports:
                reports.append(OrderStatusReport.from_dict(dict_report))

            len_reports = len(reports)
            plural = "" if len_reports == 1 else "s"
            receipt_log = f"Received {len(reports)} OrderStatusReport{plural}"

            if command.log_receipt_level == LogLevel.INFO:
                self._log.info(receipt_log)
            else:
                self._log.debug(receipt_log)

            return reports
        except Exception as e:
            self._log.error(f"Failed to generate order status reports: {e}")
            return []

    async def generate_order_status_report(
        self, command: GenerateOrderStatusReport
    ) -> OrderStatusReport | None:
        self._log.warning("Order status report generation not yet implemented")
        return None

    async def generate_fill_reports(
        self, command: GenerateFillReports
    ) -> list[FillReport]:
        try:
            dict_reports = await self._client.request_fill_reports(
                instrument_id=command.instrument_id,
                limit=None,
            )

            reports: list[FillReport] = []

            for dict_report in dict_reports:
                reports.append(FillReport.from_dict(dict_report))

            len_reports = len(reports)
            plural = "" if len_reports == 1 else "s"
            self._log.info(f"Received {len(reports)} FillReport{plural}")

            return reports
        except Exception as e:
            self._log.error(f"Failed to generate fill reports: {e}")
            return []

    async def generate_position_status_reports(
        self, command: GeneratePositionStatusReports
    ) -> list[PositionStatusReport]:
        try:
            dict_reports = await self._client.request_position_status_reports()

            reports = []

            for dict_report in dict_reports:
                reports.append(PositionStatusReport.from_dict(dict_report))

            len_reports = len(reports)
            plural = "" if len_reports == 1 else "s"
            self._log.info(f"Received {len(reports)} PositionStatusReport{plural}")

            return reports
        except Exception as e:
            self._log.error(f"Failed to generate position status reports: {e}")
            return []

    async def _submit_order(self, command: SubmitOrder) -> None:
        order = command.order

        if order.is_closed:
            self._log.warning(f"Cannot submit already closed order: {order}")
            return

        if order.is_quote_quantity:
            reason = "UNSUPPORTED_QUOTE_QUANTITY"
            self._log.error(f"Cannot submit order {order.client_order_id}: {reason}")
            self.generate_order_denied(
                strategy_id=order.strategy_id,
                instrument_id=order.instrument_id,
                reason=reason,
                ts_event=self._clock.timestamp_ns(),
            )
            return

        # Generate OrderSubmitted event here to ensure conrrect event sequencing
        self.generate_order_submitted(
            strategy_id=order.strategy_id,
            instrument_id=order.instrument_id,
            client_order_id=order.client_order_id,
            ts_event=self._clock.timestamp_ns(),
        )

        contingency_type = None
        order_list_id = None

        if order.order_list_id is not None:
            order_list_id = OrderListId(order.order_list.value)

        if order.contingency_type in (ContingencyType.OCO, ContingencyType.OTO):
            contingency_type = contingency_type_from_str(str(order.contingency_type))

        try:
            await self._client.submit_order(
                command=command,
                msg_handler=self._handle_order_msg,
            )
        except Exception as e:
            self.generate_order_rejected(
                strategy_id=order.strategy_id,
                instrument_id=order.instrument_id,
                client_order_id=order.client_order_id,
                reason=str(e),
                ts_event=self._clock.timestamp_ns(),
            )

    async def _submit_order_list(self, command: SubmitOrderList) -> None:
        for order in command.order_list_orders:
            submit_command = SubmitOrder(
                trader_id=command.trader_id,
                strategy_id=command.strategy_id,
                order=order,
                command_id=UUID4(),
                ts_init=self._clock.timestamp_ns(),
                position_id=command.position_id,
                client_id=command.client_id,
                params=command.params,
            )
            await self._submit_order(submit_command)

    def _handle_order_msg(self, msg: Any) -> None:
        try:
            if isinstance(msg, OrderAccepted):
                self._send_order_event(msg)
            elif isinstance(msg, OrderCanceled):
                self._send_order_event(msg)
            elif isinstance(msg, OrderExpired):
                self._send_order_event(msg)
            elif isinstance(msg, OrderRejected):
                self._send_order_event(msg)
            elif isinstance(msg, OrderFilled):
                self._send_order_event(msg)
            else:
                self._log.warning(f"Received unhandled message type: {type(msg)}")
        except Exception as e:
            self._log.exception("Error handling message", e)

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

    # async def modify_order(self, command: nautilus_pyo3.ModifyOrder) -> None:
    #     pass

    # async def cancel_order(self, command: nautilus_pyo3.CancelOrder) -> None:
    #     pass
