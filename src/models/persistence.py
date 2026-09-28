"""Model A: persistence baseline. Naive "no change" forecast -- the value
at time t is used as the forecast for t+lead_time_hours. No training."""

import pandas as pd

from src.data_pipeline.model_interface import ForecastModel


class PersistenceModel(ForecastModel):
    def __init__(self, target_variable: str):
        self.target_variable = target_variable

    def predict(self, features: pd.DataFrame, lead_time_hours: int) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "timestamp": features["timestamp"],
                "location": features["location"],
                "lead_time_hours": lead_time_hours,
                "forecast": features[self.target_variable],
            }
        )
