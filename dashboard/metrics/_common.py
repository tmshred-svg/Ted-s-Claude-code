from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Cell:
    label: str
    value: Optional[float] = None
    unit: str = ""
    asof: Optional[str] = None
    source: str = ""
    note: str = ""
    extra: dict = field(default_factory=dict)
    series_id: Optional[str] = None

    @property
    def display(self) -> str:
        if self.value is None:
            return f"n/a — {self.note or 'source not configured'}"
        if self.unit == "%":
            return f"{self.value * 100:.2f}%"
        if self.unit == "bp":
            return f"{self.value:.0f} bp"
        if self.unit == "$bn":
            return f"${self.value / 1e9:,.1f} bn"
        if self.unit == "$mm":
            return f"${self.value / 1e6:,.0f} mm"
        if self.unit == "idx":
            return f"{self.value:,.2f}"
        if self.unit == "ratio":
            return f"{self.value:.2f}"
        return f"{self.value:,.4g}"


def fmt_pct(x):
    return "n/a" if x is None else f"{x * 100:+.2f}%"


def fmt_bp(x):
    return "n/a" if x is None else f"{x * 1e4:+.0f} bp"


def fmt_num(x, prec=2):
    return "n/a" if x is None else f"{x:+.{prec}f}"
