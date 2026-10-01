"""Label-aware tiles for a shared, example-conditioned center detector.

All coordinates use original pixels until one isotropic affine transform is
applied to the image and every annotation. Real unmarked pixels remain unknown.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

from detector import read_image
from hybrid_data import sha256
from joint_model import CORE, HALO, NORMALIZED_RADIUS, PADDING_RGB, STRIDE, TILE
from joint_spatial import FORMAT as SPATIAL_FORMAT, check_spatial_manifest
from neural_train import check_manifest
from water_center_data import check_center_manifest

SUPERVISION_VERSION = 2

def active_scenes(real_path, synthetic_path):
    real_manifest = json.loads(Path(real_path).read_text())
    spatial = real_manifest.get('format_version') == SPATIAL_FORMAT
    if spatial:
        real = check_spatial_manifest(real_manifest)
    else:
        previous = real_manifest['previous_manual_manifest']
        if sha256(previous['path']) != previous['sha256']:
            raise ValueError('Preserved original manual manifest changed.')
        real = check_center_manifest(real_manifest, json.loads(Path(previous['path']).read_text()))
    synthetic = check_manifest(json.loads(Path(synthetic_path).read_text()))
    scenes = []
    for domain, rows in (('real', real), ('synthetic', synthetic)):
        for original in rows:
            if original['split'] in {'calibration', 'test'}:
                continue
            row = dict(original, domain=domain,
                       split='fit' if domain == 'real' and not spatial else original['split'])
            if sha256(row['source']) != row['sha256']:
                raise ValueError('Active source pixels changed.')
            scenes.append(row)
    return real_manifest, scenes


def transformed(rows, matrix):
    scale = float(np.hypot(matrix[0, 0], matrix[0, 1]))
    return [dict(row, x=float(matrix[0] @ [row['x'], row['y'], 1]),
                 y=float(matrix[1] @ [row['x'], row['y'], 1]), radius=float(row['radius']*scale))
            for row in rows]


def affine_for(scene, focus, rng, augment=True):
    """Keep a selected center in the core and a real positive query in the tile."""
    radius = float(np.median([row['radius'] for row in scene['targets']]))
    scale = NORMALIZED_RADIUS/radius
    angle = float(rng.uniform(-180, 180)) if augment else 0.
    scale *= float(rng.uniform(.75, 1.25)) if augment else 1.
    a = math.radians(angle)
    linear = scale*np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    if augment and rng.random() < .5:
        linear[0] *= -1
    if augment and rng.random() < .5:
        linear[1] *= -1
    closest = min(scene['targets'], key=lambda p: (p['x']-focus['x'])**2+(p['y']-focus['y'])**2)
    delta = linear @ np.array([closest['x']-focus['x'], closest['y']-focus['y']])
    # A far background point may need the query in the halo. It is not changed
    # into a positive label or shifted onto a droplet center.
    focus_at = np.array([TILE/2, TILE/2], dtype=float)
    margin = closest['radius']*scale+8
    focus_at = np.clip(focus_at, margin-delta, TILE-margin-delta)
    focus_at = np.clip(focus_at, HALO+12, TILE-HALO-12)
    if augment:
        # Move the crop across the source rather than nearly always placing
        # the chosen droplet at the tile center. Keep both the supervised focus
        # in the core and its nearest complete example inside the tile.
        low = np.maximum(HALO+12, margin-delta)
        high = np.minimum(TILE-HALO-12, TILE-margin-1-delta)
        if np.all(high > low):
            focus_at = rng.uniform(low, high)
    matrix = np.c_[linear, focus_at-linear @ np.array([focus['x'], focus['y']])].astype(np.float32)
    return matrix


def photometric(tile, rng):
    values = (tile-.5)*float(rng.uniform(.8, 1.2))+.5
    values = np.clip(values*float(rng.uniform(.78, 1.22))+rng.uniform(-.03, .03), 0, 1)
    values = values**float(rng.uniform(.85, 1.18))
    values *= rng.uniform(.9, 1.1, size=(1, 1, 3))
    if rng.random() < .3:
        values = np.repeat(values.mean(2, keepdims=True), 3, 2)
    if rng.random() < .5:
        values = cv2.GaussianBlur(values, (0, 0), float(rng.uniform(.2, .8)))
    return np.clip(values, 0, 1).astype(np.float32)


def circle_usable(row, valid):
    x, y, r = row['x'], row['y'], row['radius']
    if x-r < 0 or y-r < 0 or x+r >= TILE or y+r >= TILE:
        return False
    angles = np.linspace(0, 2*np.pi, 16, endpoint=False)
    xx = np.rint(np.r_[x, x+r*np.cos(angles)]).astype(int)
    yy = np.rint(np.r_[y, y+r*np.sin(angles)]).astype(int)
    if not ((xx >= 0).all() and (yy >= 0).all() and (xx < TILE).all() and (yy < TILE).all()):
        return False
    return bool(valid[yy, xx].all())


def targets_for(scene, matrix, valid):
    """Offsets/radii supervise known centers; invalid points supervise no center.

    Constant padding and the halo never contribute to a loss. Complete
    synthetic labels supply background; incomplete real images only supply
    positive neighborhoods and explicit reviewed negative neighborhoods.
    """
    size = TILE//STRIDE
    yy, xx = np.mgrid[:size, :size].astype(np.float32)
    heat = np.zeros((size, size), np.float32)
    core = np.zeros_like(heat)
    core[HALO//STRIDE:(HALO+CORE)//STRIDE, HALO//STRIDE:(HALO+CORE)//STRIDE] = 1
    usable_pixels = valid[::STRIDE, ::STRIDE].astype(np.float32)*core
    mask = usable_pixels.copy() if scene.get('complete_labels', False) else np.zeros_like(heat)
    offset = np.zeros((2, size, size), np.float32)
    radius = np.zeros((1, size, size), np.float32)
    center_mask = np.zeros((size, size), np.float32)
    reviewed_negative = np.zeros((size, size), np.float32)
    positives = transformed(scene['targets'], matrix)
    positive_ids = []
    invalid_ids = []
    # Ignore a partial object's neighborhood before marking any known centers.
    for row in positives:
        if not circle_usable(row, valid):
            mask[(STRIDE*xx-row['x'])**2+(STRIDE*yy-row['y'])**2 < (1.3*row['radius'])**2] = 0
    old_negative_ids = []
    for row in transformed(scene.get('negatives', []), matrix):
        disk = (STRIDE*xx-row['x'])**2+(STRIDE*yy-row['y'])**2 <= row['radius']**2
        mask[disk] = usable_pixels[disk]
        if scene['domain'] == 'real': reviewed_negative[disk] = usable_pixels[disk]
        if (disk*usable_pixels).any():
            old_negative_ids.append(int(row.get('id', row.get('slot'))))
    for row in transformed(scene.get('center_negatives', []), matrix):
        x, y = int(math.floor(row['x']/STRIDE)), int(math.floor(row['y']/STRIDE))
        if 0 <= x < size and 0 <= y < size and usable_pixels[y, x]:
            mask[y, x] = 1
            if scene['domain'] == 'real': reviewed_negative[y, x] = 1
            invalid_ids.append(int(row['id']))
    for row in positives:
        x, y = int(math.floor(row['x']/STRIDE)), int(math.floor(row['y']/STRIDE))
        if not circle_usable(row, valid) or not (0 <= x < size and 0 <= y < size and usable_pixels[y, x]):
            continue
        distance = (xx-x)**2+(yy-y)**2
        sigma = max(.65, row['radius']*.12/STRIDE)
        neighborhood = (STRIDE*xx-row['x'])**2+(STRIDE*yy-row['y'])**2 <= (.35*row['radius'])**2
        neighborhood[y, x] = True
        # One labeled droplet means one center throughout its known interior.
        # The narrow Gaussian remains unchanged; the rest is zero-center truth,
        # not unknown space into which a rim peak can escape the penalty.
        interior = (STRIDE*xx-row['x'])**2+(STRIDE*yy-row['y'])**2 <= row['radius']**2
        heat[neighborhood] = np.maximum(heat[neighborhood], np.exp(-distance[neighborhood]/(2*sigma*sigma)))
        heat[y, x] = 1
        mask[interior] = usable_pixels[interior]
        mask[neighborhood] = usable_pixels[neighborhood]
        offset[:, y, x] = [row['x']/STRIDE-x, row['y']/STRIDE-y]
        radius[0, y, x] = row['radius']
        center_mask[y, x] = 1
        positive_ids.append(int(row.get('id', row.get('slot'))))
    # A sampled invalid point coinciding with a true center's supervision is
    # contradictory at this output resolution. Do not count it as updated.
    invalid_ids = [int(row['id']) for row in transformed(scene.get('center_negatives', []), matrix)
                   if int(row['id']) in invalid_ids and heat[int(row['y']//STRIDE), int(row['x']//STRIDE)] == 0]
    return {'heat': heat[None], 'mask': (mask*usable_pixels)[None], 'offset': offset,
            'radius': radius, 'center_mask': center_mask[None],
            'reviewed_negative_mask': (reviewed_negative*usable_pixels*(heat == 0))[None]}, positive_ids, invalid_ids, old_negative_ids


def make_tile(scene, image, focus, rng, augment=True):
    matrix = affine_for(scene, focus, rng, augment)
    # Do not mirror visible droplets into unlabeled context at crop boundaries.
    tile = cv2.warpAffine(image, matrix, (TILE, TILE), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=PADDING_RGB)
    valid = cv2.warpAffine(np.ones(image.shape[:2], np.uint8), matrix, (TILE, TILE),
                           flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT) > 0
    targets, positive_ids, invalid_ids, old_negative_ids = targets_for(scene, matrix, valid)
    candidates = [row for row in transformed(scene['targets'], matrix) if circle_usable(row, valid)]
    if not candidates:
        return None
    query_count = 1 if rng.random() < .5 or len(candidates) == 1 else 2
    selected = [candidates[i] for i in rng.choice(len(candidates), query_count, replace=False)]
    if len(selected) == 1:
        selected.append(selected[0])  # Exactly equivalent max-correlation to one query.
    query_radius = float(np.median([row['radius'] for row in selected]))
    occupied = targets['center_mask'][0] > 0
    targets['radius'][0, occupied] = np.log(targets['radius'][0, occupied]/query_radius)
    examples = np.array([[row['x']/STRIDE, row['y']/STRIDE, row['radius']/STRIDE] for row in selected], np.float32)
    record = {'scene_id': scene['id'], 'group': scene['group'], 'domain': scene['domain'], 'split': scene['split'],
              'matrix': matrix.tolist(), 'query_ids': [int(row.get('id', row.get('slot'))) for row in selected],
              'positive_ids': positive_ids, 'invalid_center_ids': invalid_ids, 'old_negative_ids': old_negative_ids}
    return (photometric(tile, rng) if augment else tile.astype(np.float32)), targets, examples, record


def tile_bank(scenes, folder, real_count=120, synthetic_fit_count=30, validation_count=10, seed=71003,
              real_validation_count=24):
    """Balanced fixed bank; first tiles greedily cover exact known real centers."""
    if any(s['split'] not in {'fit', 'validation'} for s in scenes):
        raise ValueError('Only fitting and validation regions can enter the tile cache.')
    plans = [(s, (real_count if s['split'] == 'fit' else real_validation_count) if s['domain'] == 'real' else
              (synthetic_fit_count if s['split'] == 'fit' else validation_count)) for s in scenes]
    count = sum(n for _, n in plans)
    pixels = np.lib.format.open_memmap(folder/'tiles.npy', mode='w+', dtype=np.uint8, shape=(count, TILE, TILE, 3))
    arrays = {name: np.lib.format.open_memmap(folder/(name+'.npy'), mode='w+', dtype=np.float32,
              shape=(count, channels, TILE//STRIDE, TILE//STRIDE))
              for name, channels in [('heat', 1), ('mask', 1), ('offset', 2), ('radius', 1), ('center_mask', 1),
                                     ('reviewed_negative_mask', 1)]}
    queries = np.lib.format.open_memmap(folder/'queries.npy', mode='w+', dtype=np.float32, shape=(count, 2, 3))
    rng = np.random.default_rng(seed); records = []; index = 0
    for scene, amount in plans:
        image = read_image(scene['source']); unseen = {int(row.get('id', row.get('slot'))) for row in scene['targets']}
        invalid = {row['id'] for row in scene.get('center_negatives', [])}
        focuses = scene['targets']+scene.get('center_negatives', [])+scene.get('negatives', [])
        for variant in range(amount):
            # Cover positives first, then invalid points; subsequent tiles replay
            # them with fresh label-aware geometry and ordinary lighting changes.
            pool = [row for row in scene['targets'] if int(row.get('id', row.get('slot'))) in unseen]
            if not pool:
                pool = [row for row in scene.get('center_negatives', []) if row['id'] in invalid]
            if not pool:
                pool = focuses
            focus = pool[int(rng.integers(len(pool)))]; result = make_tile(scene, image, focus, rng, scene['split'] == 'fit')
            if result is None:
                # Far reviewed background cannot supply a same-image query in
                # this tile. Retain it in the manifest and report uncovered IDs.
                result = make_tile(scene, image, scene['targets'][variant % len(scene['targets'])], rng, scene['split'] == 'fit')
            if result is None:
                raise ValueError('No whole positive query can fit in this tile.')
            tile, targets, examples, record = result
            pixels[index] = np.rint(tile*255).astype(np.uint8)
            for name, values in targets.items(): arrays[name][index] = values
            queries[index] = examples
            record.update(index=index, variant=variant); records.append(record); index += 1
            unseen -= set(record['positive_ids']); invalid -= set(record['invalid_center_ids'])
        print('Joint tiles', scene['id'], amount, 'uncovered positives', len(unseen), 'invalid centers', len(invalid), flush=True)
        if scene['domain'] == 'real' and unseen:
            raise RuntimeError('Tile bank failed to cover every manual positive; no training is started.')
    for values in [pixels, queries, *arrays.values()]: values.flush()
    (folder/'tile-index.json').write_text(json.dumps(records)+'\n')
    return records


class TileSchedule:
    """Equal real instruments; greedily update uncovered positives before replay."""
    def __init__(self, records, scenes):
        self.rows = {r['index']: r for r in records}; self.groups = {'real': {}, 'synthetic': {}}
        self.updated_positive = set(); self.updated_invalid = set(); self.updated_old_negative = set()
        self.tile_uses = {r['index']: 0 for r in records}
        self.cursor = {'real': 0, 'synthetic': 0}
        self.expected = {}
        for scene in scenes:
            if scene['domain'] == 'real' and scene['split'] == 'fit':
                self.expected[scene['group']] = {'positives': {r['id'] for r in scene['targets']},
                                               'invalid': {r['id'] for r in scene.get('center_negatives', [])},
                                               'old_negative': {r['id'] for r in scene.get('negatives', [])}}
        for row in records:
            if row['split'] == 'fit': self.groups[row['domain']].setdefault(row['group'], []).append(row)

    def sample(self, rng):
        batch = []
        for domain in ('real', 'synthetic'):
            names = sorted(self.groups[domain])
            for _ in range(2):
                name = names[self.cursor[domain] % len(names)]; self.cursor[domain] += 1
                pool = self.groups[domain][name]
                scores = [sum((name, p) not in self.updated_positive for p in r['positive_ids'])*1000+
                          sum((name, p) not in self.updated_invalid for p in r['invalid_center_ids'])+
                          sum((name, p) not in self.updated_old_negative for p in r.get('old_negative_ids', [])) for r in pool]
                best = max(scores)
                choices = [row for row, score in zip(pool, scores) if score == best] if best else pool
                # Once annotation coverage is secured, visit every distinct
                # crop/rotation before replaying already-used variations.
                fewest_uses = min(self.tile_uses[row['index']] for row in choices)
                choices = [row for row in choices if self.tile_uses[row['index']] == fewest_uses]
                batch.append(choices[int(rng.integers(len(choices)))]['index'])
        return np.asarray(batch, np.int64)

    def mark_updated(self, indices):
        for index in indices:
            row = self.rows[int(index)]
            self.tile_uses[int(index)] += 1
            self.updated_positive.update((row['group'], p) for p in row['positive_ids'])
            self.updated_invalid.update((row['group'], p) for p in row['invalid_center_ids'])
            self.updated_old_negative.update((row['group'], p) for p in row.get('old_negative_ids', []))

    def coverage(self):
        return {group: {'positives': len(ids['positives']),
                        'updated_positives': sum((group, p) in self.updated_positive for p in ids['positives']),
                        'invalid_centers': len(ids['invalid']),
                        'updated_invalid_centers': sum((group, p) in self.updated_invalid for p in ids['invalid']),
                        'old_negatives': len(ids['old_negative']),
                        'updated_old_negatives': sum((group, p) in self.updated_old_negative for p in ids['old_negative'])}
                for group, ids in self.expected.items()}

    def all_positives_updated(self):
        return all(row['positives'] == row['updated_positives'] for row in self.coverage().values())
