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