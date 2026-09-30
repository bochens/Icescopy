"""Pure single-current-frame selection with persistent, caller-owned cell IDs.

Saved positions are used as supplied. A caller with moving cells must supply
all current positions, resolved from its own keyframes. This module does not
read other frames, infer movement, create keyframes, or detect freezing.
"""
from __future__ import annotations

from dataclasses import asdict
import math

from detector import Circle, detect, preprocess_image, same_object, validate_examples


STATE_VERSION = 1


def _id(value):
    if type(value) is not int or value < 0:
        raise ValueError('Cell IDs must be nonnegative integers.')
    return value


def _circle(row):
    if not isinstance(row, dict) or set(row) != {'x', 'y', 'radius'}:
        raise ValueError('Each circle must contain exactly x, y and radius.')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in row.values()):
        raise ValueError('Circle coordinates and radius must be numbers.')
    return Circle(**row)


def _inside(circle, shape):
    if not (0 <= circle.x < shape[1] and 0 <= circle.y < shape[0]):
        raise ValueError('Known cell centers must be inside the current frame.')


def validate_state(state):
    """Return a new canonical state, or fail without modifying the input."""
    required = {'version', 'image_size', 'next_id', 'cells'}
    if (not isinstance(state, dict) or set(state) != required or
            type(state['version']) is not int or state['version'] != STATE_VERSION):
        raise ValueError('Unsupported or malformed cell-state schema.')
    size = state['image_size']
    if (not isinstance(size, dict) or set(size) != {'width', 'height'} or
            any(type(v) is not int or v <= 0 for v in size.values())):
        raise ValueError('State image_size needs positive integer width and height.')
    next_id = _id(state['next_id'])
    if not isinstance(state['cells'], list):
        raise ValueError('State cells must be a list.')
    cells = []
    seen = set()
    for row in state['cells']:
        if not isinstance(row, dict) or set(row) != {'id', 'circle', 'source'}:
            raise ValueError('Each saved cell needs id, circle and source.')
        cell_id = _id(row['id'])
        if cell_id in seen or cell_id >= next_id:
            raise ValueError('Saved IDs must be unique and smaller than next_id.')
        if row['source'] not in ('manual', 'detected'):
            raise ValueError('Cell source must be manual or detected.')
        circle = _circle(row['circle'])
        seen.add(cell_id)
        cells.append({'id': cell_id, 'circle': asdict(circle), 'source': row['source']})
    return {'version': STATE_VERSION, 'image_size': dict(size), 'next_id': next_id, 'cells': cells}


def detect_current_frame(frame, examples=(), *, state=None, existing=(),
                         example_ids=(), current_positions=None, remove_ids=(),
                         color_order='RGB', method='template', threshold=.75,
                         encoder=None, head=None, detector=None):
    """Select on one frame and return new state plus only newly detected cells.

    `examples` and `existing` contain Circle objects in current-frame pixels.
    `example_ids` selects saved cells after current_positions is applied.
    `current_positions`, when supplied, is a complete list of {id, circle}
    for retained saved cells. IDs cannot be renamed or silently dropped.
    `remove_ids` is the explicit user-edit path; removed IDs are never reused.
    All arguments and the input state remain unchanged even if detection fails.
    """
    image = preprocess_image(frame, color_order)
    shape = image.shape[:2]
    size = {'width': shape[1], 'height': shape[0]}
    if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('Threshold must be between zero and one.')
    if state is None:
        working = {'version': STATE_VERSION, 'image_size': size, 'next_id': 0, 'cells': []}
    else:
        working = validate_state(state)
    by_id = {row['id']: row for row in working['cells']}
    removals = [_id(i) for i in remove_ids]
    if len(removals) != len(set(removals)) or not set(removals) <= set(by_id):
        raise ValueError('remove_ids must name each existing cell at most once.')
    working['cells'] = [row for row in working['cells'] if row['id'] not in removals]
    by_id = {row['id']: row for row in working['cells']}
    if current_positions is not None:
        if not isinstance(current_positions, list):
            raise ValueError('current_positions must be a complete list of id and circle records.')
        updated = {}
        for row in current_positions:
            if not isinstance(row, dict) or set(row) != {'id', 'circle'}:
                raise ValueError('Each current position must contain exactly id and circle.')
            cell_id = _id(row['id'])
            if cell_id in updated:
                raise ValueError('Current position IDs must be unique.')
            circle = _circle(row['circle'])
            updated[cell_id] = asdict(circle)
        if set(updated) != set(by_id):
            raise ValueError('Current positions must retain every saved ID and introduce no new IDs.')
        for cell_id, circle in updated.items():
            by_id[cell_id]['circle'] = circle
    elif working['image_size'] != size and by_id:
        raise ValueError('A changed frame size requires complete current_positions.')
    working['image_size'] = size

    def remember(circle, source):
        if not isinstance(circle, Circle):
            raise ValueError('examples and existing must contain Circle objects.')
        matches = [row for row in working['cells'] if same_object(circle, Circle(**row['circle']))]
        if len(matches) > 1:
            raise ValueError('Circle overlaps multiple known cells; select an explicit example_id.')
        if matches:
            return matches[0]['id']
        cell_id = working['next_id']
        working['next_id'] += 1
        row = {'id': cell_id, 'circle': asdict(circle), 'source': source}
        working['cells'].append(row)
        by_id[cell_id] = row
        return cell_id

    for circle in existing:
        remember(circle, 'manual')
    ids = [_id(i) for i in example_ids]
    if len(ids) != len(set(ids)) or not set(ids) <= set(by_id):
        raise ValueError('example_ids must select unique existing IDs.')
    for circle in examples:
        _inside(circle, shape)
        cell_id = remember(circle, 'manual')
        if cell_id not in ids:
            ids.append(cell_id)
    resolved_examples = [Circle(**by_id[i]['circle']) for i in ids]
    validate_examples(image, resolved_examples)
    protected = [Circle(**row['circle']) for row in working['cells']]
    select = detect if detector is None else detector
    results = select(image, resolved_examples, protected, method, threshold, encoder, head)
    suggestions = []
    for result in results:
        circle = _circle(result['circle'])
        _inside(circle, shape)
        score = float(result['score'])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('Detector returned an invalid score.')
        # Protect the boundary even when an alternate detector is supplied.
        if any(same_object(circle, Circle(**row['circle'])) for row in working['cells']):
            continue
        cell_id = remember(circle, 'detected')
        suggestions.append({'id': cell_id, 'circle': asdict(circle), 'score': score})
    return {'state': working, 'suggestions': suggestions, 'example_ids': ids}
