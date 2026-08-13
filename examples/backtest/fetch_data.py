import datetime
from decimal import Decimal
import os
import pandas
from pathlib import Path
from nautilus_trader.model import (
    Bar,
    BarType,
    Currency,
    InstrumentId,
    Price,
    Quantity,
    Symbol,
    Venue,
)
from nautilus_trader.model.enums import asset_class_from_str
from nautilus_trader.model.instruments import Cfd
from pymt5linux import MetaTrader5
from dotenv import load_dotenv
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from datetime import timezone

load_dotenv()


def _parse_mt5_bar(mt5_bar, price_precision, size_precision, bar_type):
    return Bar(
        bar_type=bar_type,
        open=Price(
            mt5_bar["open"].item(),
            price_precision,
        ),
        high=Price(
            mt5_bar["high"].item(),
            price_precision,
        ),
        low=Price(
            mt5_bar["low"].item(),
            price_precision,
        ),
        close=Price(
            mt5_bar["close"].item(),
            price_precision,
        ),
        volume=Quantity(mt5_bar["tick_volume"].item(), precision=size_precision),
        ts_event=mt5_bar["time"] * 1e9,
        ts_init=mt5_bar["time"] * 1e9,
    )


def _parse_mt5_bar_ask(
    mt5_bar, price_precision, size_precision, price_increment, bar_type
):
    spread = mt5_bar["spread"].item() * price_increment
    return Bar(
        bar_type=bar_type,
        open=Price(
            mt5_bar["open"].item() + spread,
            price_precision,
        ),
        high=Price(
            mt5_bar["high"].item() + spread,
            price_precision,
        ),
        low=Price(
            mt5_bar["low"].item() + spread,
            price_precision,
        ),
        close=Price(
            mt5_bar["close"].item() + spread,
            price_precision,
        ),
        volume=Quantity(mt5_bar["tick_volume"].item(), precision=size_precision),
        ts_event=mt5_bar["time"] * 1e9,
        ts_init=mt5_bar["time"] * 1e9,
    )


def _tick_size_to_precision(tick_size: float | Decimal) -> int:
    tick_size_str = f"{tick_size:.10f}"
    return len(tick_size_str.partition(".")[2].rstrip("0"))


def _parse_mt5_symbol_to_cfd(mt5_symbol, mt5_account):
    size_precision: int = _tick_size_to_precision(tick_size=mt5_symbol.volume_step)
    return Cfd(
        instrument_id=InstrumentId(Symbol(mt5_symbol.name), Venue("MT5")),
        raw_symbol=Symbol(mt5_symbol.name),
        asset_class=asset_class_from_str("Fx"),  # TODO: Sperate indicies and forex soon
        quote_currency=Currency.from_str(mt5_symbol.currency_profit),
        price_precision=mt5_symbol.digits,
        size_precision=size_precision,
        price_increment=Price(mt5_symbol.trade_tick_size, mt5_symbol.digits),
        size_increment=Quantity(mt5_symbol.volume_step, size_precision),
        ts_event=mt5_symbol.time * 1e9,
        ts_init=mt5_symbol.time * 1e9,
        base_currency=Currency.from_str(mt5_symbol.currency_base),
        lot_size=Quantity(mt5_symbol.trade_contract_size, 0),
        max_quantity=Quantity(
            mt5_symbol.trade_contract_size * mt5_symbol.volume_max, size_precision
        ),
        min_quantity=Quantity(
            mt5_symbol.trade_contract_size * mt5_symbol.volume_min, size_precision
        ),
        max_notional=None,
        min_notional=None,
        max_price=None,
        min_price=None,
        margin_init=Decimal(1 / mt5_account.leverage),
        margin_maint=Decimal(1 / mt5_account.leverage),
        maker_fee=Decimal(0),
        taker_fee=Decimal(0),
        tick_scheme_name=None,
        info=None,
    )


if __name__ == "__main__":
    account_number = int(os.getenv("MT5_ACCOUNT"))
    password = str(os.getenv("MT5_PASSWORD"))
    server = str(os.getenv("MT5_SERVER"))
    rpyc_host = str(os.getenv("MT5_RPYC_HOST"))
    rpyc_port = int(os.getenv("MT5_RPYC_PORT"))

    CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog"
    catalog = ParquetDataCatalog(CATALOG_PATH)

    mt5 = MetaTrader5(host=rpyc_host, port=rpyc_port)
    initialized = mt5.initialize(login=account_number, password=password, server=server)

    if not initialized:
        error = mt5.last_error()
        print(f"MT5 initialize failed: {error}")

    symbol = f"EURUSDm"
    size_precision: int = _tick_size_to_precision(
        tick_size=mt5.symbol_info(symbol).volume_step
    )
    instrument = _parse_mt5_symbol_to_cfd(mt5.symbol_info(symbol), mt5.account_info())
    timezone = timezone.utc
    start = datetime.datetime(2025, 1, 1, 00, 00, tzinfo=timezone)
    end = datetime.datetime(2025, 12, 31, 23, 59, tzinfo=timezone)
    rates = mt5.copy_rates_range(
        symbol=symbol, timeframe=mt5.TIMEFRAME_M1, date_from=start, date_to=end
    )

    mt5.shutdown()

    rates_frame = pandas.DataFrame(rates)
    rates_frame["time"] = pandas.to_datetime(rates_frame["time"], unit="s")

    print(rates_frame)

    bid_bars: list[Bar] = []
    ask_bars: list[Bar] = []
    for i in range(len(rates)):
        bid_bars.append(
            _parse_mt5_bar(
                mt5_bar=rates[i],
                price_precision=instrument.price_precision,
                size_precision=size_precision,
                bar_type=BarType.from_str(f"{symbol}.MT5-1-MINUTE-BID-EXTERNAL"),
            )
        )
        ask_bars.append(
            _parse_mt5_bar_ask(
                mt5_bar=rates[i],
                price_precision=instrument.price_precision,
                size_precision=size_precision,
                price_increment=float(instrument.price_increment),
                bar_type=BarType.from_str(f"{symbol}.MT5-1-MINUTE-ASK-EXTERNAL"),
            )
        )

    catalog.write_data([instrument])
    catalog.write_data(bid_bars)
    catalog.write_data(ask_bars)
