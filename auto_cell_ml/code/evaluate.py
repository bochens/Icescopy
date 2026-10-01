"""Show example-guided predictions on training and separate evaluation recordings."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

if __package__:
    from . import data, infer
else:
    import data
    import infer


def match_centers(predictions, labels):
    """Maximum one-to-one matches within max(3.5 pixels, 35% of labeled radius)."""
    labels = np.asarray(labels, dtype=float).reshape(-1, 3)
    predicted = np.asarray([[p['x'], p['y']] for p in predictions], dtype=float).reshape(-1, 2)
    distances = np.linalg.norm(predicted[:, None] - labels[None, :, :2], axis=2)
    allowed = np.maximum(3.5, 0.35 * labels[:, 2])
    neighbors = [sorted(np.flatnonzero(row <= allowed).tolist(), key=lambda i: row[i])
                 for row in distances]
    owners = {}

    def assign(prediction, visited):
        for label in neighbors[prediction]:
            if label in visited:
                continue
            visited.add(label)
            if label not in owners or assign(owners[label], visited):
                owners[label] = prediction
                return True
        return False

    for prediction in range(len(predicted)):
        assign(prediction, set())
    return {'matched': len(owners), 'missed': len(labels) - len(owners),
            'extra_or_misplaced': len(predictions) - len(owners),
            'reference_count': len(labels),
            'matching_rule': 'one-to-one centers within max(3.5 pixels, 35% of labeled radius)'}


def evaluate(manifest, examples, model, output, *, device='cpu', threshold=0.5):
    manifest, examples, model, output = map(Path, (manifest, examples, model, output))
    if output.exists():
        raise FileExistsError(f'Evaluation directory already exists: {output}')
    rows = json.loads(manifest.read_text())['setups']
    evaluation_examples = json.loads(examples.read_text())['examples']
    output.mkdir(parents=True, exist_ok=False)
    report = {'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
              'example_file_sha256': hashlib.sha256(examples.read_bytes()).hexdigest(),
              'threshold': threshold, 'device': device, 'results': [],
              'note': 'Training matches are diagnostics. Independent images have no complete labels; inspect overlays.'}
    for row in rows:
        name = row['setup']
        _, circles, _ = data._read_source(manifest, name)
        # Fixed source-label indices, chosen independently of predictions.
        indices = sorted(set((0, len(circles) // 2)))
        seeds = circles[indices].tolist()
        result = infer.run(model, manifest.parent / row['train']['image'],
                           output / 'train' / name, examples=seeds, device=device, threshold=threshold)
        remaining = np.delete(circles, indices, axis=0)
        result.update(partition='train', dataset=name, supplied_example_count=len(indices),
                      training_diagnostic=match_centers(result['circles'], remaining))
        report['results'].append(result)
        evaluation = row['evaluation']
        if evaluation.get('image'):
            image = manifest.parent / evaluation['image']
            if hashlib.sha256(image.read_bytes()).hexdigest() != evaluation['sha256']:
                raise ValueError(f'Evaluation source hash changed: {name}')
            result = infer.run(model, image, output / 'independent' / name,
                               examples=evaluation_examples[name], device=device, threshold=threshold)
            result.update(partition='independent', dataset=name)
            report['results'].append(result)
        (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('manifest', 'examples', 'model', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--device', choices=('cpu', 'mps', 'cuda'), default='cpu')
    parser.add_argument('--threshold', type=float, default=0.5)
    evaluate(**vars(parser.parse_args()))


if __name__ == '__main__':
    main()
