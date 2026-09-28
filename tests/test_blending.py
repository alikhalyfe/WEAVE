from src.blending.weight_engine import calculate_weights
from src.blending.blender import blend_forecasts


# Historical model errors
model_errors = {
    "model_a": 10,
    "model_b": 20,
    "ai_model": 5
}

# Calculate adaptive weights
weights = calculate_weights(model_errors)

print("Model weights:")
for model, weight in weights.items():
    print(f"{model}: {weight:.3f}")


# Current forecasts
forecasts = {
    "model_a": 80,
    "model_b": 70,
    "ai_model": 90
}

# Create blended forecast
blended = blend_forecasts(forecasts, weights)

print(f"\nBlended forecast: {blended:.2f}")