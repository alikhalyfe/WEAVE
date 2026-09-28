def blend_forecasts(forecasts, weights):
    """
    Combine multiple model forecasts using their weights.

    Parameters
    ----------
    forecasts : dict
        Forecast values from each model.
        Example:
        {
            "model_a": 80,
            "model_b": 70,
            "ai_model": 90
        }

    weights : dict
        Weight assigned to each model.
        Example:
        {
            "model_a": 0.3,
            "model_b": 0.2,
            "ai_model": 0.5
        }

    Returns
    -------
    float
        Final blended forecast.
    """

    blended_value = sum(
        forecasts[model] * weights[model]
        for model in forecasts
    )

    return blended_value