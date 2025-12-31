from nautilus_trader.common.config import PositiveInt
from nautilus_trader.config import LiveDataClientConfig


class MT5ClientConfig(LiveDataClientConfig, frozen=True):
    """
    Configuration for ``MT5DataClient`` instances.

    Parameters
    ----------
    account_number: PositiveInt, [default=None]
        The MetaTrader 5 account number.
        If ``None`` then will source the ``MT5_ACCOUNT`` environment variable.
    password: str, [default=None]
        The MetaTrader 5 account password.
        If ``None`` then will source the ``MT5_PASSWORD`` environment variable.
    server: str, [default=None]
        The MetaTrader 5 account server.
        If ``MT5_SERVER`` environment variable.
    timeout: PositiveInt, [default=60000]
        The MetaTrader 5 connection timeout in milliseconds.
        If ``None`` then the default value is 60000 (60 seconds).
    rpyc_host: str, [default=None]
        The RPyC host from server side MT5 Adapter.
        If ``None`` then will source the ``RPYC_HOST`` environment variable.
    rpyc_port: PositiveInt, [default=None]
        The RPyC port from server side MT5 Adapter.
        If ``NOne`` then will source the ``RPYC_HOST`` environment variable.
    """

    account_number: PositiveInt | None = None
    password: str | None = None
    server: str | None = None
    timeout: PositiveInt = 60000
    rpyc_host: str | None = None
    rpyc_port: PositiveInt | None = None
