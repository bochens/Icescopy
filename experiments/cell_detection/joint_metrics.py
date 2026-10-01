"""Measure recovery and placement without treating unknown real pixels as empty."""
from __future__ import annotations

from dataclasses import asdict

import numpy as np
from scipy.optimize import linear_sum_assignment

from detector import Circle, same_object


def circle(row):
    return row if isinstance(row, Circle) else Circle(
        float(row['x']), float(row['y']), float(row['radius']))


def match_centers(predictions, references, tolerance):
    """Maximize one-to-one matches, then minimize error in reference radii."""
    if not predictions or not references:
        return []
    distance = np.asarray([[np.hypot(p.x-r.x, p.y-r.y)/r.radius
                            for r in references] for p in predictions])
    allowed = distance <= tolerance
    # A missed match must cost more than the total error of all valid matches.
    penalty = (min(distance.shape)+1)*(tolerance+1)
    rows, columns = linear_sum_assignment(np.where(allowed, distance, penalty))
    return [{'prediction': int(i), 'reference': int(j),
             'error_radii': float(distance[i, j])}
            for i, j in zip(rows, columns) if allowed[i, j]]


def measure_scene(scene, predictions, seeds):
    """Broad recovery uses one radius; accurate placement uses 0.35 radius.

    Explicit invalid-center points have a small 0.15-radius neighborhood. They
    do not label an entire surrounding droplet or patch as water-free.
    """
    truth = [circle(row) for row in scene['targets']]
    predictions = [circle(row) for row in predictions]
    if len(set(seeds)) != len(seeds) or any(i < 0 or i >= len(truth) for i in seeds):
        raise ValueError('Example indices must be distinct and inside the target list.')
    remaining_ids = [i for i in range(len(truth)) if i not in seeds]
    references = [truth[i] for i in remaining_ids]
    broad = match_centers(predictions, references, 1.)
    centered = match_centers(predictions, references, .35)
    for matches in (broad, centered):
        for row in matches:
            row['reference'] = remaining_ids[row['reference']]
    broad_predictions = {row['prediction'] for row in broad}
    centered_predictions = {row['prediction'] for row in centered}
    found = {row['reference'] for row in broad}
    accurate = {row['reference'] for row in centered}
    negatives = [circle(row) for row in scene.get('negatives', [])]
    invalid_centers = [circle(row) for row in scene.get('center_negatives', [])]
    negative_hits = [i for i, p in enumerate(predictions)
                     if any(np.hypot(p.x-n.x, p.y-n.y) < n.radius for n in negatives)]
    invalid_hits = [i for i, p in enumerate(predictions)
                    if any(np.hypot(p.x-n.x, p.y-n.y) <= .15*n.radius
                           for n in invalid_centers)]
    errors = [row['error_radii'] for row in broad]
    complete = scene.get('complete_labels', False)
    return {
        'seeds': list(seeds), 'remaining': len(references),
        'suggestions': len(predictions), 'found': len(broad),
        'centered': len(centered), 'missed': len(references)-len(broad),
        'extras': len(predictions)-len(broad),
        'not_centered': len(predictions)-len(centered),
        'missed_ids': [i for i in remaining_ids if i not in found],
        'not_centered_ids': [i for i in remaining_ids if i not in accurate],
        'extra_indices': [i for i in range(len(predictions)) if i not in broad_predictions],
        'offset_indices': sorted(broad_predictions-centered_predictions),
        'known_negative_indices': negative_hits,
        'invalid_center_indices': invalid_hits,
        'matches': broad, 'centered_matches': centered,
        'median_error_radii': float(np.median(errors)) if errors else None,
        'p90_error_radii': float(np.quantile(errors, .9)) if errors else None,
        'recall': len(broad)/len(references) if references else 1.,
        'centered_recall': len(centered)/len(references) if references else 1.,
        'precision': len(broad)/len(predictions) if complete and predictions else None,
        'centered_precision': len(centered)/len(predictions) if complete and predictions else None,
        'duplicate_existing': sum(any(same_object(p, truth[i]) for i in seeds)
                                  for p in predictions),
        'circles': [asdict(p) for p in predictions],
    }


def summarize(rows):
    """Average example trials within each scene before pooling scene counts."""
    by_scene = {}
    keys = ('remaining', 'suggestions', 'found', 'centered', 'missed', 'extras',
            'not_centered', 'duplicate_existing')
    for entry in rows:
        by_scene.setdefault(entry['scene_id'], []).append(entry)
    means = {name: {key: float(np.mean([row[key] for row in entries])) for key in keys}
             for name, entries in by_scene.items()}
    totals = {key: sum(row[key] for row in means.values()) for key in keys}
    return {'mean_counts_by_scene': means, 'pooled_scene_means': totals,
            'recall': totals['found']/max(1., totals['remaining']),
            'centered_recall': totals['centered']/max(1., totals['remaining'])}
