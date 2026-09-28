import numpy as np


def mae(y_true, y_pred):
    """Calculate Mean Absolute Error."""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    return np.mean(np.abs(y_true - y_pred))


def rmse(y_true, y_pred):
    """Calculate Root Mean Square Error."""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    return np.sqrt(np.mean((y_true - y_pred) ** 2))


def precision_recall_f1(y_true, y_pred):
    """Calculate precision, recall and F1 for binary events."""

    y_true = np.array(y_true).astype(bool)
    y_pred = np.array(y_pred).astype(bool)

    true_positive = np.sum(y_true & y_pred)
    false_positive = np.sum(~y_true & y_pred)
    false_negative = np.sum(y_true & ~y_pred)

    precision = (
        true_positive / (true_positive + false_positive)
        if (true_positive + false_positive) > 0
        else 0.0
    )

    recall = (
        true_positive / (true_positive + false_negative)
        if (true_positive + false_negative) > 0
        else 0.0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return precision, recall, f1


def csi(y_true, y_pred):
    """Calculate Critical Success Index for binary events."""

    y_true = np.array(y_true).astype(bool)
    y_pred = np.array(y_pred).astype(bool)

    true_positive = np.sum(y_true & y_pred)
    false_positive = np.sum(~y_true & y_pred)
    false_negative = np.sum(y_true & ~y_pred)

    denominator = true_positive + false_positive + false_negative

    return true_positive / denominator if denominator > 0 else 0.0