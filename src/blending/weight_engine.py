import numpy as np
from scipy.optimize import nnls


def optimal_weights(forecasts, actual):
    """
    Skill-optimal linear combination weights (constrained stacking).

    Solves min ||forecasts @ w - actual||^2 subject to w >= 0 with NNLS,
    then normalises w to sum to 1 so the blend stays a convex combination
    (interpretable as model shares, and never extrapolates beyond the
    members). Unlike inverse-error weighting this accounts for correlated
    errors between models: two near-identical models don't both get
    counted as independent evidence.

    Parameters
    ----------
    forecasts : array-like, shape (n_samples, n_models)
    actual : array-like, shape (n_samples,)

    Returns
    -------
    numpy.ndarray, shape (n_models,)
        Non-negative weights summing to 1 (equal weights if NNLS returns
        all zeros, e.g. when every forecast is zero).
    """
    forecasts = np.asarray(forecasts, dtype=float)
    actual = np.asarray(actual, dtype=float)
    w, _ = nnls(forecasts, actual)
    total = w.sum()
    if total <= 0:
        return np.full(forecasts.shape[1], 1.0 / forecasts.shape[1])
    return w / total


def calculate_weights(model_errors, epsilon=1e-6):
    """
    Calculate model weights using inverse MAE.

    Parameters
    ----------
    model_errors : dict
        Dictionary containing model names and their historical MAE.
        Example:
        {
            "model_a": 10,
            "model_b": 20,
            "ai_model": 5
        }

    epsilon : float
        Small value to prevent division by zero.

    Returns
    -------
    dict
        Normalized weights for each model.
    """

    inverse_errors = {
        model: 1 / (error + epsilon)
        for model, error in model_errors.items()
    }

    total = sum(inverse_errors.values())

    weights = {
        model: value / total
        for model, value in inverse_errors.items()
    }

    return weights