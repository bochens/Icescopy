"""Train one shared example-guided center/offset/radius network on active data."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import time

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from hybrid_data import sha256
from joint_data import SUPERVISION_VERSION, TileSchedule, active_scenes, tile_bank
from joint_model import ARCHITECTURE, VERSION, STRIDE, TILE, JointNetwork, input_tensor, save_joint
from joint_spatial import FORMAT as SPATIAL_FORMAT
from neural_model import batchnorm_buffers, changed_tensors, prefix_state, tensor_hash


CONFIG = {'seed': 71003, 'threads': 4, 'passes': 4, 'steps_per_pass': 60,
          'batch_tiles': 4, 'real_tiles_per_instrument': 240, 'synthetic_fit_tiles_per_scene': 30,
          'synthetic_validation_tiles_per_scene': 10, 'backbone_learning_rate': 5e-5,
          'real_validation_tiles_per_scene': 40,
          'decoder_learning_rate': 2e-4, 'weight_decay': 1e-4, 'negative_loss_weight': 2.,
          'supervision_version': SUPERVISION_VERSION, 'reviewed_negative_bce_weight': 1.,
          'reviewed_negative_rule': 'Mean max-logit BCE per reviewed empty annotation; mean BCE per invalid-center annotation; average available category means.',
          'augmentation_version': 2,
          'padding': 'Constant ImageNet mean RGB; outside-source pixels and halo excluded from loss. No mirrored objects.',
          'augmentation': 'Uniform rotation -180..180 degrees, isotropic scale0.75..1.25, full-core crop translation, flips and bounded lighting/blur.',
          'tile_sampling': 'Cover labels first, then visit each distinct crop before replaying it.',
          'offset_loss_weight': 1., 'radius_loss_weight': .1, 'gradient_clip': 5.,
          'selection': 'Lowest validation loss versus initial weights, equally over domains/scenes; trained checkpoints require all fitting positives and reviewed empty centers updated.',
          'required_real_cache_coverage': 'Every fitting and validation positive and reviewed empty center; disk-edge intersection alone does not count.',
          'conditioning': 'Actual shared-image features pooled at one or two supplied positive circles.',
          'input_normalization': 'Source whole-frame1/99 normalization then ImageNet channel normalization; no per-tile percentile normalization.',
          'calibration': 'Separate synthetic calibration uses centered F1; no real output selects weights or cutoff.'}


def reviewed_region_bce(logits, target):
    """Each annotated empty region contributes its worst pixel exactly once.

    Adding easy negative pixels cannot dilute a region's false peak. Invalid
    points remain individual annotation centers, rather than empty disks. The
    two category means share total weight one, so many invalid points cannot
    drown a small number of reviewed empty wells. Unknown/padded pixels and
    positive Gaussian conflicts contribute no gradient.
    """
    allowed = (target['mask'] > 0) & (target['heat'] == 0)
    regions = target['reviewed_empty_regions'].bool() & allowed
    present = regions.flatten(2).any(-1)
    empty = logits.sum()*0
    if present.any():
        peaks = logits.expand_as(regions).masked_fill(~regions, -torch.inf).flatten(2).amax(-1)
        empty = F.softplus(peaks[present]).mean()
    points = target['reviewed_invalid_points'].long()
    h, w = logits.shape[-2:]; x, y = points[..., 0], points[..., 1]
    valid = (x >= 0) & (y >= 0) & (x < w) & (y < h)
    indices = y.clamp(0, h-1)*w+x.clamp(0, w-1)
    valid &= allowed.flatten(2)[:, 0].gather(1, indices)
    invalid = logits.sum()*0
    if valid.any():
        values = logits.flatten(2)[:, 0].gather(1, indices)
        invalid = F.softplus(values[valid]).mean()
    terms = ([empty] if present.any() else [])+([invalid] if valid.any() else [])
    combined = torch.stack(terms).mean() if terms else logits.sum()*0
    return combined, empty, invalid, int(present.sum()), int(valid.sum())


def joint_loss(predicted, target, cfg=CONFIG):
    """Focal center loss, with an explicit doubled penalty for false centers."""
    logits = predicted['logits']; heat = target['heat']; mask = target['mask']
    probability = logits.sigmoid()
    positive = (heat == 1).float()*mask
    negative = (heat < 1).float()*mask
    count = positive.sum().clamp_min(1)
    positive_loss = -(F.logsigmoid(logits)*(1-probability).pow(2)*positive).sum()/count
    negative_loss = -(F.logsigmoid(-logits)*probability.pow(2)*(1-heat).pow(4)*negative).sum()/count
    confidence = positive_loss+cfg['negative_loss_weight']*negative_loss
    reviewed_bce, empty_bce, invalid_bce, empty_count, invalid_count = reviewed_region_bce(logits, target)
    centers = target['center_mask']
    offset = (F.smooth_l1_loss(predicted['offset'], target['offset'], reduction='none')*centers).sum()/(2*count)
    radius = (F.smooth_l1_loss(predicted['log_radius'], target['radius'], reduction='none')*centers).sum()/count
    total = confidence+cfg['reviewed_negative_bce_weight']*reviewed_bce+cfg['offset_loss_weight']*offset+cfg['radius_loss_weight']*radius
    return total, {'total': float(total.detach()), 'confidence': float(confidence.detach()),
                   'positive': float(positive_loss.detach()), 'negative': float(negative_loss.detach()),
                   'offset': float(offset.detach()), 'radius': float(radius.detach()),
                   'reviewed_negative_bce': float(reviewed_bce.detach()),
                   'reviewed_empty_peak_bce': float(empty_bce.detach()),
                   'reviewed_invalid_point_bce': float(invalid_bce.detach()),
                   'reviewed_empty_regions': empty_count, 'reviewed_invalid_points': invalid_count}


def cache_features(network, folder, records):
    pixels = np.load(folder/'tiles.npy', mmap_mode='r')
    with torch.no_grad():
        shapes = [tuple(value.shape[1:]) for value in network.prefix_maps(input_tensor(np.asarray(pixels[:1], np.float32)/255))]
    saved = [np.lib.format.open_memmap(folder/f'prefix-{i}.npy', mode='w+', dtype=np.float16,
                                     shape=(len(records), *shape)) for i, shape in enumerate(shapes)]
    start = time.perf_counter()
    with torch.no_grad():
        for first in range(0, len(records), 8):
            last = min(first+8, len(records))
            maps = network.prefix_maps(input_tensor(np.asarray(pixels[first:last], np.float32)/255))
            for output, values in zip(saved, maps): output[first:last] = values.cpu().numpy()
            if first % 200 == 0: print('Joint frozen features', last, '/', len(records), flush=True)
    for output in saved: output.flush()
    return {'seconds': time.perf_counter()-start, 'tiles': len(records), 'shapes': shapes,
            'dtype': 'float16 stored, float32 decoded/trained',
            'files': {f'prefix-{i}.npy': sha256(folder/f'prefix-{i}.npy') for i in range(4)}}


class CachedTiles:
    def __init__(self, folder):
        self.maps = [np.load(folder/f'prefix-{i}.npy', mmap_mode='r') for i in range(4)]
        self.targets = {name: np.load(folder/(name+'.npy'), mmap_mode='r')
                        for name in ('heat', 'mask', 'offset', 'radius', 'center_mask', 'reviewed_negative_mask',
                                     'reviewed_empty_regions', 'reviewed_invalid_points')}
        self.queries = np.load(folder/'queries.npy', mmap_mode='r')

    def batch(self, indices):
        maps = [torch.from_numpy(np.asarray(values[indices], np.float32).copy()) for values in self.maps]
        targets = {name: torch.from_numpy(np.asarray(values[indices]).copy()) for name, values in self.targets.items()}
        queries = torch.from_numpy(np.asarray(self.queries[indices]).copy())
        return maps, targets, queries


def optimizer_for(network, cfg):
    late = [p for p in network.backbone.parameters() if p.requires_grad]
    decoder = [p for name, p in network.named_parameters() if not name.startswith('backbone.')]
    return torch.optim.AdamW([{'params': late, 'lr': cfg['backbone_learning_rate']},
                              {'params': decoder, 'lr': cfg['decoder_learning_rate']}], weight_decay=cfg['weight_decay'])


def initialize_resume(network, checkpoint, source):
    """Continue only a compatible spatial fit, keeping the synthetic prefix."""
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    if saved.get('version') != VERSION or saved.get('architecture') != ARCHITECTURE:
        raise ValueError('Unsupported joint resume checkpoint.')
    metadata = saved['metadata']; previous = metadata['source']
    required = ('real_manifest_sha256', 'synthetic_manifest_sha256', 'parent_encoder_sha256',
                'scene_hashes', 'scene_groups', 'cached_scene_splits')
    if (not source.get('spatial_split') or not previous.get('spatial_split')
            or any(previous.get(k) != source.get(k) for k in required)
            or any(split not in ('fit', 'validation') for split in previous['cached_scene_splits'].values())):
        raise ValueError('Resume checkpoint must use the same spatial manifests and fitting/validation sources.')
    expected = prefix_state(network.backbone)
    preserved = {name: saved['state_dict']['backbone.'+name] for name in expected}
    prefix_hash = tensor_hash(expected)
    if tensor_hash(preserved) != prefix_hash or metadata['frozen_prefix_sha256'] != prefix_hash:
        raise ValueError('Resume checkpoint prefix differs from the preserved synthetic parent.')
    expected_bn = batchnorm_buffers(network.backbone)
    saved_bn = {name: saved['state_dict']['backbone.'+name] for name in expected_bn}
    if tensor_hash(saved_bn) != tensor_hash(expected_bn):
        raise ValueError('Resume checkpoint changed preserved BatchNorm statistics.')
    network.load_state_dict(saved['state_dict'], strict=True); network.eval()
    return {'path': str(Path(checkpoint).resolve()), 'sha256': sha256(checkpoint),
            'selected_pass': metadata['selected_pass'], 'frozen_prefix_sha256': prefix_hash,
            'inherited_selected_actual_update_coverage': metadata.get('selected_actual_update_coverage'),
            'inherited_supervision_version': metadata['config']['supervision_version'],
            'inherited_coverage_note': 'Prior-run coverage is preserved separately; new cache/update coverage uses current center-based semantics.',
            'optimizer_state_resumed': False, 'initialization': 'Preserved selected joint weights; fresh optimizer.'}


def tiny_update_check(network, cache, index, folder, cfg):
    """One disposable update proves actual convolution changes and invariants."""
    test = copy.deepcopy(network).train(True)
    before = {n: v.detach().cpu().clone() for n, v in test.backbone.state_dict().items()}
    frozen = tensor_hash(prefix_state(test.backbone)); bn = tensor_hash(batchnorm_buffers(test.backbone))
    maps, targets, queries = cache.batch(np.asarray([index])); optimizer = optimizer_for(test, cfg)
    start = time.perf_counter(); optimizer.zero_grad(set_to_none=True)
    predicted = test.predictions(test.decode(maps), queries); loss, parts = joint_loss(predicted, targets, cfg)
    loss.backward(); optimizer.step()
    changes = changed_tensors(before, test.backbone.state_dict())
    report = {'seconds': time.perf_counter()-start, 'loss': parts,
              'changed_convolution_tensors': {n: v for n, v in changes.items() if before[n].ndim == 4},
              'prefix_unchanged': frozen == tensor_hash(prefix_state(test.backbone)),
              'batchnorm_statistics_unchanged': bn == tensor_hash(batchnorm_buffers(test.backbone)),
              'disposable_update_used_for_final_training': False}
    (folder/'speed-gradient-check.json').write_text(json.dumps(report, indent=2)+'\n')
    if not report['changed_convolution_tensors'] or not report['prefix_unchanged'] or not report['batchnorm_statistics_unchanged']:
        raise RuntimeError('The joint gradient/invariant check failed.')
    print('Joint disposable update', round(report['seconds'], 3), 'seconds', flush=True)


def select_validation_weights(network, initial_state, initial_loss, trained_loss, trained_pass):
    """Preserve initial weights unless a trained checkpoint improves validation."""
    if trained_loss < initial_loss:
        return trained_pass, trained_loss, True
    network.load_state_dict(initial_state); network.eval()
    return 0, initial_loss, False


def train(network, cache, records, scenes, folder, source, cfg):
    rng = np.random.default_rng(cfg['seed']); schedule = TileSchedule(records, scenes)
    validation = {}
    for record in records:
        if record['split'] == 'validation':
            validation.setdefault(record['domain'], {}).setdefault(record['scene_id'], []).append(record['index'])
    if not validation: raise ValueError('Separate fixed validation tiles are required.')
    before = {n: v.detach().cpu().clone() for n, v in network.backbone.state_dict().items()}
    initial_state = {n: v.detach().cpu().clone() for n, v in network.state_dict().items()}
    prefix_hash = tensor_hash(prefix_state(network.backbone)); bn_hash = tensor_hash(batchnorm_buffers(network.backbone))
    optimizer = optimizer_for(network, cfg)

    def validate():
        domains = {}
        network.eval()
        with torch.no_grad():
            for domain, groups in validation.items():
                scene_values = []
                for indices in groups.values():
                    values = []; weights = []
                    for first in range(0, len(indices), cfg['batch_tiles']):
                        batch = np.asarray(indices[first:first+cfg['batch_tiles']], np.int64)
                        maps, targets, examples = cache.batch(batch)
                        _, parts = joint_loss(network.predictions(network.decode(maps), examples), targets, cfg)
                        values.append(parts); weights.append(len(batch))
                    scene_values.append({name: float(np.average([r[name] for r in values], weights=weights)) for name in values[0]})
                domains[domain] = {name: float(np.mean([r[name] for r in scene_values])) for name in scene_values[0]}
        combined = {name: float(np.mean([r[name] for r in domains.values()])) for name in next(iter(domains.values()))}
        return dict(combined, by_domain=domains)

    initial = validate(); print('Joint initial validation', json.dumps(initial), flush=True)
    history = []; update_indices = []; best_loss = float('inf'); best_state = None; best_pass = None; start = time.perf_counter()
    for epoch in range(1, cfg['passes']+1):
        network.train(True); losses = []; epoch_start = time.perf_counter()
        for step in range(cfg['steps_per_pass']):
            indices = schedule.sample(rng); maps, targets, examples = cache.batch(indices)
            optimizer.zero_grad(set_to_none=True)
            loss, parts = joint_loss(network.predictions(network.decode(maps), examples), targets, cfg)
            if not torch.isfinite(loss): raise RuntimeError('Nonfinite joint training loss.')
            loss.backward(); torch.nn.utils.clip_grad_norm_([p for p in network.parameters() if p.requires_grad], cfg['gradient_clip'])
            optimizer.step(); schedule.mark_updated(indices); losses.append(parts)
            update_indices.append({'pass': epoch, 'step': step+1, 'tile_indices': indices.tolist()})
            if (step+1) % 20 == 0: print('Joint pass', epoch, 'step', step+1, '/', cfg['steps_per_pass'], flush=True)
        validation_loss = validate(); eligible = schedule.all_required_updated()
        row = {'pass': epoch, 'train_loss': {name: float(np.mean([r[name] for r in losses])) for name in losses[0]},
               'validation_loss': validation_loss, 'seconds': time.perf_counter()-epoch_start,
               'checkpoint_eligible': eligible, 'actual_update_coverage': schedule.coverage()}
        history.append(row); (folder/'history.json').write_text(json.dumps(history, indent=2)+'\n')
        (folder/'update-index.json').write_text(json.dumps(update_indices)+'\n')
        print('Joint pass complete', json.dumps(row), flush=True)
        if eligible and validation_loss['total'] < best_loss:
            best_loss = validation_loss['total']; best_pass = epoch
            best_state = {name: value.detach().cpu().clone() for name, value in network.state_dict().items()}
    if best_state is None: raise RuntimeError('Fixed training budget did not update every manual positive and reviewed empty center.')
    network.load_state_dict(best_state); network.eval()
    trained_changes = changed_tensors(before, network.backbone.state_dict())
    improved = best_loss < initial['total']
    metadata = {'config': cfg, 'architecture': ARCHITECTURE, 'source': source, 'selected_pass': best_pass,
                'initial_validation': initial, 'selected_validation_loss': best_loss,
                'history': history, 'training_seconds': time.perf_counter()-start,
                'frozen_prefix_sha256': prefix_hash, 'batchnorm_statistics_sha256': bn_hash,
                'frozen_prefix_unchanged': prefix_hash == tensor_hash(prefix_state(network.backbone)),
                'batchnorm_statistics_unchanged': bn_hash == tensor_hash(batchnorm_buffers(network.backbone)),
                'changed_backbone_tensor_l2_norms': trained_changes,
                'changed_convolution_tensors': {name: value for name, value in trained_changes.items() if before[name].ndim == 4},
                'selected_actual_update_coverage': history[best_pass-1]['actual_update_coverage'],
                'best_trained_pass': best_pass, 'best_trained_validation_loss': best_loss,
                'best_trained_actual_update_coverage': history[best_pass-1]['actual_update_coverage'],
                'final_actual_update_coverage': schedule.coverage(), 'improved_over_initial_validation': improved,
                'real_images_are_training_diagnostics': not source.get('spatial_split', False),
                'real_heldout_images': 0, 'real_heldout_regions': source.get('real_heldout_regions', 0),
                'note': 'One jointly trained center/offset/radius model. Unknown real pixels are not negative labels. No handcrafted circle proposals.'}
    if not metadata['frozen_prefix_unchanged'] or not metadata['batchnorm_statistics_unchanged'] or not metadata['changed_convolution_tensors']:
        raise RuntimeError('Joint update invariants failed.')
    save_joint(folder/'best-trained.pt', network, metadata)
    selected_pass, selected_loss, improved = select_validation_weights(network, initial_state, initial['total'], best_loss, best_pass)
    if not improved:
        metadata = dict(metadata, selected_pass=0, selected_validation_loss=initial['total'],
                        selected_actual_update_coverage=None, changed_backbone_tensor_l2_norms={},
                        changed_convolution_tensors={},
                        note='No trained checkpoint beat initial validation. The selected model preserves initial weights; best-trained.pt retains actual updated weights.')
    save_joint(folder/'joint.pt', network, metadata)
    (folder/'training-report.json').write_text(json.dumps(metadata, indent=2)+'\n')
    return metadata


def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ('real-labels', 'synthetic-labels', 'parent-checkpoint', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--cache-only', action='store_true')
    parser.add_argument('--prepared-cache', type=Path)
    parser.add_argument('--resume-joint', type=Path, help='Initialize from a compatible spatial joint checkpoint; keep the synthetic parent prefix.')
    parser.add_argument('--new-cache', type=Path, help='Save a new tile cache with the training data; must not exist.')
    parser.add_argument('--passes', type=int, default=CONFIG['passes'])
    args = parser.parse_args(); cfg = dict(CONFIG)
    if args.passes < 1: parser.error('--passes must be a positive integer.')
    if args.prepared_cache and args.new_cache: parser.error('Use either a prepared cache or a new cache path.')
    cfg['passes'] = args.passes
    torch.set_num_threads(cfg['threads']); cv2.setNumThreads(cfg['threads']); torch.manual_seed(cfg['seed'])
    manifest, scenes = active_scenes(args.real_labels, args.synthetic_labels)
    parent_hash = sha256(args.parent_checkpoint)
    if parent_hash != manifest['starting_encoder']['sha256']: raise ValueError('Active manifest specifies a different parent.')
    source = {'real_manifest_path': str(args.real_labels.resolve()), 'real_manifest_sha256': sha256(args.real_labels),
              'synthetic_manifest_path': str(args.synthetic_labels.resolve()), 'synthetic_manifest_sha256': sha256(args.synthetic_labels),
              'parent_checkpoint': str(args.parent_checkpoint.resolve()), 'parent_encoder_sha256': parent_hash,
              'scene_hashes': {s['id']: s['sha256'] for s in scenes}, 'scene_groups': {s['id']: s['group'] for s in scenes},
              'calibration_scenes_used_for_weights': False}
    source['spatial_split'] = manifest.get('format_version') == SPATIAL_FORMAT
    source['real_heldout_regions'] = sum(s['split'] == 'test' for s in manifest['scenes']) if source['spatial_split'] else 0
    source['cached_scene_splits'] = {s['id']: s['split'] for s in scenes}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'config.json').write_text(json.dumps(cfg, indent=2)+'\n')
    network = JointNetwork(args.parent_checkpoint)
    if args.resume_joint:
        source['resume_joint'] = initialize_resume(network, args.resume_joint, source)
    folder = args.prepared_cache or args.new_cache or args.output/'tile-cache'
    if args.prepared_cache:
        provenance = json.loads((folder/'cache-source.json').read_text())
        old_config = {k: v for k, v in provenance['config'].items() if k != 'passes'}
        new_config = {k: v for k, v in cfg.items() if k != 'passes'}
        if provenance['source'] != source or old_config != new_config: raise ValueError('Prepared cache source/config mismatch.')
        for name, expected in provenance['cache_hashes'].items():
            if sha256(folder/name) != expected: raise ValueError('Prepared cache changed.')
        records = json.loads((folder/'tile-index.json').read_text())
    else:
        folder.mkdir(); start = time.perf_counter()
        records = tile_bank(scenes, folder, cfg['real_tiles_per_instrument'], cfg['synthetic_fit_tiles_per_scene'],
                            cfg['synthetic_validation_tiles_per_scene'], cfg['seed'], cfg['real_validation_tiles_per_scene'])
        features = cache_features(network, folder, records)
        source['cache_preparation_seconds'] = time.perf_counter()-start
        # Fixed identity fields enable a fresh training output to reuse preparation.
        cache_source = {k: v for k, v in source.items() if k != 'cache_preparation_seconds'}
        provenance = {'source': cache_source, 'config': cfg, 'frozen_features': features,
                      'cache_hashes': {path.name: sha256(path) for path in folder.iterdir() if path.is_file()}}
        (folder/'cache-source.json').write_text(json.dumps(provenance, indent=2)+'\n')
    cache = CachedTiles(folder)
    tiny_update_check(network, cache, next(r['index'] for r in records if r['domain'] == 'real' and r['split'] == 'fit'), args.output, cfg)
    if args.cache_only:
        print('Prepared joint cache only; no substantive training started.', flush=True); return
    source['tile_cache'] = str(folder.resolve()); source['tile_cache_hashes'] = provenance['cache_hashes']
    train(network, cache, records, scenes, args.output, source, cfg)
    if sha256(args.parent_checkpoint) != parent_hash: raise RuntimeError('Preserved parent changed during training.')
    if args.resume_joint and sha256(args.resume_joint) != source['resume_joint']['sha256']:
        raise RuntimeError('Preserved resume checkpoint changed during training.')


if __name__ == '__main__': main()
