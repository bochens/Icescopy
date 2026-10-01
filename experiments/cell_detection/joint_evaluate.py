"""Compare the joint detector with the saved first-run detector on manual photos.

These images entered training. This script measures training recovery and
placement; it does not estimate accuracy on new recordings.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw

from detector import read_image, same_object
from hybrid_data import sha256
from joint_metrics import circle, measure_scene, summarize
from single_frame import detect_current_frame
from water_metrics import fixed_trials


def baseline_predictions(entry, seeds, scene):
    if entry['truth'] != scene['targets']:
        raise ValueError('Baseline reference circles differ from current manual labels.')
    rows = [r for r in entry['results'] if r['method'] == 'updated' and r['seeds'] == seeds]
    if len(rows) != 1:
        raise ValueError('Expected one saved actual-v1 result per example selection.')
    row = rows[0]
    banks = [b for b in entry['proposal_banks'] if abs(b['radius']-row['proposal_radius']) < 1e-6]
    if len(banks) != 1:
        raise ValueError('Cannot resolve saved proposal geometry.')
    return [banks[0]['proposals'][i] for i in row['accepted']], row['threshold']


def preview(image, scene, metric, title, width=1000):
    scale = width/image.shape[1]
    height = round(image.shape[0]*scale)
    canvas = Image.new('RGB', (width, height+66), 'white')
    canvas.paste(Image.fromarray(np.uint8(np.clip(image, 0, 1)*255)).resize((width, height)), (0, 66))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 7), f"{title}: {metric['centered']}/{metric['remaining']} centered; "
              f"{metric['found']} recovered; {metric['extras']} extra", fill='black')
    draw.text((10, 27), 'Green centered | Yellow offset | Orange extra | Cyan examples | Magenta reference needing correction', fill='black')
    draw.text((10, 45), 'Training image: this is not an independent accuracy test.', fill='black')

    def mark(row, color, line=2):
        c = circle(row)
        x, y, r = c.x*scale, c.y*scale+66, c.radius*scale
        draw.ellipse((x-r, y-r, x+r, y+r), outline=color, width=line)

    accurate = {r['prediction'] for r in metric['centered_matches']}
    offset = set(metric['offset_indices'])
    for i, row in enumerate(metric['circles']):
        mark(row, '#29e85b' if i in accurate else '#ffe34b' if i in offset else '#ff912e')
    for i in metric['not_centered_ids']:
        mark(scene['targets'][i], '#f151e2', 2)
    for i in metric['seeds']:
        mark(scene['targets'][i], '#00d8ff', 3)
    return canvas


def state_audit(model, scene, threshold):
    """Exercise repeated current-frame selection with the real trained detector."""
    raw = cv2.imread(scene['source'], cv2.IMREAD_UNCHANGED)
    examples = [circle(scene['targets'][i]) for i in (0, len(scene['targets'])//2)]

    def select(image, supplied, protected, method, cutoff, encoder, head):
        return model.predict(image, supplied, protected=protected, threshold=cutoff)

    start = time.perf_counter()
    first = detect_current_frame(raw, examples, color_order='BGR', threshold=threshold, detector=select)
    saved = deepcopy(first['state'])
    repeated = detect_current_frame(raw, state=first['state'], example_ids=first['example_ids'],
                                    color_order='BGR', threshold=threshold, detector=select)
    # Same dimensions, changed appearance, as with a later frame in a recording.
    altered = np.clip(raw.astype(np.float32)*.86, 0, np.iinfo(raw.dtype).max()).astype(raw.dtype)
    changed = detect_current_frame(altered, state=first['state'], example_ids=first['example_ids'],
                                   color_order='BGR', threshold=threshold, detector=select)
    known = [circle(r['circle']) for r in saved['cells']]
    duplicate = sum(any(same_object(circle(r['circle']), c) for c in known)
                    for r in changed['suggestions'])
    if first['state'] != saved or repeated['suggestions'] or duplicate:
        raise AssertionError('Repeated-frame identity or duplicate guard failed.')
    for row in saved['cells']:
        if row not in changed['state']['cells']:
            raise AssertionError('Existing cell geometry or identity changed.')
    return {'scene_id': scene['id'], 'first_additions': len(first['suggestions']),
            'repeat_additions': len(repeated['suggestions']),
            'brightness_changed_additions': len(changed['suggestions']),
            'duplicate_existing': duplicate, 'existing_records_unchanged': True,
            'seconds_three_calls': time.perf_counter()-start,
            'scope': 'Decoded frame arrays; no application or video-decoder integration.'}


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ('checkpoint', 'manual-labels', 'baseline-report', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--threshold', type=float, required=True)
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error('Threshold must be between zero and one.')
    args.output.mkdir(parents=True, exist_ok=False)
    manual = json.loads(args.manual_labels.read_text())
    baseline = json.loads(args.baseline_report.read_text())
    old = {row['id']: row for row in baseline['manual_training_diagnostics']}
    from joint_model import JointDetector
    start = time.perf_counter()
    model = JointDetector(args.checkpoint)
    report = {'interpretation': 'Five training photos; incomplete real labels; no overall precision claim.',
              'checkpoint_sha256': sha256(args.checkpoint),
              'manual_manifest_sha256': sha256(args.manual_labels),
              'baseline_report_sha256': sha256(args.baseline_report),
              'threshold': args.threshold, 'model_load_seconds': time.perf_counter()-start,
              'rows': []}
    for scene in manual['scenes']:
        if sha256(scene['source']) != scene['sha256']:
            raise ValueError('Source image changed.')
        image = read_image(scene['source'])
        for seeds in fixed_trials(len(scene['targets'])):
            examples = [circle(scene['targets'][i]) for i in seeds]
            old_circles, old_cutoff = baseline_predictions(old[scene['id']], seeds, scene)
            before = measure_scene(scene, old_circles, seeds)
            before.update(scene_id=scene['id'], method='actual_v1', threshold=old_cutoff)
            start = time.perf_counter()
            suggestions = model.predict(image, examples, protected=examples, threshold=args.threshold)
            elapsed = time.perf_counter()-start
            after = measure_scene(scene, [row['circle'] for row in suggestions], seeds)
            after.update(scene_id=scene['id'], method='joint', threshold=args.threshold,
                         seconds=elapsed, scores=[float(row['score']) for row in suggestions])
            report['rows'].extend((before, after))
            if seeds == [0, len(scene['targets'])//2]:
                for name, metric in [('actual-v1', before), ('joint', after)]:
                    preview(image, scene, metric, f"{scene['id']} {name}").save(
                        args.output/f"{scene['id']}-{name}.png")
            print(scene['id'], seeds, 'centered', after['centered'], '/', after['remaining'],
                  'found', after['found'], 'extra', after['extras'], 'seconds', round(elapsed, 3), flush=True)
        # This is a fresh output folder; partial results remain inspectable on failure.
        (args.output/'partial-report.json').write_text(json.dumps(report, indent=2)+'\n')
    report['summary'] = {method: {str(n): summarize([r for r in report['rows']
                         if r['method'] == method and len(r['seeds']) == n]) for n in (1, 2)}
                         for method in ('actual_v1', 'joint')}
    report['state_audit'] = state_audit(model, manual['scenes'][1], args.threshold)
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report['summary']), flush=True)


if __name__ == '__main__':
    main()
