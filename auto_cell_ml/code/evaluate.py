"""Show example-guided predictions on training and separate evaluation recordings."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

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
    write_overview(output, report)
    write_overview(output, report, partition='train')
    return report


def write_overview(output, report, *, partition='independent'):
    """A compact visual result, with supplied examples distinct from new circles."""
    if partition not in ('train', 'independent'):
        raise ValueError('Unknown evaluation partition')
    rows = [row for row in report['results'] if row['partition'] == partition]
    if not rows:
        return
    output = Path(output)
    destination = output / ('training-overview.jpg' if partition == 'train' else 'overview.jpg')
    if destination.exists():
        raise FileExistsError(destination)
    width, height = 800, 650
    canvas = Image.new('RGB', (width * 2, height * ((len(rows) + 1) // 2)), 'white')
    draw = ImageDraw.Draw(canvas)
    for index, row in enumerate(rows):
        x, y = (index % 2) * width, (index // 2) * height
        label = 'Training image' if partition == 'train' else 'Separate recording'
        draw.text((x + 12, y + 10), f"{row['dataset']} | {label}", fill='black', font_size=20)
        if partition == 'train':
            score = row['training_diagnostic']
            detail = f"{score['matched']}/{score['reference_count']} remaining labels found; {score['extra_or_misplaced']} extras"
        else:
            detail = f"{row['count']} new selections + {len(row['examples'])} examples"
        draw.text((x + 12, y + 42), detail, fill='black', font_size=18)
        note = 'Training diagnostic only' if partition == 'train' else 'No complete evaluation labels'
        draw.text((x + 12, y + 67), f'Green: new | Cyan: supplied examples | {note}',
                  fill='black', font_size=16)
        with Image.open(output / partition / (row['dataset'] + '.jpg')) as preview:
            preview.thumbnail((width - 24, height - 108))
            canvas.paste(preview, (x + (width - preview.width) // 2, y + 100))
    canvas.save(destination, quality=93)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('manifest', 'examples', 'model', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--device', choices=('cpu', 'mps', 'cuda'), default='cpu')
    parser.add_argument('--threshold', type=float, default=0.5)
    evaluate(**vars(parser.parse_args()))


if __name__ == '__main__':
    main()
