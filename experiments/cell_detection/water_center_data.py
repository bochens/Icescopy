"""Invalid selection centers; a nearby water droplet may still be in the crop."""
from __future__ import annotations

import copy
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np

from detector import Circle, patches, read_image
from hybrid_data import augment_training, sha256
from water_data import WaterTriplets, check_manual_manifest


CENTER_TOLERANCE = .35
MINIMUM_SEPARATION = .55
CENTER_KINDS = {'miscentered', 'between_cells', 'background'}


def center_margin(negative, targets):
    """Check actual rounded patch origin plus one output pixel of safety.

    The shared crop rounds its source center before resizing. Rotation/flips
    and isotropic scaling around the patch center cannot recenter a neighbor.
    This extra margin covers that rounding and one output pixel at scale .90.
    """
    side = max(5, int(round(4.5*negative.radius)) | 1)
    distances = np.asarray([np.hypot(round(negative.x)-c.x, round(negative.y)-c.y)/c.radius for c in targets])
    rounded = np.asarray([np.hypot(round(negative.x)-c.x, round(negative.y)-c.y)-
                          CENTER_TOLERANCE*c.radius-side/(96*.90) for c in targets])
    if distances.min() < MINIMUM_SEPARATION-1e-9 or rounded.min() <= 0:
        raise ValueError('Invalid-center crop is too close to a marked positive after crop rounding.')
    return {'minimum_separation_radius': float(distances.min()), 'rounding_margin_pixels': float(rounded.min())}


def check_center_manifest(manifest, original):
    """Retain every original label; center negatives may overlap circle edges."""
    scenes = check_manual_manifest(manifest)
    old = {s['id']: s for s in check_manual_manifest(original)}
    if set(old) != {s['id'] for s in scenes}:
        raise ValueError('Center training must retain exactly the original instrument images.')
    total = 0
    for scene in scenes:
        before = old[scene['id']]
        for key in ('group', 'sha256', 'width', 'height', 'targets', 'negatives'):
            if scene[key] != before[key]:
                raise ValueError('Original labels or pixels changed: '+scene['id']+' '+key)
        targets = [Circle(float(c['x']), float(c['y']), float(c['radius'])) for c in scene['targets']]
        if not scene.get('center_negative_review_complete'):
            raise ValueError('Invalid-center annotations require completed review.')
        known = set()
        for row in scene.get('center_negatives', []):
            identity = row['id']
            if type(identity) is not int or identity < 0 or identity in known:
                raise ValueError('Center-negative IDs must be unique within their separate namespace.')
            known.add(identity)
            if row.get('kind') not in CENTER_KINDS or not row.get('provenance'):
                raise ValueError('Center negatives require reviewed kind and provenance.')
            circle = Circle(float(row['x']), float(row['y']), float(row['radius']))
            if not (0 <= circle.x < scene['width'] and 0 <= circle.y < scene['height']):
                raise ValueError('Center-negative centers must lie inside the original image.')
            center_margin(circle, targets)
            total += 1
    if not total:
        raise ValueError('No reviewed invalid selection centers supplied.')
    return scenes


def build_center_crops(scenes, folder, variants=4, seed=61004):
    """Exact invalid centers, no crop/radius jitter or affine translation."""
    plans = []
    for scene in scenes:
        if sha256(scene['source']) != scene['sha256']:
            raise ValueError('Center-negative source pixels changed.')
        targets = [Circle(float(c['x']), float(c['y']), float(c['radius'])) for c in scene['targets']]
        for row in scene.get('center_negatives', []):
            circle = Circle(float(row['x']), float(row['y']), float(row['radius']))
            plans.append((scene, row, circle, center_margin(circle, targets)))
    values = np.lib.format.open_memmap(folder/'crops.npy', mode='w+', dtype=np.uint8,
                                     shape=(len(plans)*variants, 96, 96, 3))
    rng = np.random.default_rng(seed); records = []; current = None
    for scene, row, circle, margin in plans:
        if current != scene['id']:
            image = read_image(scene['source']); current = scene['id']
            if image.shape[:2] != (scene['height'], scene['width']):
                raise ValueError('Center-negative source dimensions changed.')
        patch = patches(image, [circle])[0]
        for variant in range(variants):
            index = len(records); values[index] = augment_training(patch, rng, translate=False)
            records.append({'index': index, 'scene_id': scene['id'], 'group': scene['group'],
                            'domain': 'real', 'split': 'fit', 'label': 0,
                            'object_id': 'center_negatives:'+str(row['id']), 'variant': variant,
                            'source_circle': asdict(circle), 'circle': asdict(circle),
                            'label_source': 'explicit_reviewed_invalid_center', 'kind': row['kind'],
                            'provenance': row['provenance'], 'center_guard': margin,
                            'augmentation': 'No crop jitter, radius jitter or translation; centered rotation/flip/isotropic scaling and photometric transforms.'})
    values.flush(); del values
    (folder/'crop-index.json').write_text(json.dumps(records)+'\n')
    return records


