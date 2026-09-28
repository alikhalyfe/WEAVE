import pandas as pd
from src.evaluation.evaluation import evaluate_multiple_models


def run_evaluation(file_path, observed_column, prediction_columns):
    data = pd.read_csv(file_path)

    results = evaluate_multiple_models(
        data,
        observed_column,
        prediction_columns
    )

    print("\nEvaluation Results:")
    print(results)

    return results


if __name__ == "__main__":
    print("Evaluation script ready.")
    print("Waiting for actual model prediction data.")