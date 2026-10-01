"""V2 center-negative adaptation, reusing v1 pixels and starting from v1 weights."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from hybrid_data import load_synthetic_records, sha256
from neural_model import FineTunedEncoder
from neural_train import cache_prefix
from water_center_data import CenterTriplets, append_manual_cache, build_center_crops, check_center_manifest
from water_neural_train import CONFIG as WATER_CONFIG, combine_parent_cache, train_water, verify_parent_prefix


CONFIG = dict(WATER_CONFIG, seed=61004, center_variants=4, maximum_crops=30000,
              initialization='preserved_first_manual_water_adaptation',
              sampling='Half manual/half synthetic replay; equal instruments; half old/half invalid-center manual negatives; cycle all object IDs.',
              selection='Fixed final pass after all421 positives and all669 invalid centers receive updates; separate synthetic validation reported, not a checkpoint search.',
              center_augmentation='Exact crop centers/radii; no translation or crop jitter; centered rotation/flip/isotropic scaling and photometric transforms.',
              centering_diagnostic_tolerance=.35)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manual-labels', 'synthetic-labels', 'synthetic-cache', 'parent-checkpoint', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(); manifest = json.loads(args.manual_labels.read_text())
    original_path = Path(manifest['previous_manual_manifest']['path'])
    if sha256(original_path) != manifest['previous_manual_manifest']['sha256']:
        raise ValueError('Original user-label manifest changed.')
    scenes = check_center_manifest(manifest, json.loads(original_path.read_text()))
    parent_sha = sha256(args.parent_checkpoint)
    previous = Path(manifest['previous_fit_cache'])
    if (manifest['starting_encoder']['sha256'] != parent_sha or
            sha256(previous/'encoder.pt') != parent_sha):
        raise ValueError('V2 must initialize from the unchanged v1 manual-trained encoder.')
    prior = json.loads((previous/'training-report.json').read_text())
    if prior['source']['manual_manifest_sha256'] != sha256(original_path):
        raise ValueError('Previous crop cache belongs to different user labels.')
    original_manual = previous/'manual-crops'
    for name, key in [('prefix.npy', 'prefix_sha256'), ('teacher.npy', 'teacher_sha256')]:
        if sha256(original_manual/name) != prior['source']['manual_cache'][key]:
            raise ValueError('Original manual cache changed: '+name)
    old, old_source = load_synthetic_records(args.synthetic_labels, args.synthetic_cache)
    count = len(old)+sum(len(s['targets'])+len(s['negatives']) for s in scenes)*CONFIG['manual_variants']
    center_count = sum(len(s.get('center_negatives', [])) for s in scenes)
    count += center_count*CONFIG['center_variants']
    if count > CONFIG['maximum_crops']:
        raise ValueError('Center-negative crop bank exceeds the declared 30k cap.')
    parent = FineTunedEncoder(args.parent_checkpoint, CONFIG['threads'])
    compatibility = {'synthetic': verify_parent_prefix(parent, args.synthetic_cache),
                     'original_manual': verify_parent_prefix(parent, original_manual)}
    args.output.mkdir(parents=True, exist_ok=False); cv2.setNumThreads(CONFIG['threads'])
    (args.output/'config.json').write_text(json.dumps(CONFIG, indent=2)+'\n')
    centers = args.output/'center-crops'; centers.mkdir()
    center_rows = build_center_crops(scenes, centers, CONFIG['center_variants'], CONFIG['seed'])
    cache_prefix(parent, centers, center_rows)
    manual = args.output/'manual-crops'; manual.mkdir()
    real = append_manual_cache(parent, original_manual, centers, manual)
    old, combined = combine_parent_cache(parent, args.output, args.synthetic_cache, old, manual, real)
    source = {'manual_manifest_sha256': sha256(args.manual_labels),
              'original_manual_manifest_sha256': sha256(original_path),
              'synthetic_manifest_sha256': sha256(args.synthetic_labels),
              'parent_encoder_sha256': parent_sha, 'parent_encoder_path': str(args.parent_checkpoint.resolve()),
              'manual_scene_hashes': {s['id']: s['sha256'] for s in scenes},
              'synthetic_cache_source': old_source, 'prefix_compatibility': compatibility,
              'manual_cache': {'prefix_sha256': sha256(manual/'prefix.npy'), 'teacher_sha256': sha256(manual/'teacher.npy')},
              'combined_cache': combined, 'manual_positives': sum(len(s['targets']) for s in scenes),
              'original_manual_negatives': sum(len(s['negatives']) for s in scenes),
              'invalid_selection_centers': center_count, 'new_center_crops': len(center_rows),
              'manual_crops': len(real), 'combined_crops': count, 'real_heldout_images': 0,
              'reused_original_manual_hashes': {name: sha256(original_manual/name)
                                             for name in ('crops.npy', 'prefix.npy', 'crop-index.json')},
              'new_manual_crop_hashes': {name: sha256(manual/name) for name in ('crops.npy', 'crop-index.json')},
              'center_label_semantics': 'Invalid centered detection; fluid may be present elsewhere in the crop.'}
    print('V2 bank', count, 'crops;', center_count, 'invalid centers', flush=True)
    train_water(parent, old, args.output, source, CONFIG, sampler_class=CenterTriplets, final_pass_only=True)
    if sha256(args.parent_checkpoint) != parent_sha:
        raise RuntimeError('Preserved v1 checkpoint changed.')


if __name__ == '__main__':
    main()
