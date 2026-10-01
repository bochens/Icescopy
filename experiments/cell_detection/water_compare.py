"""Matched parent/new scoring models for the five user-labeled water images.

Manual-frame recovery is training diagnostics, never held-out real accuracy.
Only the separate procedural calibration split selects the predeclared F2 cutoff.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

from benchmark import example_trials, subset
from detector import Circle, detect, pair_features, patch_descriptors, preprocess_image, propose, read_image, scores
from hybrid_data import sha256
from neural_compare import comparison_banks
from neural_model import FIRST_TRAINABLE_BLOCK, FineTunedEncoder, suffix_embeddings
from neural_train import check_manifest
from water_data import check_manual_manifest
from water_metrics import calibrate_f2, fixed_trials, native_diagnostic
from water_neural_train import verify_parent_prefix


FEATURES = ['gray_correlation', 'edge_correlation', 'mean_profile_difference',
            'max_profile_difference', 'neural_similarity']


def crop_banks(args, parent, updated):
    """Both heads receive identical labeled crops; parent teacher is regenerated.

    The trainer's parent teacher already equals the normalized parent embedding
    on these exact uint8 crops. The new suffix receives the same frozen prefix.
    No validation/calibration crop can enter scoring-model fitting.
    """
    records = json.loads((args.fit_cache/'crop-index.json').read_text())
    source = updated.checkpoint_metadata['source']
    for path, key in [(args.manual_labels, 'manual_manifest_sha256'),
                      (args.synthetic_labels, 'synthetic_manifest_sha256')]:
        if sha256(path) != source[key]:
            raise ValueError('Comparison label manifest differs from training provenance.')
    for name, key in [('prefix.npy', 'prefix_sha256'), ('teacher.npy', 'teacher_sha256')]:
        if sha256(args.fit_cache/name) != source['combined_cache'][key]:
            raise ValueError('Trainer cache changed: '+name)
    if source['parent_encoder_sha256'] != sha256(args.parent_checkpoint):
        raise ValueError('Comparison parent differs from trainer initialization.')
    old = np.load(args.synthetic_cache/'crops.npy', mmap_mode='r')
    manual = np.load(args.fit_cache/'manual-crops'/'crops.npy', mmap_mode='r')
    if len(records) != len(old)+len(manual):
        raise ValueError('Crop records do not match the combined sources.')
    prefix = np.load(args.fit_cache/'prefix.npy', mmap_mode='r')
    teacher = np.load(args.fit_cache/'teacher.npy', mmap_mode='r')
    compatibility = verify_parent_prefix(parent, args.synthetic_cache)
    compatibility['manual_prefix'] = verify_parent_prefix(parent, args.fit_cache/'manual-crops')
    probe_ids = np.linspace(0, len(records)-1, 8).astype(int)
    with parent.torch.inference_mode():
        actual = suffix_embeddings(parent.model.features[FIRST_TRAINABLE_BLOCK:],
                                   parent.torch.from_numpy(np.asarray(prefix[probe_ids]).copy())).numpy()
    difference = float(np.max(np.abs(actual-teacher[probe_ids])))
    if difference > 1e-5 or not np.isfinite(difference):
        raise ValueError('Cached teacher is not the preserved parent embedding.')
    compatibility['parent_teacher_max_abs_difference'] = difference
    (args.output/'head-cache-provenance.json').write_text(json.dumps({
        'compatibility': compatibility, 'fit_crop_indices': [i for i, r in enumerate(records) if r['split'] == 'fit'],
        'input_hashes': {str(p.resolve()): sha256(p) for p in
                         (args.synthetic_cache/'crops.npy', args.fit_cache/'manual-crops'/'crops.npy',
                          args.fit_cache/'crop-index.json', args.fit_cache/'prefix.npy', args.fit_cache/'teacher.npy')}
    })+'\n')
    ids = np.asarray([i for i, r in enumerate(records) if r['split'] == 'fit'], dtype=int)
    shared = {'gray': [], 'edges': [], 'profiles': []}; adapted = []
    suffix = updated.model.features[FIRST_TRAINABLE_BLOCK:]
    started = time.perf_counter()
    with updated.torch.inference_mode():
        for first in range(0, len(ids), 64):
            indices = ids[first:first+64]
            crops = np.stack([old[i] if i < len(old) else manual[i-len(old)] for i in indices])
            for name, values in zip(shared, patch_descriptors(crops.astype(np.float32)/255)):
                shared[name].append(values)
            adapted.append(suffix_embeddings(suffix, updated.torch.from_numpy(np.asarray(prefix[indices]).copy())).numpy())
    shared = {name: np.concatenate(values) for name, values in shared.items()}
    banks = (dict(shared, embedding=np.asarray(teacher[ids]).copy()),
             dict(shared, embedding=np.concatenate(adapted)))
    selected = [dict(records[i], index=j) for j, i in enumerate(ids)]
    print('Head crop banks', len(selected), 'in', round(time.perf_counter()-started, 2), 's', flush=True)
    return selected, banks


def fit_matched_head(records, bank, encoder_sha):
    """Five-feature logistic scorer; equal domains, groups and positive/negative mass.

    Each exemplar comes from a different object than its candidate. Manual
    negatives are explicit annotations; no unmarked proposal is labeled empty.
    Augmented variants are grouped by their one original instrument image.
    """
    domains = {}
    for r in records:
        if r['split'] != 'fit' or r['label'] not in (0, 1):
            raise ValueError('Head fitting accepts labeled fit crops only.')
        if r['domain'] == 'real' and r['label_source'] not in ('user_positive', 'explicit_reviewed_negative'):
            raise ValueError('Manual fitting requires explicit labels.')
        domains.setdefault(r['domain'], {}).setdefault(r['group'], []).append(r)
    if set(domains) != {'real', 'synthetic'}:
        raise ValueError('Both manual and synthetic replay domains are required.')
    rows, labels, masses = [], [], []
    for domain, groups in sorted(domains.items()):
        for group, members in sorted(groups.items()):
            objects = {}
            for r in members:
                if r['label'] == 1:
                    objects.setdefault(r['object_id'], r['index'])
            candidates = [r['index'] for r in members]
            object_ids = list(objects)
            anchor_objects = [object_ids[i] for i in np.unique(np.linspace(0, len(object_ids)-1,
                                                                        min(16, len(object_ids))).astype(int))]
            anchors = [objects[o] for o in anchor_objects]
            pair = pair_features(subset(bank, candidates), subset(bank, anchors))
            group_x, group_y = [], []
            for j, identity in enumerate(anchor_objects):
                keep = np.asarray([r['label'] == 0 or r['object_id'] != identity for r in members])
                group_x.append(pair[keep, j]); group_y.extend(r['label'] for r, k in zip(members, keep) if k)
            x = np.concatenate(group_x); y = np.asarray(group_y, dtype=float)
            if not y.any() or y.all():
                raise ValueError('Every head-fitting group needs both explicit classes.')
            mass = .5/len(groups)
            weights = np.where(y == 1, mass*.5/y.sum(), mass*.5/(1-y).sum())
            rows.append(x); labels.append(y); masses.append(weights)
    x = np.concatenate(rows); y = np.concatenate(labels); weights = np.concatenate(masses)
    mean = np.sum(x*weights[:, None], axis=0)/weights.sum()
    scale = np.maximum(np.sqrt(np.sum((x-mean)**2*weights[:, None], axis=0)/weights.sum()), 1e-6)
    x = (x-mean)/scale
    def objective(w):
        logits = x@w[:-1]+w[-1]
        p = 1/(1+np.exp(-np.clip(logits, -30, 30)))
        error = weights*(p-y)
        return (float(np.sum(weights*(np.logaddexp(0, logits)-y*logits))+.003*np.dot(w[:-1], w[:-1])),
                np.r_[x.T@error+.006*w[:-1], error.sum()])
    with threadpool_limits(limits=4):
        fitted = minimize(objective, np.zeros(6), jac=True, method='L-BFGS-B', options={'maxiter': 150})
    if not fitted.success:
        raise RuntimeError('Matched scoring model did not converge: '+fitted.message)
    return {'mean': mean.tolist(), 'scale': scale.tolist(), 'weights': fitted.x[:-1].tolist(),
            'bias': float(fitted.x[-1]), 'features': FEATURES, 'encoder_sha256': encoder_sha,
            'training_domain': 'manual_water_and_synthetic_replay', 'training_pairs': len(y),
            'positive_pairs': int(y.sum()), 'negative_pairs': int((1-y).sum()),
            'training_groups': {d: sorted(g) for d, g in domains.items()},
            'weighting': '50/50 manual/synthetic; equal instrument/holder groups; balanced positive/negative mass within each group.',
            'regularization': .003, 'anchor_objects_per_group': 16,
            'note': 'Matched five-feature scoring procedure on augmented fit crops only. Scores are not calibrated occupancy probabilities.'}


def prepare_frame(scene, radius, parent, updated, folder):
    if sha256(scene['source']) != scene['sha256']:
        raise ValueError('Input source changed: '+scene['id'])
    start = time.perf_counter(); image = read_image(scene['source'])
    truth = [Circle(float(t['x']), float(t['y']), float(t['radius'])) for t in scene['targets']]
    circles = propose(image, radius)
    banks = comparison_banks(image, circles, parent, updated)
    examples = comparison_banks(image, truth, parent, updated)
    coords = np.asarray([[c.x, c.y, c.radius] for c in circles]).reshape(-1, 3)
    distance = np.linalg.norm(coords[:, None, :2]-np.asarray([[c.x, c.y] for c in truth])[None, :, :], axis=2)
    path = folder/(scene['id']+'-r'+format(radius, '.9g')+'-features.npz')
    np.savez_compressed(path, circles=coords,
                        **{'parent_candidate_'+k: v for k, v in banks[0].items()},
                        **{'parent_example_'+k: v for k, v in examples[0].items()},
                        updated_candidate_embedding=banks[1]['embedding'],
                        updated_example_embedding=examples[1]['embedding'])
    elapsed = time.perf_counter()-start
    print('Frame bank', scene['id'], 'radius', radius, 'in', round(elapsed, 2), 's', flush=True)
    return {'scene': scene, 'truth': truth, 'circles': circles, 'banks': banks, 'examples': examples,
            'distance': distance, 'seconds': elapsed, 'proposal_radius': radius, 'cache_sha256': sha256(path)}


def summarize(entries, complete):
    output = {}
    for method in ('parent', 'updated'):
        output[method] = {}
        for count in (1, 2):
            groups = {}
            for entry in entries:
                rows = [r for r in entry['results'] if r['method'] == method and len(r['seeds']) == count]
                groups[entry['id']] = {key: float(np.mean([r[key] for r in rows]))
                                      for key in ('found', 'remaining', 'missed', 'known_negative_detections',
                                                  'unclassified_additions', 'unmatched_suggestions', 'proposal_ceiling')}
            pooled = {key: sum(g[key] for g in groups.values()) for key in next(iter(groups.values()))}
            pooled['recall'] = pooled['found']/max(1, pooled['remaining'])
            pooled['precision'] = pooled['found']/max(1, pooled['found']+pooled['unmatched_suggestions']) if complete else None
            output[method][str(count)] = {'mean_counts_by_scene': groups, 'pooled_scene_means': pooled,
                                          'equal_scene_recall': float(np.mean([g['found']/max(1, g['remaining']) for g in groups.values()])),
                                          'label_interpretation': 'complete synthetic labels' if complete else 'incomplete training labels; precision unknown'}
    return output


def diagnose(scenes, heads, parent, updated, folder, manual):
    entries = []
    for scene in scenes:
        trials = fixed_trials(len(scene['targets'])) if manual else example_trials(len(scene['targets']))
        radii = sorted({float(np.median([scene['targets'][i]['radius'] for i in ids])) for ids in trials})
        items = {radius: prepare_frame(scene, radius, parent, updated, folder) for radius in radii}
        entry = {k: scene[k] for k in ('id', 'recording', 'width', 'height', 'complete_labels')}
        entry.update(truth=scene['targets'], negatives=scene.get('negatives', []), results=[],
                     interpretation='training diagnostic' if manual else 'previously explored structured synthetic holdout',
                     proposal_banks=[{'radius': r, 'proposals': [asdict(c) for c in item['circles']],
                                      'seconds': item['seconds'], 'cache_sha256': item['cache_sha256']}
                                     for r, item in items.items()])
        for method, index in [('parent', 0), ('updated', 1)]:
            for ids in trials:
                radius = float(np.median([scene['targets'][i]['radius'] for i in ids])); item = items[radius]
                values = scores(item['banks'][index], subset(item['examples'][index], ids), 'learned', heads[method])
                result = native_diagnostic(item, values, ids, heads[method]['threshold'])
                result.update(method=method, proposal_radius=radius, scores=values.tolist())
                entry['results'].append(result)
        entries.append(entry)
        print('Diagnostic finished', scene['id'], flush=True)
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manual-labels', 'synthetic-labels', 'synthetic-cache', 'fit-cache',
                 'parent-checkpoint', 'checkpoint', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--structured-labels', type=Path)
    args = parser.parse_args()
    manual = check_manual_manifest(json.loads(args.manual_labels.read_text()))
    synthetic = check_manifest(json.loads(args.synthetic_labels.read_text()))
    if args.output.exists():
        raise ValueError('Comparison output exists; choose a fresh directory.')
    parent_sha, updated_sha = sha256(args.parent_checkpoint), sha256(args.checkpoint)
    if json.loads(args.manual_labels.read_text())['starting_encoder']['sha256'] != parent_sha:
        raise ValueError('Manifest specifies a different preserved parent.')
    model_start = time.perf_counter()
    parent = FineTunedEncoder(args.parent_checkpoint); updated = FineTunedEncoder(args.checkpoint)
    model_seconds = time.perf_counter()-model_start
    args.output.mkdir(parents=True, exist_ok=False); cv2.setNumThreads(4)
    for name in ('calibration-banks', 'diagnostic-banks', 'structured-banks'):
        (args.output/name).mkdir()
    records, banks = crop_banks(args, parent, updated)
    heads = {'parent': fit_matched_head(records, banks[0], parent_sha),
             'updated': fit_matched_head(records, banks[1], updated_sha)}
    (args.output/'head-fit.json').write_text(json.dumps(heads, indent=2)+'\n')
    calibration = [prepare_frame(s, float(s['targets'][0]['radius']), parent, updated,
                                 args.output/'calibration-banks') for s in synthetic if s['split'] == 'calibration']
    with threadpool_limits(limits=4):
        thresholds = {method: calibrate_f2(calibration, i, heads[method])
                      for i, method in enumerate(('parent', 'updated'))}
    for method, head in heads.items():
        (args.output/(method+'-head.json')).write_text(json.dumps(head, indent=2)+'\n')
    (args.output/'calibration.json').write_text(json.dumps(thresholds, indent=2)+'\n')
    print('Both synthetic F2 cutoffs frozen', {k: v['threshold'] for k, v in thresholds.items()}, flush=True)
    # All weight/head/checkpoint/threshold choices are complete before diagnostics.
    diagnostics = diagnose(manual, heads, parent, updated, args.output/'diagnostic-banks', manual=True)
    structured = []
    if args.structured_labels:
        test = json.loads(args.structured_labels.read_text())['scenes']
        if ({s.get('group', s['recording']) for s in test} & {s['group'] for s in synthetic}
                or {s['sha256'] for s in test} & {s['sha256'] for s in synthetic+manual}):
            raise ValueError('Structured holdout overlaps fitting or reserved synthetic corpus.')
        structured = diagnose(test, heads, parent, updated, args.output/'structured-banks', manual=False)
    # Measure one full current-frame call per encoder with two examples on a
    # predeclared central instrument scene. Root separately checks video/state.
    timed = manual[len(manual)//2]; ids = fixed_trials(len(timed['targets']))[3]
    raw = cv2.imread(timed['source'], cv2.IMREAD_UNCHANGED)
    selected = [Circle(float(timed['targets'][i]['x']), float(timed['targets'][i]['y']),
                       float(timed['targets'][i]['radius'])) for i in ids]
    timings = []
    for method, encoder in [('parent', parent), ('updated', updated)]:
        start = time.perf_counter(); image = preprocess_image(raw, 'BGR')
        additions = detect(image, selected, method='learned', threshold=heads[method]['threshold'], encoder=encoder, head=heads[method])
        elapsed = time.perf_counter()-start
        entry = next(e for e in diagnostics if e['id'] == timed['id'])
        cached = next(r for r in entry['results'] if r['method'] == method and r['seeds'] == ids)
        geometry = next(b['proposals'] for b in entry['proposal_banks'] if b['radius'] == cached['proposal_radius'])
        expected = {tuple(geometry[i][k] for k in ('x', 'y', 'radius')): cached['scores'][i]
                    for i in cached['accepted']}
        actual = {tuple(a['circle'][k] for k in ('x', 'y', 'radius')): a['score'] for a in additions}
        if set(actual) != set(expected):
            raise AssertionError('Actual current-frame detector selections differ from the cached diagnostic trial.')
        maximum_difference = max((abs(actual[c]-expected[c]) for c in actual), default=0.)
        if maximum_difference > 1e-5:
            raise AssertionError('Actual current-frame detector scores differ from the cached diagnostic trial.')
        timings.append({'method': method, 'scene': timed['id'], 'seeds': ids,
                        'seconds': elapsed, 'additions': len(additions),
                        'cached_trial_same_selections': True, 'max_abs_score_difference': maximum_difference,
                        'includes': 'Normalization, proposals, known-cell exclusion, all crops, full CPU encoder, scoring and duplicate removal; file/model loading excluded.'})
    report = {'heads': heads, 'thresholds': thresholds, 'manual_training_diagnostics': diagnostics,
              'manual_summary': summarize(diagnostics, complete=False),
              'structured_holdout': structured, 'structured_summary': summarize(structured, complete=True) if structured else None,
              'current_frame_timings': timings, 'model_load_seconds': model_seconds,
              'input_hashes': {name: {'path': str(getattr(args, name).resolve()), 'sha256': sha256(getattr(args, name))}
                               for name in ('manual_labels', 'synthetic_labels', 'parent_checkpoint', 'checkpoint')},
              'source_checkpoint': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'limitations': ['All five real photos are training data with incomplete annotations; no real held-out accuracy or precision is claimed.',
                              'Parent and updated models use the same newly fitted scorer and synthetic F2 calibration; this isolates neural updates under that procedure, not changes versus the parent historical scorer.',
                              'Manual negatives are explicit; other unmatched additions remain unclassified and all selections are retained.',
                              'Separate synthetic validation chooses the checkpoint; calibration is not an independent test.',
                              'Structured holdout is excluded from this adaptation but has been explored in earlier experiments.',
                              'Each trial uses only its current frame and selected-example median proposal radius; every example and reference retains its native radius.']}
    if args.structured_labels:
        report['input_hashes']['structured_labels'] = {'path': str(args.structured_labels.resolve()), 'sha256': sha256(args.structured_labels)}
    (args.output/'report.json').write_text(json.dumps(report)+'\n')
    print('Comparison saved', args.output/'report.json', flush=True)


if __name__ == '__main__':
    main()