def append_manual_cache(parent, previous, centers, output):
    """Reuse original pixels/prefix; regenerate all teachers from the v1 parent."""
    old_rows = json.loads((previous/'crop-index.json').read_text())
    new_rows = json.loads((centers/'crop-index.json').read_text())
    old_crops = np.load(previous/'crops.npy', mmap_mode='r'); new_crops = np.load(centers/'crops.npy', mmap_mode='r')
    old_prefix = np.load(previous/'prefix.npy', mmap_mode='r'); new_prefix = np.load(centers/'prefix.npy', mmap_mode='r')
    if (len(old_rows) != len(old_crops) or len(old_rows) != len(old_prefix) or
            len(new_rows) != len(new_crops) or len(new_rows) != len(new_prefix)):
        raise ValueError('Manual cache records and arrays disagree.')
    count = len(old_rows)+len(new_rows)
    crops = np.lib.format.open_memmap(output/'crops.npy', mode='w+', dtype=np.uint8, shape=(count, 96, 96, 3))
    prefix = np.lib.format.open_memmap(output/'prefix.npy', mode='w+', dtype=np.float32,
                                      shape=(count, *old_prefix.shape[1:]))
    crops[:len(old_rows)] = old_crops; crops[len(old_rows):] = new_crops
    prefix[:len(old_rows)] = old_prefix; prefix[len(old_rows):] = new_prefix
    crops.flush(); prefix.flush(); del crops, prefix
    records = copy.deepcopy(old_rows)
    for row in new_rows:
        records.append(dict(row, index=len(records)))
    (output/'crop-index.json').write_text(json.dumps(records)+'\n')
    from neural_model import FIRST_TRAINABLE_BLOCK, suffix_embeddings
    prefix = np.load(output/'prefix.npy', mmap_mode='r')
    teacher = np.lib.format.open_memmap(output/'teacher.npy', mode='w+', dtype=np.float32, shape=(count, 576))
    with parent.torch.inference_mode():
        for first in range(0, count, 64):
            teacher[first:first+64] = suffix_embeddings(parent.model.features[FIRST_TRAINABLE_BLOCK:],
                parent.torch.from_numpy(np.asarray(prefix[first:first+64]).copy())).numpy()
    teacher.flush(); del teacher
    return records


class CenterTriplets(WaterTriplets):
    """Equal old/new negative sampling, cycling every reviewed invalid center."""
    def __init__(self, records, split):
        super().__init__(records, split)
        self.negative_pools = {}; self.negative_order = {}; self.negative_cursor = {}; self.negative_turn = {}
        self.updated_negative = set()
        for r in records:
            if r['split'] == split and r['domain'] == 'real' and r['label'] == 0:
                kind = 'new' if r['label_source'] == 'explicit_reviewed_invalid_center' else 'old'
                key = (r['group'], r['scene_id'], kind)
                self.negative_pools.setdefault(key, {}).setdefault(r['object_id'], []).append(r)

    def sample(self, rng, count):
        samples = super().sample(rng, count)
        for sample in samples:
            source = self.rows[int(sample[0])]
            if source['domain'] != 'real':
                continue
            frame = (source['group'], source['scene_id'])
            kinds = [kind for kind in ('old', 'new') if (*frame, kind) in self.negative_pools]
            turn = self.negative_turn.get(frame, 0); kind = kinds[turn % len(kinds)]
            self.negative_turn[frame] = turn+1; key = (*frame, kind)
            pool = self.negative_pools[key]; names = sorted(pool)
            if self.negative_cursor.get(key, 0) >= len(self.negative_order.get(key, [])):
                self.negative_order[key] = rng.permutation(len(names)); self.negative_cursor[key] = 0
            name = names[int(self.negative_order[key][self.negative_cursor[key]])]
            self.negative_cursor[key] += 1; variants = pool[name]
            sample[2] = variants[int(rng.integers(len(variants)))]['index']
        return samples

    def mark_updated(self, samples):
        super().mark_updated(samples)
        for index in samples[:, 2]:
            r = self.rows[int(index)]
            if r.get('label_source') == 'explicit_reviewed_invalid_center':
                self.updated_negative.add((r['group'], r['scene_id'], r['object_id']))

    def negative_coverage(self):
        return {group: {'centers': len(pool),
                        'updated_centers': sum((group, scene, identity) in self.updated_negative for identity in pool)}
                for (group, scene, kind), pool in self.negative_pools.items() if kind == 'new'}

    def all_manual_updated(self):
        return super().all_manual_updated() and all(c['centers'] == c['updated_centers']
                                                   for c in self.negative_coverage().values())
