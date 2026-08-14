from typing import Final

from nautilus_trader.model.identifiers import ClientId, Venue

MT5: Final[str] = "MT5"
MT5_VENUE: Final[Venue] = Venue(MT5)
MT5_CLIENT_ID: Final[ClientId] = ClientId(MT5)
