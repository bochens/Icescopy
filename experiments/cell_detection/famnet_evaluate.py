"""Evaluate fixed pretrained FamNet density/heuristic circles; no fitting."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np

from detector import preprocess_image
from hybrid_data import sha256
from joint_evaluate import preview
from joint_metrics import circle, measure_scene, summarize
from pretrained_famnet import FamNetDetector, PEAK_RULE


def comparison(row):
    return {key: row.get(key) for key in ('found', 'centered', 'remaining', 'extras', 'seconds')} | {
        'known_empty_hits': len(row['known_negative_indices'])}


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ('official-root', 'backbone-weights', 'manual-labels', 'spatial-labels', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('reuse-pcr', 'historical-joint-report', 'whole-joint-report', 'spatial-joint-report'):
        parser.add_argument('--'+name, type=Path)
    args = parser.parse_args()
    manual = json.loads(args.manual_labels.read_text()); spatial = json.loads(args.spatial_labels.read_text())
    whole = sorted(manual['scenes'], key=lambda s: ('PCR' not in s['id'], s['id']))
    heldout = [s for s in spatial['scenes'] if s['split'] == 'test']
    if len(whole) != 5 or len(heldout) != 5:
        raise ValueError('Expected five original diagnostic images and five reserved test crops.')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'peak-rule.json').write_text(json.dumps(PEAK_RULE, indent=2)+'\n')
    start = time.perf_counter(); model = FamNetDetector(args.official_root, args.backbone_weights)
    load_seconds = time.perf_counter()-start
    git_commit = subprocess.check_output(['git', '-C', str(args.official_root), 'rev-parse', 'HEAD'], text=True).strip()
    historical = json.loads(args.historical_joint_report.read_text())['rows'] if args.historical_joint_report else []
    joint_whole = json.loads(args.whole_joint_report.read_text())['rows'] if args.whole_joint_report else []
    joint_test = json.loads(args.spatial_joint_report.read_text())['rows'] if args.spatial_joint_report else []
    reused = json.loads(args.reuse_pcr.read_text()) if args.reuse_pcr else None
    if reused:
        if (reused['manual_manifest_sha256'] != sha256(args.manual_labels) or
                reused['provenance']['peak_rule'] != PEAK_RULE or
                reused['provenance']['backbone_weights']['sha256'] != model.provenance['backbone_weights']['sha256'] or
                reused['provenance']['regressor_weights']['sha256'] != model.provenance['regressor_weights']['sha256']):
            raise ValueError('Cached PCR predictions differ from the fixed inputs/model/peak rule.')
    rows = []
    report = {'interpretation': 'Pretrained counting model, no training/adaptation. Density counts and heuristic circle localization are distinct outputs. Whole photos are diagnostics; reserved crops share the same recordings.',
              'provenance': model.provenance, 'official_git_commit': git_commit,
              'official_url': 'https://github.com/cvlab-stonybrook/LearningToCountEverything',
              'license': 'MIT', 'model_load_seconds': load_seconds,
              'manifest_hashes': {'manual': sha256(args.manual_labels), 'spatial': sha256(args.spatial_labels)},
              'source_code_hashes': {name: sha256(Path(__file__).parent/name) for name in ('pretrained_famnet.py', 'famnet_evaluate.py')},
              'package_versions': {name: importlib.metadata.version(name) for name in ('torch', 'torchvision', 'numpy', 'scipy', 'Pillow')},
              'opencv_version': cv2.__version__, 'rows': rows,
              'timing_includes': 'Current-frame percentile normalization, authors resize/normalization, shared ResNet features, exemplar correlation, density regressor, peak extraction and protection. Excludes file decode, weights download/loading and output writing.'}
    for category, scenes in (('whole_image_diagnostic', whole), ('reserved_test_region', heldout)):
        for scene in scenes:
            if sha256(scene['source']) != scene['sha256']: raise ValueError('Input image pixels changed.')
            raw = cv2.imread(scene['source'], cv2.IMREAD_UNCHANGED)
            if raw is None: raise ValueError('Cannot decode input image.')
            trials = [[0], [0, len(scene['targets'])//2]] if category == 'whole_image_diagnostic' else [[0, len(scene['targets'])//2]]
            for seeds in trials:
                examples = [circle(scene['targets'][i]) for i in seeds]
                cached = next((r for r in reused['rows'] if r['scene_id'] == scene['id'] and r['seeds'] == seeds), None) if reused else None
                stem = scene['id']+'-'+str(len(seeds))
                if cached:
                    density = np.load(args.reuse_pcr.parent/('density-'+str(len(seeds))+'.npy'))
                    metric = measure_scene(scene, cached['circles'], seeds)
                    extra = {k: cached[k] for k in ('seconds', 'density_count_including_examples', 'density_shape', 'geometry', 'localization')}
                    image = preprocess_image(raw, 'BGR')
                    extra['reused_prediction_report_sha256'] = sha256(args.reuse_pcr)
                else:
                    start = time.perf_counter(); image = preprocess_image(raw, 'BGR')
                    result = model.predict(image, examples, protected=examples)
                    seconds = time.perf_counter()-start
                    density = result['density']; metric = measure_scene(scene, [p['circle'] for p in result['predictions']], seeds)
                    extra = {'seconds': seconds, 'density_count_including_examples': result['density_count_including_examples'],
                             'density_shape': list(density.shape), 'geometry': result['geometry'], 'localization': result['localization']}
                row = dict(metric, **extra, scene_id=scene['id'], category=category, source_sha256=scene['sha256'],
                           known_annotated_targets=len(scene['targets']), complete_count_reference=False,
                           comparisons={})
                for name, saved in ([('actual_manual_v1', historical), ('clean_spatial_joint_whole_diagnostic', joint_whole)]
                                    if category == 'whole_image_diagnostic' else [('clean_spatial_joint_test', joint_test)]):
                    found = [r for r in saved if r['scene_id'] == scene['id'] and r['seeds'] == seeds and
                             (name != 'actual_manual_v1' or r.get('method') == 'actual_v1')]
                    if found: row['comparisons'][name] = comparison(found[0])
                rows.append(row)
                np.save(args.output/(stem+'-density.npy'), density)
                note = ('Pretrained/no adaptation; whole-image diagnostic, not an independent new recording.' if category == 'whole_image_diagnostic' else
                        'Pretrained/no adaptation; reserved region of an existing recording. Peak circles are heuristic.')
                preview(image, scene, metric, 'FamNet density-peak circles', note=note).save(args.output/(stem+'-predictions.png'))
                high = float(np.quantile(density, .995))
                heat = cv2.applyColorMap(np.uint8(np.clip(density/max(high, 1e-12), 0, 1)*255), cv2.COLORMAP_VIRIDIS)
                cv2.imwrite(str(args.output/(stem+'-density.png')), heat)
                report['summary'] = {name: summarize([r for r in rows if r['category'] == name and len(r['seeds']) == 2])
                                     for name in ('whole_image_diagnostic', 'reserved_test_region')}
                (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
                print(json.dumps({'category': category, 'scene_id': scene['id'], 'seeds': seeds,
                                  'density_count': row['density_count_including_examples'], 'centered': row['centered'],
                                  'found': row['found'], 'remaining': row['remaining'], 'extras': row['extras'],
                                  'known_empty_hits': len(row['known_negative_indices']), 'seconds': row['seconds']}), flush=True)
    report['weights_unchanged_after_inference'] = all(sha256(entry['path']) == entry['sha256'] for entry in
                                                   (model.provenance['backbone_weights'], model.provenance['regressor_weights']))
    report['status'] = 'complete'
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__': main()
