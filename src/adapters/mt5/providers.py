from typing import Any

from adapters.mt5.constants import MT5_VENUE
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.core import nautilus_pyo3
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.model.identifiers import INstrumentId
from nautilus_trader.model.instruments import instruments_from_pyo3


class MT5InstrumentProvider(InstrumentProvider):
    pass
