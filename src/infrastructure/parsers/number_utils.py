from __future__ import annotations

import re


def clean_number(text, default: str = "0", to_int: bool = False):
    """Extract number from a string."""
    if text is None or text == "N/A":
        return 0 if to_int else default

    digits = "".join(re.findall(r"\d+", str(text)))
    if not digits:
        return 0 if to_int else default
    return int(digits) if to_int else digits
