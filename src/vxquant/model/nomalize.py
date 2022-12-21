import re
from typing import Tuple, Callable, Union
from functools import lru_cache


def normalize_freq(freq: str) -> Tuple[int, str]:
    """
    Parse freq into a unified format

    Parameters
    ----------
    freq : str
        Raw freq, supported freq should match the re '^([0-9]*)(month|mon|week|w|day|d|minute|min)$'

    Returns
    -------
    freq: Tuple[int, str]
        Unified freq, including freq count and unified freq unit. The freq unit should be '[month|week|day|minute]'.
            Example:

            .. code-block::

                print(freq_parse("day"))
                (1, "day" )
                print(freq_parse("2mon"))
                (2, "month")
                print(freq_parse("10w"))
                (10, "week")

    """
    freq = freq.lower()
    match_obj = re.match("^([0-9]*)(month|mon|week|w|day|d|minute|min)$", freq)
    if match_obj is None:
        raise ValueError(
            "freq format is not supported, the freq should be like (n)month/mon,"
            " (n)week/w, (n)day/d, (n)minute/min"
        )
    _count = int(match_obj[1]) if match_obj[1] else 1
    _freq = match_obj[2]
    _freq_format_dict = {
        "month": "month",
        "mon": "month",
        "week": "week",
        "w": "week",
        "day": "day",
        "d": "day",
        "minute": "minute",
        "min": "minute",
    }
    return _count, _freq_format_dict[_freq]


def normalize_symbol(symbol: str):
    # todo 用正则表达式进行进一步优化

    match_obj = re.match(r"^[A-Za-z]{2,4}.?([0-9]{6,10})$", symbol)

    if match_obj:
        code = match_obj[1]
    else:
        match_obj = re.match(r"^([0-9]{6,10}).?[A-Za-z]{2,4}$", symbol)

    if match_obj is None:
        raise ValueError(f"{symbol} format is not support.")

    code = match_obj[1]
    exchange = (
        symbol.replace("se", "").replace("SE", "").replace(".", "").replace(code, "")
    )
    if exchange.upper() in {"OF", "ETF", "LOF", ""}:
        exchange = "SZSE" if code[0] in ["0", "1", "2", "3", "4"] else "SHSE"
    else:
        exchange = exchange if len(exchange) > 2 else f"{exchange}SE"

    return (exchange.upper(), code)


@lru_cache(200)
def to_symbol(instrument: str):
    if instrument.upper() in {"CNY", "CACH"}:
        return "CNY"

    match_obj = re.match(r"^(SHSE|SZSE).(\d{6})$", instrument)

    if match_obj:
        return instrument

    exchange, code = normalize_symbol(instrument)
    return f"{exchange}.{code}"


if __name__ == "__main__":
    print(to_symbol("SHSE.600000"))
    print(to_symbol("SH600000"))
    print(to_symbol("sh600000"))
    print(to_symbol("600000.sh"))
    print(to_symbol("600000.SHSE"))
    print(to_symbol("600000sh"))
