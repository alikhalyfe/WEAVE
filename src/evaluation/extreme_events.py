import numpy as np


def classify_heavy_rain(precipitation, threshold=50.0):
    """Classify heavy rainfall events."""
    return np.array(precipitation) >= threshold


def classify_heat(temperature, threshold=35.0):
    """Classify high-temperature events."""
    return np.array(temperature) >= threshold


def classify_high_wind(wind_speed, threshold=15.0):
    """Classify high-wind events."""
    return np.array(wind_speed) >= threshold


def event_metrics(y_true, y_pred):
    """Calculate precision, recall, F1 and CSI for an extreme event."""

    y_true = np.array(y_true).astype(bool)
    y_pred = np.array(y_pred).astype(bool)

    true_positive = np.sum(y_true & y_pred)
    false_positive = np.sum(~y_true & y_pred)
    false_negative = np.sum(y_true & ~y_pred)

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive > 0
        else 0.0
    )

    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative > 0
        else 0.0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    csi_denominator = true_positive + false_positive + false_negative

    csi = (
        true_positive / csi_denominator
        if csi_denominator > 0
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "csi": csi
    }