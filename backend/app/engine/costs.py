from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def monthly_equivalent(quarterly_total: Decimal) -> Decimal:
    """A commitment comparison basis, never a provider monthly tariff."""
    return money(quarterly_total / Decimal(3))


def stop_savings(current_cost: Decimal | None) -> Decimal | None:
    # The supplied snapshot explicitly bills powered-off VMs.
    return Decimal("0.00") if current_cost is not None else None


def sum_known(values: list[Decimal | None]) -> Decimal:
    return money(sum((value for value in values if value is not None), Decimal(0)))
