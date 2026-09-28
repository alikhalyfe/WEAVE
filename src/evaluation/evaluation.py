import pandas as pd

from src.evaluation.metrics import mae, rmse


def evaluate_model(y_true, y_pred):
    """
    Calculate MAE and RMSE for one forecast model.
    """
    return {
        "MAE": mae(y_true, y_pred),
        "RMSE": rmse(y_true, y_pred)
    }


def load_observed_data(file_path):
    """
    Load observed ERA5 weather data.
    """
    return pd.read_csv(file_path)


if __name__ == "__main__":
    data_path = "data/sample/era5_pune_test_clean.csv"

    data = load_observed_data(data_path)

    print("Dataset loaded successfully.")
    print(f"Rows: {len(data)}")
    print("Columns:")
    print(list(data.columns))