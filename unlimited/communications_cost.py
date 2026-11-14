"""Scenario-based communications TCO. No claimed live provider prices or savings."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


def money(value: object) -> Decimal:
    """Reject ambiguous/non-finite inputs and preserve decimal arithmetic."""
    if isinstance(value, bool):
        raise ValueError("boolean is not a monetary amount")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid monetary amount") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("monetary amounts must be finite and nonnegative")
    return result


@dataclass(frozen=True)
class Scenario:
    paid_seats: int
    current_monthly_seat_price: Decimal
    alternative_monthly_base: Decimal
    alternative_monthly_per_seat: Decimal = Decimal("0")
    alternative_monthly_operations: Decimal = Decimal("0")
    alternative_monthly_support: Decimal = Decimal("0")
    alternative_monthly_ai: Decimal = Decimal("0")
    alternative_monthly_storage: Decimal = Decimal("0")
    one_time_migration: Decimal = Decimal("0")
    one_time_training: Decimal = Decimal("0")
    months: int = 12
    capability_parity_verified: bool = False
    security_requirements_verified: bool = False

    def __post_init__(self):
        if isinstance(self.paid_seats, bool) or not isinstance(self.paid_seats, int) or self.paid_seats < 1:
            raise ValueError("paid_seats must be a positive integer")
        if isinstance(self.months, bool) or not isinstance(self.months, int) or self.months < 1:
            raise ValueError("months must be a positive integer")
        fields = (
            "current_monthly_seat_price", "alternative_monthly_base",
            "alternative_monthly_per_seat", "alternative_monthly_operations",
            "alternative_monthly_support", "alternative_monthly_ai",
            "alternative_monthly_storage", "one_time_migration",
            "one_time_training",
        )
        for field in fields:
            object.__setattr__(self, field, money(getattr(self, field)))


def compare(scenario: Scenario) -> dict:
    """Return scenarios, not promises. Negative savings means alternative costs more."""
    m = Decimal(scenario.months)
    current = Decimal(scenario.paid_seats) * scenario.current_monthly_seat_price * m
    monthly = (
        scenario.alternative_monthly_base
        + Decimal(scenario.paid_seats) * scenario.alternative_monthly_per_seat
        + scenario.alternative_monthly_operations
        + scenario.alternative_monthly_support
        + scenario.alternative_monthly_ai
        + scenario.alternative_monthly_storage
    )
    alternative = monthly * m + scenario.one_time_migration + scenario.one_time_training
    difference = current - alternative
    feasible = scenario.capability_parity_verified and scenario.security_requirements_verified
    return {
        "currency": "USD",
        "months": scenario.months,
        "paid_seats": scenario.paid_seats,
        "current_total": str(current),
        "alternative_total": str(alternative),
        "difference": str(difference),
        "difference_pct": str((difference / current * 100) if current else Decimal("0")),
        "potential_savings_not_verified": not feasible,
        "migration_feasible": feasible,
        "warning": (
            "Scenario only: not a verified savings claim. Check functional equivalence, "
            "security, migrations, contracts and actual provider invoices."
        ),
    }


def seat_break_even(scenario: Scenario) -> Optional[int]:
    """Smallest paid seat count at which replacement is not more expensive, if possible."""
    variable_delta = scenario.current_monthly_seat_price - scenario.alternative_monthly_per_seat
    fixed = (
        (scenario.alternative_monthly_base + scenario.alternative_monthly_operations
         + scenario.alternative_monthly_support + scenario.alternative_monthly_ai
         + scenario.alternative_monthly_storage) * Decimal(scenario.months)
        + scenario.one_time_migration + scenario.one_time_training
    )
    if variable_delta <= 0:
        return 1 if fixed == 0 and variable_delta == 0 else None
    n = fixed / (variable_delta * Decimal(scenario.months))
    return max(1, int(n.to_integral_value(rounding="ROUND_CEILING")))
