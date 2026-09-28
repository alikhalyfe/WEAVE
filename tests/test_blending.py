from src.blending.weight_engine import calculate_weights
from src.blending.blender import blend_forecasts


def test_blended_forecast():
    model_errors = {
        "model_a": 10,
        "model_b": 20,
        "ai_model": 5
    }

    weights = calculate_weights(model_errors)

    forecasts = {
        "model_a": 80,
        "model_b": 70,
        "ai_model": 90
    }

    blended = blend_forecasts(forecasts, weights)

    assert round(blended, 2) == 84.29