"""Compare the packaged CPU detector with saved PyTorch evaluation predictions."""
import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from icescopy_neural_detection import Circle, NeuralDetector, load_model


def check(manifest, evaluation, output):
    manifest, evaluation, output = map(Path, (manifest, evaluation, output))
    if output.exists():
        raise FileExistsError(output)
    sources = {row['setup']: row for row in json.loads(manifest.read_text())['setups']}
    saved = json.loads(evaluation.read_text())
    config = load_model()
    if config.metadata['training_model_sha256'] != saved['model_sha256']:
        raise ValueError('Evaluation and runtime model weights differ')
    detector = NeuralDetector(config)
    results = []
    for row in saved['results']:
        partition = 'train' if row['partition'] == 'train' else 'evaluation'
        with Image.open(manifest.parent / sources[row['dataset']][partition]['image']) as image:
            values = np.asarray(image)
            if values.dtype == np.uint16:
                image = Image.fromarray(np.rint(values.astype(np.float32) / 257).astype(np.uint8))
            rgb = np.array(image.convert('RGB'))
        examples = [Circle(*c) for c in row['examples']]
        start = time.perf_counter()
        predictions = detector.predict(rgb, examples=examples)
        elapsed = time.perf_counter() - start
        remaining = [p['circle'] for p in predictions]
        largest_error = 0.0
        saved_only = []
        for expected in row['circles']:
            if not remaining:
                saved_only.append(expected)
                continue
            index = min(range(len(remaining)), key=lambda i: sum(
                (remaining[i][key] - expected[key]) ** 2 for key in ('x', 'y')))
            # Use the same object-matching rule as evaluate.py. Tiny score
            # changes can choose another peak on a broad droplet response.
            if np.hypot(remaining[index]['x'] - expected['x'], remaining[index]['y'] - expected['y']) > max(3.5, 0.35 * expected['radius']):
                saved_only.append(expected)
                continue
            actual = remaining.pop(index)
            largest_error = max(largest_error, *(abs(actual[key] - expected[key]) for key in ('x', 'y', 'radius')))
        runtime_only = [p for p in predictions if p['circle'] in remaining]
        # OpenCV 4 and 5 warpAffine can differ by one 8-bit level in reference
        # crops. Keep the threshold unchanged and report borderline changes.
        assert all(abs(p['confidence'] - config.threshold) < 0.03 for p in saved_only), saved_only
        assert all(abs(p['score'] - config.threshold) < 0.03 for p in runtime_only), runtime_only
        # Repeat with all output cells protected, as when invoking the tool again.
        assert not detector.predict(rgb, examples=examples,
                                    protected=[p['circle'] for p in predictions])
        counts = {}
        extra_examples = [Circle(**p['circle']) for p in predictions[:3]]
        for count in (0, 1, 3, 5):
            selected = (examples + extra_examples)[:count]
            assert len(selected) == count
            counts[str(count)] = len(detector.predict(rgb, examples=selected))
        result = dict(dataset=row['dataset'], partition=row['partition'], count=len(predictions),
                      seconds=elapsed, max_geometry_error_pixels=largest_error,
                      saved_count=row['count'], saved_only=saved_only, runtime_only=runtime_only,
                      repeat_added=0, example_count_outputs=counts)
        results.append(result)
        print(json.dumps(result), flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'model_sha256': saved['model_sha256'], 'results': results,
                                 'note': 'Counts for other example sets are functional checks, not accuracy scores.'}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('manifest', 'evaluation', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    check(**vars(parser.parse_args()))
