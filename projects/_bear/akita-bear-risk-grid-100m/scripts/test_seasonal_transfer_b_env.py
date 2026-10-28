import unittest

import numpy as np

from grid import Grid
from seasonal_transfer_b_env import seasonal_labels, fit_transfer


class SeasonalTransferTest(unittest.TestCase):
    def test_identical_window_boundaries_and_full_reconciliation(self):
        grid = Grid(0, 0, 3, 1, 100)
        muni = np.array([[0, 0, -1]], dtype=np.int16)
        dates = np.array(["2024-03-31", "2024-04-01", "2024-09-30",
                          "2024-10-01", "2025-04-01", "2025-09-30",
                          "2026-04-01"], dtype="datetime64[m]")
        x = np.array([50, 50, 150, 50, 50, 250, 150])
        y = np.full(len(x), 50)
        known = {2024: np.array([[2, 1, 0]]), 2025: np.array([[1, 0, 0]]),
                 2026: np.array([[0, 1, 0]])}
        counts, info = seasonal_labels(grid, muni, x, y, dates, known)
        self.assertEqual(counts[2024].tolist(), [[1, 1, 0]])
        self.assertEqual(counts[2025].tolist(), [[1, 0, 0]])
        self.assertEqual(counts[2026].tolist(), [[0, 1, 0]])
        self.assertEqual(info[2025]["outside_window_reports"], 1)

    def test_mismatch_stops_before_fit(self):
        grid = Grid(0, 0, 1, 1, 100)
        muni = np.array([[0]])
        with self.assertRaisesRegex(ValueError, "c2024"):
            seasonal_labels(grid, muni, [50], [50],
                            np.array(["2024-05-01"], dtype="datetime64[m]"),
                            {2024: np.array([[0]]), 2025: np.array([[0]]),
                             2026: np.array([[0]])})

    def test_fit_uses_train_labels_only(self):
        seen = []

        class Fake:
            def fit(self, X, y):
                seen.append(y.copy())
                return self

            def predict_proba(self, X):
                return np.column_stack([np.full(len(X), .2), np.full(len(X), .8)])

        scores = fit_transfer(np.zeros((3, 28)), np.array([True, False, True]), Fake)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].tolist(), [True, False, True])
        self.assertEqual(scores.tolist(), [.8, .8, .8])


if __name__ == "__main__":
    unittest.main()
