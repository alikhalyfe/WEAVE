"""Interface future forecast models (persistence baseline, Random Forest,
XGBoost, ...) implement, so Member 2 can plug models in without touching
the data pipeline (Task 7). No concrete/fabricated forecasts here."""

from abc import ABC, abstractmethod

import pandas as pd


class ForecastModel(ABC):
    @abstractmethod
    def predict(self, features: pd.DataFrame, lead_time_hours: int) -> pd.DataFrame:
        """Returns a DataFrame with columns:
        timestamp, location, lead_time_hours, forecast
        """
        raise NotImplementedError
