"""Validate disjoint image regions before making any augmented training tile."""
from __future__ import annotations

import json
from pathlib import Path

from hybrid_data import sha256
from water_center_data import check_center_manifest


FORMAT = 'joint-spatial-split-v1'


def check_spatial_manifest(manifest):
    parent_ref = manifest['parent_manual_manifest']
    if sha256(parent_ref['path']) != parent_ref['sha256']:
        raise ValueError('Original reviewed annotations changed.')
    parent = json.loads(Path(parent_ref['path']).read_text())
    old_ref = parent['previous_manual_manifest']
    if sha256(old_ref['path']) != old_ref['sha256']:
        raise ValueError('Original manual annotations changed.')
    original = json.loads(Path(old_ref['path']).read_text())
    check_center_manifest(parent, original)
    # This recorded parent predates every real-image update. The reviewed
    # whole-image manifest instead points to a real-trained model: do not use it.
    if manifest['starting_encoder'] != original['starting_encoder']:
        raise ValueError('Spatial evaluation requires the synthetic-only parent.')
    sources = {row['id']: row for row in parent['scenes']}
    grouped = {identity: {} for identity in sources}
    seen_ids = set()
    for row in manifest['scenes']:
        source = sources[row['original_scene_id']]
        split = row['split']
        if (split not in {'fit', 'validation', 'test'} or split in grouped[source['id']]
                or row['id'] in seen_ids or row['group'] != row['id']):
            raise ValueError('Expected exactly one unique region per source and split.')
        seen_ids.add(row['id'])
        box = row['source_bbox']
        x0, y0, x1, y1 = box
        if (any(type(v) is not int for v in box) or not
                (0 <= x0 < x1 <= source['width'] and 0 <= y0 < y1 <= source['height'])):
            raise ValueError('Invalid original-pixel region.')
        if (row['original_source'] != source['source'] or row['original_sha256'] != source['sha256']
                or (row['width'], row['height']) != (x1-x0, y1-y0)):
            raise ValueError('Region provenance or dimensions changed.')
        if row.get('complete_labels', False):
            raise ValueError('Unmarked real pixels must remain unknown.')
        for kind in ('targets', 'negatives', 'center_negatives'):
            expected = [dict(c, x=c['x']-x0, y=c['y']-y0) for c in source[kind]
                        if (c['x']-c['radius'] >= x0 and c['y']-c['radius'] >= y0
                            and c['x']+c['radius'] < x1 and c['y']+c['radius'] < y1)]
            if row[kind] != expected:
                raise ValueError('Region labels must preserve the exact contained original circles.')
        if len(row['targets']) < 2:
            raise ValueError('Each region needs at least two example droplets.')
        if sha256(row['source']) != row['sha256']:
            raise ValueError('Saved region pixels changed.')
        grouped[source['id']][split] = row
    for regions in grouped.values():
        if set(regions) != {'fit', 'validation', 'test'}:
            raise ValueError('A source is missing a fit, validation or test region.')
        rows = list(regions.values())
        for i, first in enumerate(rows):
            a = first['source_bbox']
            for second in rows[i+1:]:
                b = second['source_bbox']
                if max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3]):
                    raise ValueError('Training and evaluation pixels overlap.')
                for kind in ('targets', 'negatives', 'center_negatives'):
                    if {r['id'] for r in first[kind]} & {r['id'] for r in second[kind]}:
                        raise ValueError('An original annotation crosses split boundaries.')
    return manifest['scenes']
