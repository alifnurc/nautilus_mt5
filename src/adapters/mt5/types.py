from typing import Final

from nautilus_trader.core import nautilus_pyo3

MT5Instrument = nautilus_pyo3.CurrencyPair | nautilus_pyo3.CryptoFuture

MT5_INSTRUMENT_TYPES: Final[
    tuple[type[nautilus_pyo3.CurrencyPair], type[nautilus_pyo3.CryptoFuture]]
] = (nautilus_pyo3.CurrencyPair, nautilus_pyo3.CryptoFuture)
