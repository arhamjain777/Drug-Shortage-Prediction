"""Transaction-style stock ledger rules. Quantity = opening + sum(movements)."""
from __future__ import annotations
from dataclasses import dataclass

SIGN = {"receipt": 1, "issue": -1, "transfer_in": 1, "transfer_out": -1, "adjustment": 1}


class InsufficientStock(ValueError):
    pass


@dataclass(frozen=True)
class Movement:
    kind: str
    quantity: float          # always positive, except 'adjustment' which is signed
    reason: str = ""
    user: str = ""


def validate_movement(m: Movement) -> None:
    if m.kind not in SIGN:
        raise ValueError(f"unknown movement kind: {m.kind}")
    if m.kind == "adjustment":
        if m.quantity == 0:
            raise ValueError("adjustment quantity must be non-zero")
        if not m.reason.strip() or not m.user.strip():
            raise ValueError("adjustments require a reason and a user")
    elif m.quantity <= 0:
        raise ValueError("quantity must be > 0")


def apply_movement(balance: float, m: Movement) -> float:
    validate_movement(m)
    new = balance + SIGN[m.kind] * m.quantity
    if new < 0:
        raise InsufficientStock(f"would leave balance {new:g} < 0")
    return new


def reconcile(opening: float, movements) -> float:
    bal = opening
    for m in movements:
        bal = apply_movement(bal, m)
    return bal
