"""Model B (Random Forest) and the AI Model.

AI Model uses scikit-learn's HistGradientBoostingRegressor rather than
XGBoost -- xgboost isn't an installed dependency (requirements.txt only
has scikit-learn among ML libs) and HistGradientBoostingRegressor is a
gradient-boosted-tree model of the same family, already available. Swap
in real XGBoost later by adding it to requirements.txt and pointing
AIModel's constructor at xgboost.XGBRegressor if the team wants that
specific library.

Each instance is trained for exactly one (target_variable, lead_time_hours)
pair, matching how these two are normally trained (one model per forecast
horizon) rather than encoding lead time as a feature.
"""

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor

from src.data_pipeline.model_interface import ForecastModel


class _TreeForecastModel(ForecastModel):
    regressor_cls = None
    drop_na_features = False  # RandomForestRegressor can't handle NaN features

    def __init__(self, target_variable: str, lead_time_hours: int, feature_columns: list[str], **regressor_kwargs):
        self.target_variable = target_variable
        self.lead_time_hours = lead_time_hours
        self.feature_columns = feature_columns
        self.model_ = self.regressor_cls(**regressor_kwargs)
        self.is_fitted_ = False

    def _target_column(self) -> str:
        return f"{self.target_variable}_target_{self.lead_time_hours}h"

    def fit(self, train_df: pd.DataFrame) -> "_TreeForecastModel":
        target_col = self._target_column()
        columns = [*self.feature_columns, target_col]
        rows = train_df[columns].dropna() if self.drop_na_features else train_df[columns].dropna(subset=[target_col])
        self.model_.fit(rows[self.feature_columns], rows[target_col])
        self.is_fitted_ = True
        return self

    def predict(self, features: pd.DataFrame, lead_time_hours: int) -> pd.DataFrame:
        if lead_time_hours != self.lead_time_hours:
            raise ValueError(
                f"{type(self).__name__} was trained for lead_time_hours="
                f"{self.lead_time_hours}, cannot predict for {lead_time_hours}."
            )
        if not self.is_fitted_:
            raise RuntimeError(f"{type(self).__name__} must be fit() before predict().")

        rows = features[self.feature_columns]
        usable = rows.dropna() if self.drop_na_features else rows
        forecast = pd.Series(index=features.index, dtype=float)
        forecast.loc[usable.index] = self.model_.predict(usable)

        return pd.DataFrame(
            {
                "timestamp": features["timestamp"],
                "location": features["location"],
                "lead_time_hours": lead_time_hours,
                "forecast": forecast,
            }
        )


class RandomForestModel(_TreeForecastModel):
    """Model B."""

    regressor_cls = RandomForestRegressor
    drop_na_features = True

    def __init__(self, target_variable, lead_time_hours, feature_columns, n_estimators=100, max_depth=15, n_jobs=-1, random_state=0, **kwargs):
        super().__init__(
            target_variable, lead_time_hours, feature_columns,
            n_estimators=n_estimators, max_depth=max_depth, n_jobs=n_jobs, random_state=random_state, **kwargs,
        )


class AIModel(_TreeForecastModel):
    """AI Model -- gradient-boosted trees (HistGradientBoostingRegressor).
    Handles NaN features natively, unlike RandomForestModel."""

    regressor_cls = HistGradientBoostingRegressor
    drop_na_features = False

    def __init__(self, target_variable, lead_time_hours, feature_columns, max_iter=150, random_state=0, **kwargs):
        super().__init__(
            target_variable, lead_time_hours, feature_columns,
            max_iter=max_iter, random_state=random_state, **kwargs,
        )
