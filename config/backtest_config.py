"""Aggregation-only settings for the CSV-only standalone V3 project."""
from dataclasses import dataclass

@dataclass(frozen=True)
class StructureConfig:
    source_minutes: int = 15
    structure_minutes: int = 240
    anchor_minutes_utc: int = 0
    require_complete: bool = True
    fill_missing: bool = False

    def __post_init__(self):
        if self.source_minutes <= 0 or self.structure_minutes <= 0:
            raise ValueError('Timeframes must be positive.')
        if self.structure_minutes % self.source_minutes:
            raise ValueError('Structure timeframe must be divisible by source timeframe.')
        if self.anchor_minutes_utc % self.source_minutes:
            raise ValueError('Anchor must align with the source grid.')
        if not 0 <= self.anchor_minutes_utc < self.structure_minutes:
            raise ValueError('Anchor must be within one structure interval.')
        if not self.require_complete or self.fill_missing:
            raise ValueError('Only complete bars are indicators; missing candles are never filled.')

    @property
    def expected_source_count(self):
        return self.structure_minutes // self.source_minutes
