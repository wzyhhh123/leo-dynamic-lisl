"""Directed aggregate OD commodities used by the Gate D fluid model."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Commodity:
    commodity_id: str
    source: str
    destination: str
    weight: float = 1.0

    def __post_init__(self):
        if not self.commodity_id or not self.source or not self.destination:
            raise ValueError("EMPTY_COMMODITY_FIELD")
        if self.source == self.destination:
            raise ValueError("COMMODITY_SOURCE_EQUALS_DESTINATION")
        if self.weight <= 0.0:
            raise ValueError("NONPOSITIVE_COMMODITY_WEIGHT")

    @classmethod
    def from_dict(cls, row):
        return cls(str(row["commodity_id"]), str(row["source"]),
                   str(row["destination"]), float(row.get("weight", 1.0)))

    def to_dict(self):
        return {"commodity_id": self.commodity_id, "source": self.source,
                "destination": self.destination, "weight": self.weight}
