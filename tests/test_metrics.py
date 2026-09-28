from src.evaluation.metrics import mae, rmse, precision_recall_f1, csi


def test_mae():
    assert mae([10, 20, 30], [12, 18, 33]) == 2.3333333333333335


def test_rmse():
    assert round(rmse([10, 20, 30], [12, 18, 33]), 6) == 2.380476


def test_precision_recall_f1():
    precision, recall, f1 = precision_recall_f1(
        [1, 1, 0, 1],
        [1, 0, 0, 1]
    )

    assert precision == 1.0
    assert round(recall, 2) == 0.67
    assert round(f1, 2) == 0.80


def test_csi():
  assert round(rmse([10, 20, 30], [12, 18, 33]), 6) == 2.380476
