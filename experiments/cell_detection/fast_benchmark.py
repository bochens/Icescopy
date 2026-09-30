"""One fixed tree experiment with grouped training and separate calibration.

Real recording A and independent rendered groups fit the classifier. Separate
rendered groups choose the threshold. Evaluation labels never fit either.
All inspected real recordings remain exploratory, not blind confirmation tests.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
from threadpoolctl import threadpool_limits

from benchmark import evaluate, example_trials, subset
from detector import Circle, preprocess_image, propose, read_image
from fast_model import DESCRIPTOR_VERSION, FEATURE_NAMES, MODEL_VERSION, THREADS, detect, feature_bank, pair_features, scores
from structured_scenes import render


# Each family/seed is one indivisible group, across clear, glare and blur views.
TRAIN_SEEDS = {'pcr': [71011, 81013], 'grid': [72017, 82021],
               'disc': [73019, 83023], 'pocket': [74023, 84029]}
CALIBRATION_SEEDS = {'pcr': 91009, 'grid': 92033, 'disc': 93047, 'pocket': 94049}
FORBIDDEN_SEEDS = {1103, 2207, 3301, 4409, 1204, 2308, 3402, 4510}
PARAMETERS = {'max_iter': 100, 'max_leaf_nodes': 15, 'min_samples_leaf': 40,
              'l2_regularization': 1., 'learning_rate': .1,
              'early_stopping': False, 'random_state': 60930}


def generated_training(folder):
    scenes = []
    for split, seeds in [('fit', TRAIN_SEEDS), ('calibration', CALIBRATION_SEEDS)]:
        for family, values in seeds.items():
            for seed in values if isinstance(values, list) else [values]:
                if seed in FORBIDDEN_SEEDS:
                    raise ValueError('A structured diagnostic seed entered training/calibration.')
                for condition in ('clear', 'glare', 'gray_blur'):
                    raw, targets, negatives, metadata = render(family, seed, condition=condition)
                    scene_id = f'{split}-{family}-{seed}-{condition}'
                    source = folder/(scene_id+'.png')
                    if not cv2.imwrite(str(source), raw):
                        raise IOError('Generated image write failed.')
                    scenes.append({'id': scene_id, 'recording': f'simulated-{family}-{seed}',
                                   'group': f'simulated-{family}-{seed}', 'source': str(source.resolve()),
                                   'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                                   'width': raw.shape[1], 'height': raw.shape[0], 'split': split,
                                   'targets': targets, 'negatives': negatives, 'complete_labels': True,
                                   'rendering': metadata, 'label_status': 'Procedural training or calibration group; approximate optics.'})
    (folder/'labels.json').write_text(json.dumps({'scenes': scenes}, indent=2)+'\n')
    return scenes


def prepare(scene, folder):
    source = Path(scene['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != scene['sha256']:
        raise ValueError('Input changed since labels were recorded: '+scene['id'])
    start = time.perf_counter()
    image = read_image(source)
    radius = float(scene['targets'][0]['radius'])
    truth = [Circle(float(t['x']), float(t['y']), radius) for t in scene['targets']]
    circles = propose(image, radius)
    bank, examples = feature_bank(image, circles), feature_bank(image, truth)
    distance = np.linalg.norm(np.array([[c.x, c.y] for c in circles])[:, None, :]-
                              np.array([[c.x, c.y] for c in truth])[None, :, :], axis=2)
    elapsed = time.perf_counter()-start
    preview = cv2.cvtColor(np.uint8(image*255), cv2.COLOR_RGB2BGR)
    scale = min(1., 1400/image.shape[1])
    preview = cv2.resize(preview, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(folder/(scene['id']+'.jpg')), preview, [cv2.IMWRITE_JPEG_QUALITY, 92])
    np.savez_compressed(folder/(scene['id']+'-features.npz'),
                        **{'candidate_'+k: v for k, v in bank.items()},
                        **{'example_'+k: v for k, v in examples.items()},
                        circles=np.array([[c.x, c.y, c.radius] for c in circles]))
    print(scene['id'], len(circles), 'proposals;', round(elapsed, 3), 's', flush=True)
    return {'scene': scene, 'truth': truth, 'circles': circles, 'bank': bank, 'examples': examples,
            'distance': distance, 'seconds': elapsed, 'preview_scale': scale}


def fit(prepared):
    import sklearn
    from sklearn.ensemble import HistGradientBoostingClassifier
    rows, labels, groups = [], [], []
    rng = np.random.default_rng(60930)
    for item in prepared:
        scene = item['scene']
        if scene['split'] != 'fit':
            continue
        if not scene['complete_labels']:
            raise ValueError('Training requires complete labels.')
        radius = item['truth'][0].radius
        nearest = item['distance'].min(axis=1)
        positive = np.flatnonzero(nearest < .8*radius)
        negative = np.flatnonzero(nearest > 1.8*radius)
        # Keep all reached targets and a fixed random background sample. This
        # bounds training cost; classification still sees every proposal at run time.
        if len(negative) > 512:
            negative = np.sort(rng.choice(negative, 512, replace=False))
        ids = np.unique(np.linspace(0, len(item['truth'])-1, min(8, len(item['truth']))).astype(int))
        indices = np.r_[positive, negative]
        pair = pair_features(subset(item['bank'], indices), subset(item['examples'], ids))
        for j, seed in enumerate(ids):
            keep = item['distance'][indices, seed] >= 1.8*radius
            rows.append(pair[keep, j])
            labels.append((nearest[indices[keep]] < .8*radius).astype(np.uint8))
            groups.extend([scene['group']]*int(keep.sum()))
    if not rows:
        raise ValueError('No fit groups supplied.')
    x, y = np.concatenate(rows), np.concatenate(labels)
    groups = np.asarray(groups)
    weights = np.zeros(len(y), np.float64)
    unique_groups = np.unique(groups)
    for group in unique_groups:
        for label in (0, 1):
            keep = (groups == group) & (y == label)
            weights[keep] = .5/max(1, int(keep.sum()))
    weights *= len(y)/len(unique_groups)
    classifier = HistGradientBoostingClassifier(**PARAMETERS)
    start = time.perf_counter()
    with threadpool_limits(limits=THREADS):
        classifier.fit(x, y, sample_weight=weights)
    metadata = {'parameters': PARAMETERS, 'threads': THREADS, 'fit_seconds': time.perf_counter()-start,
                'training_pairs': len(y), 'positive_pairs': int(y.sum()), 'negative_pairs': int((1-y).sum()),
                'training_groups': unique_groups.tolist(),
                'training_scene_ids': [p['scene']['id'] for p in prepared if p['scene']['split'] == 'fit'],
                'sampling': 'Up to eight reference examples, all positive proposals, and at most 512 negative proposals per training scene; groups and classes receive equal total weight.'}
    print('Fit', len(y), 'pairs;', round(metadata['fit_seconds'], 2), 's', flush=True)
    return {'model_version': MODEL_VERSION, 'descriptor_version': DESCRIPTOR_VERSION,
            'feature_names': FEATURE_NAMES, 'sklearn_version': sklearn.__version__,
            'classifier': classifier, 'threshold': .5, 'metadata': metadata}


def calibrate(prepared, bundle):
    cached = []
    for item in prepared:
        if item['scene']['split'] == 'calibration':
            for ids in example_trials(len(item['truth'])):
                cached.append((item, ids, scores(item['bank'], subset(item['examples'], ids), bundle)))
    if not cached:
        raise ValueError('No separate calibration groups supplied.')
    choices = []
    for threshold in np.linspace(.05, .999, 96):
        tp = fp = remaining = 0
        for item, ids, values in cached:
            result = evaluate(item, values, ids, threshold)
            tp += result['found']; fp += result['false_detections']; remaining += result['remaining']
        precision, recall = tp/max(1, tp+fp), tp/max(1, remaining)
        choices.append((precision >= .99, recall if precision >= .99 else precision,
                        recall, float(threshold), precision, tp, fp, remaining))
    best = max(choices)
    bundle['threshold'] = best[3]
    bundle['metadata']['calibration'] = {'threshold': best[3], 'precision': best[4], 'recall': best[2],
                                        'found': best[5], 'false_detections': best[6], 'remaining': best[7],
                                        'groups': sorted({p['scene']['group'] for p in prepared if p['scene']['split'] == 'calibration'}),
                                        'target_precision': .99,
                                        'selection': 'Highest recall with aggregate precision >=99%; otherwise highest precision. Separate rendered groups only; evaluation labels are not used.'}
    by_family = {}
    for item, ids, values in cached:
        family = item['scene']['rendering']['family']
        totals = by_family.setdefault(family, {'found': 0, 'false_detections': 0, 'remaining': 0})
        result = evaluate(item, values, ids, best[3])
        for key in totals:
            totals[key] += result[key]
    for totals in by_family.values():
        totals['precision'] = totals['found']/max(1, totals['found']+totals['false_detections'])
        totals['recall'] = totals['found']/max(1, totals['remaining'])
    bundle['metadata']['calibration']['by_family'] = by_family
    print('Frozen calibration threshold', round(best[3], 4), 'precision', round(best[4], 4),
          'recall', round(best[2], 4), flush=True)


def report_scenes(prepared, bundle, actual_timing=True):
    entries = []
    for item in prepared:
        scene = item['scene']
        entry = {k: scene[k] for k in ['id', 'recording', 'split', 'width', 'height', 'label_status', 'complete_labels']}
        entry.update(seconds=item['seconds'], radius=item['truth'][0].radius,
                     negatives=scene.get('negatives', []),
                     proposal_reference_coverage=int((item['distance'].min(axis=0) < item['truth'][0].radius).sum()),
                     preview_scale=item['preview_scale'], truth=[asdict(c) for c in item['truth']],
                     proposals=[asdict(c) for c in item['circles']], results=[])
        trials = example_trials(len(item['truth']))
        if scene['id'] == 'TAMU-A-0' and [0, 8] not in trials:
            trials.append([0, 8])
        for ids in trials:
            value = scores(item['bank'], subset(item['examples'], ids), bundle)
            result = evaluate(item, value, ids, bundle['threshold'])
            result.update(method='fast', scores=np.round(value, 5).tolist())
            entry['results'].append(result)
        if actual_timing:
            raw = cv2.imread(str(scene['source']), cv2.IMREAD_UNCHANGED)
            timings = []
            for ids in ([0], [0, len(item['truth'])//2]):
                selected = [item['truth'][i] for i in ids]
                start = time.perf_counter()
                image = preprocess_image(raw, color_order='BGR')
                additions = detect(image, selected, method='fast', threshold=bundle['threshold'], head=bundle)
                timings.append({'seeds': ids, 'seconds': time.perf_counter()-start, 'suggestions': len(additions),
                                'includes': 'Current-frame preprocessing, proposal generation, protected-candidate exclusion, direct patches for remaining candidates and supplied examples, feature comparison, tree prediction, duplicate exclusion; excludes file/model loading.'})
            entry['single_frame_timings'] = timings
        entries.append(entry)
        for count in (1, 2):
            rows = [r for r in entry['results'] if len(r['seeds']) == count]
            print(scene['id'], count, 'examples: found', round(float(np.mean([r['found'] for r in rows])), 2),
                  'missed', round(float(np.mean([r['missed'] for r in rows])), 2),
                  'unmatched', round(float(np.mean([r['unmatched_suggestions'] for r in rows])), 2), flush=True)
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real-labels', type=Path, required=True)
    parser.add_argument('--structured-labels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output folder already exists; choose a new name.')
    real = json.loads(args.real_labels.read_text())['scenes']
    structured = json.loads(args.structured_labels.read_text())['scenes']
    # The supplied manifest is the boundary: every original is read only.
    real_fit, real_eval = [], []
    for scene in real:
        if scene['split'] == 'development':
            if scene['recording'] != 'A':
                parser.error('Only recording A is authorized for real training.')
            real_fit.append(dict(scene, split='fit', group='real-A'))
        else:
            real_eval.append(scene)
    if len({s['id'] for s in real+structured}) != len(real+structured):
        parser.error('Scene IDs must be unique.')
    args.output.mkdir(parents=True, exist_ok=False)
    training = args.output/'training'; training.mkdir()
    evaluation = args.output/'evaluation'; evaluation.mkdir()
    cv2.setNumThreads(THREADS)
    generated = generated_training(training)
    prepared = [prepare(s, training) for s in real_fit+generated]
    bundle = fit(prepared)
    calibrate(prepared, bundle)
    bundle['metadata']['training_scene_hashes'] = {p['scene']['id']: p['scene']['sha256'] for p in prepared}
    import joblib
    joblib.dump(bundle, args.output/'fast-model.joblib', compress=3)
    metadata = {k: v for k, v in bundle.items() if k != 'classifier'}
    (args.output/'model-metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    # Do not prepare evaluation scenes until classifier and threshold are fixed.
    held_out = [prepare(s, evaluation) for s in real_eval+structured]
    development = [dict(p, scene=dict(p['scene'], split='development')) for p in prepared if p['scene']['group'] == 'real-A']
    for p in development:
        source = training/(p['scene']['id']+'.jpg')
        (evaluation/source.name).write_bytes(source.read_bytes())
    report = {'thresholds': {'fast': bundle['metadata']['calibration']}, 'model': metadata,
              'input_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [args.real_labels, args.structured_labels]},
              'scenes': report_scenes(development+held_out, bundle),
              'limitations': ['All real recordings were inspected during experiment development; results are exploratory.',
                              'Rendered optics are approximations; synthetic success does not establish real occupancy accuracy.',
                              'Missing positive annotations do not mean empty; incomplete-label precision is not reported.',
                              'Only recording A and independent rendered groups fit the tree. Separate rendered groups calibrate the threshold.',
                              'Preparation timing caches features for every reference circle. single_frame_timings measure actual one/two-example calls.',
                              'Scores are experimental rankings, not calibrated real occupancy probabilities.',
                              'No motion estimation, other-image scanning, application integration, or changes to freezing detection.']}
    (evaluation/'report.json').write_text(json.dumps(report)+'\n')
    print('Report', evaluation/'report.json', flush=True)


if __name__ == '__main__':
    main()
