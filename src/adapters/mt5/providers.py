from decimal import Decimal
from typing import List, Optional

from adapters.mt5.constants import MT5_VENUE
from adapters.mt5.client import AsyncMT5RPyCClient
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.model.identifiers import InstrumentId
from pymt5linux import MetaTrader5


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
        self._instruments = list[nautilus_pyo3.Instrument] = []
        self._loaded = False

    async def _load_all(self) -> None:
        try:
            symbols = await MetaTrader5.symbols_get()

            for symbol_obj in symbols:
                instrument = await self._create_instrument(symbol_obj)
                if instrument:
                    self._instruments[instrument.id] = instrument

            self._loaded = True
        except Exception as e:
            print(f"Error loading instruments: {e}")

    async def _create_instrument(self, symbol_obj):
        try:
            symbol = symbol_obj.name
            symbol_info = await MetaTrader5.symbol_info(symbol)
            if not symbol_info:
                return None

            # Parse to Nautilus format
            instrument_id = InstrumentId(
                symbol=nautilus_pyo3.Symbol(symbol), venue=MT5_VENUE
            )

            # Create instrument
            instrument = nautilus_pyo3.Instrument(
                id=instrument_id,
                asset_class=nautilus_pyo3.AssetClass.FX,
                base_currency=nautilus_pyo3.Currency.from_str(symbol[:3]),
                quote_currency=nautilus_pyo3.Currency.from_str(symbol[:3]),
                price_precision=symbol_info.digits,
                size_precision=2,
                lot_size=nautilus_pyo3.Quantity.from_str(str(symbol_info.volume_step)),
                min_quantity=nautilus_pyo3.Quantity.from_str(
                    str(symbol_info.volume_min)
                ),
                max_quantity=nautilus_pyo3.Quantity.from_str(
                    str(symbol_info.volume_max)
                ),
                margin_init=Decimal(str(symbol_info.margin_initial)),
                margin_maint=Decimal(str(symbol_info.margin_maintenance)),
            )
            return instrument
        except Exception as e:
            print(f"Error creating instrument {symbol_obj.name}: {e}")
            return None

    def get(self, instrument_id: InstrumentId) -> Optional[nautilus_pyo3.Instrument]:
        return self._instruments.get(instrument_id)

    def list_all(self) -> List[nautilus_pyo3.Instrument]:
        return list(self._instruments.values())

    def list_symbols(self) -> List[str]:
        return [inst.id.symbol.value for inst in self._instruments.values()]
