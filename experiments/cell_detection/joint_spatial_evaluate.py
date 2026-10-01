"""Evaluate fixed weights and cutoff on reserved regions after model selection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from detector import read_image
from hybrid_data import sha256
from joint_evaluate import preview, state_audit
from joint_metrics import circle, measure_scene, summarize
from joint_model import JointDetector
from joint_spatial import check_spatial_manifest
from water_metrics import fixed_trials


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ('checkpoint', 'real-labels', 'calibration', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    calibration = json.loads(args.calibration.read_text())
    if sha256(args.checkpoint) != calibration['checkpoint_sha256']:
        raise ValueError('Cutoff was selected for different weights.')
    manifest = json.loads(args.real_labels.read_text())
    scenes = [s for s in check_spatial_manifest(manifest) if s['split'] == 'test']
    model = JointDetector(args.checkpoint)
    source = model.metadata['source']
    if (not source['spatial_split'] or source['real_manifest_sha256'] != sha256(args.real_labels)
            or any(s['id'] in source['scene_hashes'] for s in scenes)):
        raise ValueError('Model fitting provenance does not exclude these test regions.')
    threshold = calibration['selected']['threshold']
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'checkpoint_sha256': sha256(args.checkpoint), 'real_manifest_sha256': sha256(args.real_labels),
              'calibration_sha256': sha256(args.calibration), 'threshold': threshold,
              'interpretation': 'Reserved regions of previously inspected images, not new recordings. Incomplete labels; no overall precision claim.',
              'rows': []}
    for scene in scenes:
        image = read_image(scene['source'])
        for seeds in fixed_trials(len(scene['targets'])):
            examples = [circle(scene['targets'][i]) for i in seeds]
            start = time.perf_counter()
            suggestions = model.predict(image, examples, protected=examples, threshold=threshold)
            elapsed = time.perf_counter()-start
            metric = measure_scene(scene, [row['circle'] for row in suggestions], seeds)
            metric.update(scene_id=scene['id'], seconds=elapsed,
                          scores=[row['score'] for row in suggestions])
            report['rows'].append(metric)
            if seeds == [0, len(scene['targets'])//2]:
                preview(image, scene, metric, scene['id'],
                        note='Reserved region: weights and cutoff fixed beforehand; same recording as training regions.').save(
                            args.output/(scene['id']+'.png'))
            print(scene['id'], seeds, 'centered', metric['centered'], '/', metric['remaining'],
                  'found', metric['found'], 'extra', metric['extras'],
                  'known negative hits', len(metric['known_negative_indices']), 'seconds', round(elapsed, 3), flush=True)
        (args.output/'partial-report.json').write_text(json.dumps(report, indent=2)+'\n')
    report['summary'] = {str(n): summarize([r for r in report['rows'] if len(r['seeds']) == n]) for n in (1, 2)}
    report['state_audit'] = state_audit(model, next(s for s in scenes if 'PCR' in s['id']), threshold)
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report['summary']), flush=True)


if __name__ == '__main__': main()
