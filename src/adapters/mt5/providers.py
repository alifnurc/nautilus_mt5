from typing import Any, List

from nautilus_trader.config import InstrumentProviderConfig

from adapters.mt5.constants import MT5_VENUE
from adapters.mt5.client import AsyncMT5RPyCClient
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import instruments_from_pyo3


class MT5InstrumentProvider(InstrumentProvider):
    """
    Provides an instrument definitions from MT5 platform.

    Parameters
    ----------
    client: AsyncMT5RPyCClient
        The MT5 RPyC Client.
    active_only: bool, [default=True]
        Wheter to only load active instruments.
    config: InstrumentProviderConfig, [default=None]
        The instrument provider configuration.
    """

    def __init__(
        self,
        client: AsyncMT5RPyCClient,
        active_only: bool = True,
        config: InstrumentProviderConfig | None = None,
    ) -> None:
        super().__init__(config=config)
        self._client = client
        self._active_only = active_only
        self._log_warnings = config.log_warnings if config else True
        self._instruments_pyo3: list[nautilus_pyo3.Instrument] = []

    @property
    def active_only(self) -> bool:
        return self._active_only

    def instruments_pyo3(self) -> List[Any]:
        return self._instruments_pyo3

    async def load_all_async(self, filters: dict | None = None) -> None:
        filters_str = "..." if not filters else f"with filters {filters}..."
        self._log.info(f"Loading all instruments{filters_str}")

        pyo3_instruments = await self._client.request_instruments(
            self._active_only,
        )

        self._instruments_pyo3 = pyo3_instruments
        instruments = instruments_from_pyo3(pyo3_instruments)
        for instrument in instruments:
            self.add(instrument=instrument)

    async def load_ids_async(
        self, instrument_ids: list[InstrumentId], filters: dict | None = None
    ) -> None:
        if not instrument_ids:
            self._log.warning("No instrument IDs given for loading")
            return

        # Check all instrument IDs
        for instrument_id in instrument_ids:
            PyCondition.equal(
                instrument_id.venue, MT5_VENUE, "instrument_id.venue", "MT5"
            )

        pyo3_instruments = await self._client.request_instruments(
            self._active_only,
        )

        self._instruments_pyo3 = pyo3_instruments
        instruments = instruments_from_pyo3(pyo3_instruments)

        for instrument in instruments:
            if instrument.id not in instrument_ids:
                continue
            self.add(instrument=instrument)

    async def load_async(
        self, instrument_id: InstrumentId, filters: dict | None = None
    ) -> None:
        PyCondition.not_none(instrument_id, "instrument_id")
        await self.load_ids_async([instrument_id], filters)
