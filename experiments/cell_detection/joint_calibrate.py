"""Choose a joint detector cutoff on reserved, completely labeled synthetic images."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np

from detector import read_image
from hybrid_data import sha256
from joint_metrics import circle, match_centers
from water_metrics import fixed_trials


def choose_threshold(trials, thresholds):
    """Balance accurately centered detections and extras; do not use real photos."""
    curve = []
    for threshold in thresholds:
        found = total = remaining = 0
        for trial in trials:
            references = [circle(row) for row in trial['references']]
            predictions = [circle(row['circle']) for row in trial['suggestions']
                           if row['score'] >= threshold]
            found += len(match_centers(predictions, references, .35))
            total += len(predictions)
            remaining += len(references)
        row = {'threshold': float(threshold), 'centered': found,
               'remaining': remaining, 'suggestions': total,
               'not_centered': total-found, 'missed_or_offset': remaining-found,
               'centered_precision': found/total if total else 0.,
               'centered_recall': found/remaining if remaining else 0.,
               'centered_f1': 2*found/max(1, total+remaining)}
        curve.append(row)
    selected = max(curve, key=lambda row: (row['centered_f1'], row['centered_precision'],
                                         row['centered_recall'], row['threshold']))
    return selected, curve


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ('checkpoint', 'synthetic-labels', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.synthetic_labels.read_text())
    scenes = [s for s in manifest['scenes'] if s['split'] == 'calibration']
    other_groups = {s['group'] for s in manifest['scenes'] if s['split'] != 'calibration'}
    if not scenes or any(not s.get('complete_labels') or s['group'] in other_groups for s in scenes):
        raise ValueError('Calibration requires complete synthetic labels and separate groups.')
    from joint_model import JointDetector
    model = JointDetector(args.checkpoint)
    trials = []
    start = time.perf_counter()
    # Fixed before inference: include a permissive floor and a regular cutoff grid.
    thresholds = np.unique(np.r_[.01, np.arange(.05, .951, .025), .975])
    for scene in scenes:
        if sha256(scene['source']) != scene['sha256']:
            raise ValueError('Synthetic source changed.')
        image = read_image(scene['source'])
        prepared = {}
        for seeds in fixed_trials(len(scene['targets'])):
            examples = [circle(scene['targets'][i]) for i in seeds]
            radius = float(np.median([c.radius for c in examples]))
            if radius not in prepared:
                prepared[radius] = model.prepare_frame(image, radius)
            predictions = model.predict_prepared(prepared[radius], examples,
                                                  protected=examples, threshold=.01)
            trials.append({'scene_id': scene['id'], 'seeds': seeds,
                           'references': [row for i, row in enumerate(scene['targets']) if i not in seeds],
                           'suggestions': predictions})
        print('Calibration predictions', scene['id'], flush=True)
    selected, curve = choose_threshold(trials, thresholds)
    report = {'checkpoint_sha256': sha256(args.checkpoint),
              'synthetic_manifest_sha256': sha256(args.synthetic_labels),
              'rule': 'Centered F1 on reserved synthetic calibration images; 0.35 reference-radius tolerance.',
              'interpretation': 'Cutoff selection data, not an independent test result.',
              'selected': selected, 'curve': curve, 'trials': trials,
              'seconds': time.perf_counter()-start}
    (args.output/'calibration.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(selected), flush=True)


if __name__ == '__main__':
    main()
