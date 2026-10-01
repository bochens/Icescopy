"""Native-radius training diagnostics and predeclared synthetic F2 calibration."""
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from benchmark import evaluate, example_trials, subset
from detector import Circle, same_object, scores
from neural_calibration import accepted_prefix_counts


def fixed_trials(count):
    """Three singles and two pairs, fixed from label order before any scores."""
    if count < 3:
        raise ValueError('The manual diagnostic requires at least three targets.')
    first, middle, last = 0, count // 2, count - 1
    return [[first], [middle], [last], [first, middle], [middle, last]]


def native_diagnostic(item, values, seed_ids, threshold):
    """Match within each reference's own radius; unmatched manual pixels are unknown.

    The manual circles are incomplete positive labels. Only explicit reviewed
    negatives count as known mistakes. Every accepted circle remains in output.
    """
    truth, circles = item['truth'], item['circles']
    seeds = [truth[i] for i in seed_ids]
    kept = []
    for raw_index in np.argsort(-values, kind='stable'):
        index = int(raw_index)
        if values[index] < threshold or any(same_object(circles[index], c) for c in seeds):
            continue
        if not any(same_object(circles[index], circles[j]) for j in kept):
            kept.append(index)
    remaining = [i for i in range(len(truth)) if i not in seed_ids]
    matched = []
    if kept and remaining:
        distance = item['distance'][np.ix_(kept, remaining)]
        radii = np.asarray([truth[i].radius for i in remaining])
        valid = distance < radii[None, :]
        rows, columns = linear_sum_assignment(np.where(valid, distance / radii[None, :], 10000.))
        matched = [(kept[r], remaining[c], float(distance[r, c]))
                   for r, c in zip(rows, columns) if valid[r, c]]
    matched_candidates = {m[0] for m in matched}
    found_ids = {m[1] for m in matched}
    negatives = [Circle(float(c['x']), float(c['y']), float(c['radius']))
                 for c in item['scene'].get('negatives', [])]
    known_negative = [i for i in kept if i not in matched_candidates and
                      any(np.hypot(circles[i].x-c.x, circles[i].y-c.y) < c.radius for c in negatives)]
    unknown = [i for i in kept if i not in matched_candidates and i not in known_negative]
    complete = item['scene'].get('complete_labels', False)
    ceiling = int((item['distance'][:, remaining].min(axis=0) <
                   np.asarray([truth[i].radius for i in remaining])).sum()) if remaining and circles else 0
    return {'seeds': list(seed_ids), 'threshold': float(threshold), 'found': len(matched),
            'remaining': len(remaining), 'missed': len(remaining)-len(matched),
            'missed_ids': [i for i in remaining if i not in found_ids],
            'known_negative_detections': len(known_negative), 'known_negative_indices': known_negative,
            'unclassified_additions': len(unknown), 'unclassified_indices': unknown,
            'unmatched_suggestions': len(kept)-len(matched),
            'false_detections': len(kept)-len(matched) if complete else None,
            'precision': len(matched)/len(kept) if complete and kept else None,
            'recall': len(matched)/len(remaining) if remaining else 1.,
            'proposal_ceiling': ceiling, 'accepted': kept, 'matches': matched,
            'duplicate_existing': sum(any(same_object(circles[i], c) for c in seeds) for i in kept)}


def f2_key(found, extras, remaining, threshold):
    """F2 weights missed targets four times extras; ties favor recall then precision."""
    missed = remaining-found
    f2 = 5*found/max(1, 5*found+4*missed+extras)
    recall = found/max(1, remaining)
    precision = found/max(1, found+extras)
    return f2, recall, precision, float(threshold)


def calibrate_f2(prepared, index, head):
    """Exact F2 sweep on separate synthetic calibration scenes, never manual frames.

    Lower scores cannot change earlier greedy duplicate choices. Filtering the
    complete accepted order therefore gives identical selections at every
    higher cutoff. Equal scores enter together under >=; matching is recomputed
    for each prefix by the existing Hungarian assignment helper.
    """
    events, cached, families = [], [], {}
    remaining = 0
    for item in prepared:
        scene = item['scene']
        if (scene['split'] != 'calibration' or not scene['recording'].startswith('neural-synthetic-')
                or not scene.get('complete_labels', False)):
            raise ValueError('F2 calibration requires separate, completely labeled synthetic scenes.')
        family = scene['rendering']['family']
        families.setdefault(family, {'found': 0, 'false_detections': 0, 'remaining': 0})
        for ids in example_trials(len(item['truth'])):
            values = scores(item['banks'][index], subset(item['examples'][index], ids), 'learned', head)
            if not np.isfinite(values).all():
                raise ValueError('Nonfinite calibration scores.')
            changes, count = accepted_prefix_counts(item, values, ids, minimum=0.)
            events.extend((score, tp, fp, family) for score, tp, fp in changes)
            remaining += count
            families[family]['remaining'] += count
            cached.append((item, ids, values, changes, count))
    if not cached:
        raise ValueError('No synthetic calibration scenes.')
    thresholds = np.unique([0., 1., *(e[0] for e in events)])[::-1]
    events.sort(key=lambda e: e[0], reverse=True)
    position = found = extras = 0
    best = None
    for threshold in thresholds:
        while position < len(events) and events[position][0] >= threshold:
            _, tp, fp, family = events[position]
            found += tp; extras += fp
            families[family]['found'] += tp; families[family]['false_detections'] += fp
            position += 1
        key = f2_key(found, extras, remaining, threshold)
        if best is None or key > best[0]:
            best = (key, found, extras, {name: dict(c) for name, c in families.items()})
    key, found, extras, family_counts = best
    probes = np.unique([0., 1., key[3], *np.quantile(thresholds, [0, .25, .5, .75, 1])])
    # Two trials per scene suffice to guard prefix and tie semantics cheaply.
    verified = [trial for i, trial in enumerate(cached)
                if i == 0 or i == len(cached)-1 or cached[i-1][0] is not trial[0]
                or cached[i+1][0] is not trial[0]]
    for threshold in probes:
        for item, ids, values, changes, count in verified:
            actual = evaluate(item, values, ids, threshold)
            expected = (sum(e[1] for e in changes if e[0] >= threshold),
                        sum(e[2] for e in changes if e[0] >= threshold))
            if expected != (actual['found'], actual['false_detections']):
                raise AssertionError('F2 prefix sweep disagrees with the evaluator.')
    for counts in family_counts.values():
        counts.update(f2=f2_key(counts['found'], counts['false_detections'], counts['remaining'], key[3])[0],
                      recall=counts['found']/max(1, counts['remaining']),
                      precision=counts['found']/max(1, counts['found']+counts['false_detections']))
    result = {'threshold': key[3], 'f2': key[0], 'recall': key[1], 'precision': key[2],
              'found': found, 'false_detections': extras, 'remaining': remaining,
              'by_family': family_counts, 'groups': sorted({p['scene']['group'] for p in prepared}),
              'selection': 'Predeclared maximum F2; misses cost four times extras. Synthetic calibration only.',
              'search': {'method': 'Exact accepted-score sweep including endpoints 0 and 1.',
                         'thresholds': len(thresholds), 'events': len(events),
                         'verified_thresholds': len(probes), 'verified_trials': len(verified)}}
    head['threshold'] = key[3]; head['calibration'] = result
    return result
