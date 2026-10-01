"""One prediction cannot count for two droplets, and greedy order cannot lose a match."""
import numpy as np

from auto_cell_ml.code.evaluate import match_centers


def test_one_to_one_assignment_recovers_ambiguous_neighbor():
    predictions = [{'x': 2, 'y': 0}, {'x': 0, 'y': 0}]
    result = match_centers(predictions, [[0, 0, 10], [5, 0, 10]])
    assert (result['matched'], result['missed'], result['extra_or_misplaced']) == (2, 0, 0)


def test_duplicates_and_empty_predictions():
    predictions = [{'x': 0, 'y': 0}, {'x': 1, 'y': 0}, {'x': 20, 'y': 0}]
    result = match_centers(predictions, [[0, 0, 10]])
    assert (result['matched'], result['missed'], result['extra_or_misplaced']) == (1, 0, 2)
    assert match_centers([], [[0, 0, 10]])['missed'] == 1
    assert match_centers(predictions, np.empty((0, 3)))['extra_or_misplaced'] == 3
