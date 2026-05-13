# SAFETY CRITICAL — DO NOT MODIFY VALUES
# These limits prevent dangerous thermal exposure to research subjects.
# Source: examples/medoc-python-api/C/inc/constants.h
#
# If limits must legitimately change, recompute _CHECKSUM with:
#   python3 -c "import hashlib; from medoc.safety import _TABLE; print(hashlib.sha256(repr(_TABLE).encode()).hexdigest())"
# then update _CHECKSUM below and commit deliberately.

import hashlib

_TABLE = (
    (56.0,      0),
    (55.0,     50),
    (52.0,    400),
    (51.0,   1000),
    (50.0,   5000),
    (49.0,  10000),
    (47.0,  60000),
    ( 6.0, 300000),
    ( 0.0, 300000),
    (-10.0, 300000),
)

_CHECKSUM = "93738341022f2afb3ef47e85980e89fc537c6870476b552cf803b4159cb4eeee"


def _validate() -> None:
    actual = hashlib.sha256(repr(_TABLE).encode()).hexdigest()
    if actual != _CHECKSUM:
        raise RuntimeError(
            "Safety limits table checksum mismatch — do not edit _TABLE without updating _CHECKSUM. "
            f"Expected {_CHECKSUM!r}, got {actual!r}"
        )


_validate()


def get_safety_ms(temp: float) -> int:
    """Return the maximum milliseconds the thermode may stay at this temperature."""
    for threshold, max_ms in _TABLE:
        if temp >= threshold:
            return max_ms
    return _TABLE[-1][1]


def get_safety_level(temp: float) -> float:
    """Return the temperature threshold bracket that applies to this temperature."""
    for threshold, _ in _TABLE:
        if temp >= threshold:
            return threshold
    return _TABLE[-1][0]
