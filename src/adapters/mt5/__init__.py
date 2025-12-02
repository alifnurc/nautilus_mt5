"""
MT5 platform integration adapter.

This subpackage provides an instrument provider, data and execution clients, configurations, and constants for connectiong to and interacting with Metatrader 5 API.

For convenience, the most commonly used symbols are re-exported at the subpackage's top level, so downstream code can simply import from ``adapters.mt5``.
"""

from adapters.mt5.config import MT5DataClientConfig, MT5ExecClientConfig
from adapters.mt5.constants import MT5, MT5_CLIENT_ID, MT5_VENUE
from adapters.mt5.factories import MT5LiveDataClientFactory, MT5LiveExecClientFactory

__all__ = [
    "MT5",
    "MT5_CLIENT_ID",
    "MT5_VENUE",
    "MT5DataClientConfig",
    "MT5ExecClientConfig" "MT5LiveDataClientFactory",
    "MT5LiveExecClientFactory",
]
