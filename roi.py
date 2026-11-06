"""Compare incremental automation cash flows against the current process."""
import argparse
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction as Q
import json
from pathlib import Path


@dataclass(frozen=True)
class Year:
    avoided_overtime: Q
    other_cash_savings: Q
    running_cost: Q
    one_time_cost: Q


@dataclass(frozen=True)
class Case:
    initial_cost: Q
    rate_percent: Q
    terminal_cash: Q
    years: tuple[Year, ...]


@dataclass(frozen=True)
class Row:
    year: int
    cash: Q
    present_value: Q
    cumulative_cash: Q
    cumulative_present: Q


def read_case(path):
    def unique(pairs):
        values = {}
        for name, value in pairs:
            if name in values:
                raise ValueError(f"duplicate field: {name}")
            values[name] = value
        return values

    obj = json.loads(Path(path).read_text(encoding="utf-8"),
                     parse_int=Q, parse_float=Q, object_pairs_hook=unique)

    def keys(obj, fields, where):
        if not isinstance(obj, dict) or set(obj) != set(fields.split()):
            raise ValueError(f"{where}: expected exactly {fields}")

    def decimal(value, where, upper=10**9):
        if not isinstance(value, Q) or not 0 <= value <= upper or (value * 100).denominator != 1:
            raise ValueError(f"{where}: use a number from 0 to {upper} in hundredths")
        return value

    keys(obj, "initial_cost real_discount_percent terminal_resale terminal_removal years", "case")
    initial = decimal(obj["initial_cost"], "initial_cost")
    if initial == 0:
        raise ValueError("initial_cost must be positive")
    rate = decimal(obj["real_discount_percent"], "real_discount_percent", 100)
    terminal = (decimal(obj["terminal_resale"], "terminal_resale")
                - decimal(obj["terminal_removal"], "terminal_removal"))
    annual = obj["years"]
    if not isinstance(annual, list) or not 1 <= len(annual) <= 30:
        raise ValueError("years: provide 1 to 30 annual records")
    years = []
    for i, yr in enumerate(annual, 1):
        keys(yr, "avoided_overtime other_cash_savings running_cost one_time_cost", f"year {i}")
        years.append(Year(**{k: decimal(v, f"year {i} {k}") for k, v in yr.items()}))
    return Case(initial, rate, terminal, tuple(years))


def ledger(case):
    undiscounted = discounted = -case.initial_cost
    yield Row(0, undiscounted, discounted, undiscounted, discounted)
    growth = 1 + case.rate_percent / 100
    for i, yr in enumerate(case.years, 1):
        cash = yr.avoided_overtime + yr.other_cash_savings - yr.running_cost - yr.one_time_cost
        if i == len(case.years):
            cash += case.terminal_cash
        pv = cash / growth**i
        undiscounted += cash
        discounted += pv
        yield Row(i, cash, pv, undiscounted, discounted)


def payback(rows, field):
    """First nonnegative balance and first nonnegative balance that stays so."""
    balances = [getattr(row, field) for row in rows]
    first = next((row.year for row, value in zip(rows, balances) if value >= 0), None)
    last_deficit = max((i for i, value in enumerate(balances) if value < 0), default=-1)
    durable = rows[last_deficit + 1].year if last_deficit + 1 < len(rows) else None
    return first, durable


def fmt(value):
    with localcontext() as ctx:
        ctx.prec = 40
        return f"{Decimal(value.numerator) / Decimal(value.denominator):,.2f}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", help="path to one JSON scenario")
    args = parser.parse_args(argv)
    try:
        case = read_case(args.case)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    rows = list(ledger(case))
    print("year | incremental cash | present value | cash balance | discounted balance")
    for r in rows:
        print(f"{r.year:4d} | {fmt(r.cash):>16} | {fmt(r.present_value):>13} | "
              f"{fmt(r.cumulative_cash):>12} | {fmt(r.cumulative_present):>18}")
    print(f"Net present value: {fmt(rows[-1].cumulative_present)}")
    print(f"Simple ROI on initial cost: {fmt(100 * rows[-1].cumulative_cash / case.initial_cost)}%")

    def year(n):
        return f"year {n}" if n is not None else "not reached"

    for label, field in (("Cash", "cumulative_cash"), ("Discounted", "cumulative_present")):
        first, durable = payback(rows, field)
        print(f"{label} payback: first {year(first)}; stays nonnegative {year(durable)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
