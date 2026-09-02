"""Indian-first phone helpers. Never log full numbers."""

from __future__ import annotations

import re


def digits_only(number: str | None) -> str:
    return re.sub(r"\D", "", number or "")


def normalize_phone(number: str | None) -> str | None:
    raw = (number or "").strip()
    if not raw:
        return None
    digits = digits_only(raw)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91{digits}"
    if raw.startswith("+") and 10 <= len(digits) <= 15:
        return f"+{digits}"
    return None


def looks_like_phone(number: str | None) -> bool:
    return normalize_phone(number) is not None and len(digits_only(number)) >= 10


def mask_phone(number: str | None) -> str:
    if not number:
        return ""
    digits = number.strip()
    if len(digits) <= 6:
        return "*" * len(digits)
    return f"{digits[:3]}******{digits[-4:]}"


def validate_phone(number: str | None) -> str:
    normalized = normalize_phone(number)
    if not normalized:
        raise ValueError("Enter a valid Indian mobile, e.g. 98765 43210.")
    return normalized
