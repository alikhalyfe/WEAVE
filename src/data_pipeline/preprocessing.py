"""Pure ERA5 unit-conversion helpers.

The 5 committed city CSVs are already converted (Kelvin->C, metres->mm,
wind speed, season), so these aren't applied to them. They exist so the
conversions are tested and reusable if raw ERA5 ever needs ingesting.
"""

from src.data_pipeline.config import MONTH_TO_SEASON


def kelvin_to_celsius(temp_k):
    return temp_k - 273.15


def meters_to_mm(precip_m):
    return precip_m * 1000


def compute_wind_speed(u10, v10):
    return (u10 ** 2 + v10 ** 2) ** 0.5


def season_from_month(month: int) -> str:
    return MONTH_TO_SEASON[month]
