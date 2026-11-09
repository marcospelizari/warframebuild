"""Enemy stats at a level (saved Enemy_Level_Scaling, Common Features of Stat Scaling).

Each stat multiplier blends two endpoint curves `f(q) = 1 + C·q^E`, `q = level - base level`,
with a smoothstep weight over `q` in [L, U], evaluated in binary32 in the page's order.
"""

import struct
from dataclasses import dataclass


def f32(x: float) -> float:
    """`x` stored as an IEEE 754 binary32 value."""
    return float(struct.unpack("f", struct.pack("f", x))[0])


@dataclass(frozen=True)
class Curve:
    coefficient: float
    exponent: float

    def at(self, q: float) -> float:
        return f32(1 + f32(f32(self.coefficient) * f32(f32(q) ** f32(self.exponent))))


@dataclass(frozen=True)
class Scaling:
    low: Curve  # f1, lower endpoint curve
    high: Curve  # f2, upper endpoint curve
    lower: float  # L
    upper: float  # U

    def multiplier(self, q: float) -> float:
        """`q` below 0 (level under the base level) counts as 0: the base value."""
        q = max(q, 0.0)
        t = min(max(f32(f32(q - self.lower) / f32(self.upper - self.lower)), 0.0), 1.0)
        s = f32(f32(t * t) * f32(3 - f32(2 * t)))
        f1, f2 = self.low.at(q), self.high.at(q)
        return f32(f1 + f32(f32(f2 - f1) * s))

    def value(self, base: float, q: float) -> float:
        return f32(f32(base) * self.multiplier(q))
