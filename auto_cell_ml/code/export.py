"""Export the app's two small inference graphs and a default training reference."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

if __package__:
    from . import data
    from .model import load_model, export_runtime_onnx
else:
    import data
    from model import load_model, export_runtime_onnx


def export_bundle(model_path, manifest, output):
    model_path, manifest, output = map(Path, (model_path, manifest, output))
    if output.exists():
        raise FileExistsError(output)
    torch.set_num_threads(4)
    model, metadata = load_model(model_path)
    if data._hash(manifest) != metadata['training_manifest_sha256']:
        raise ValueError('Training manifest does not match the model')
    references, sizes = [], []
    with torch.inference_mode():
        for setup in metadata['setups']:
            image, circles, source = data._read_source(manifest, setup)
            recorded = next(item['source'] for item in metadata['source'] if item['setup'] == setup)
            if source != recorded:
                raise ValueError(f'Training source changed: {setup}')
            descriptors = []
            for circle in circles:
                pixels, _, _ = data.extract_examples(image, [circle])
                tensor = torch.from_numpy(pixels[:1].transpose(0, 3, 1, 2).copy()).float() / 255
                descriptors.append(model.encode_reference(tensor).numpy().reshape(32))
            references.append(np.mean(descriptors, axis=0))
            sizes.append(float(np.mean(circles[:, 2])))
    # Equal setup weights match the training source balance. No source pixels
    # or original filenames are included in the application resource bundle.
    default_reference = np.mean(references, axis=0).astype(float).tolist()
    default_radius = float(np.mean(sizes))
    output.mkdir(parents=True, exist_ok=False)
    detector = output / 'droplet_detector.onnx'
    reference = output / 'droplet_reference.onnx'
    export_runtime_onnx(model, detector, reference, size=metadata['crop_size'])
    config = {'format': 'icescopy-droplet-onnx-v2', 'name': 'General droplets',
              'model_file': detector.name, 'sha256': data._hash(detector),
              'reference_model_file': reference.name, 'reference_sha256': data._hash(reference),
              'tile_size': metadata['crop_size'], 'example_size': 64, 'stride': model.stride,
              'threshold': 0.5, 'default_reference': default_reference, 'default_radius': default_radius,
              'default_reference_source': 'Equal-weight mean of each training setup positive descriptor mean',
              'training_model_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
              'total_real_epochs': metadata.get('total_real_epochs', metadata['epochs']),
              'parameters': metadata['parameters']}
    (output / 'droplet_detector.json').write_text(json.dumps(config, indent=2, allow_nan=False) + '\n')
    print(f'Exported {detector.stat().st_size + reference.stat().st_size:,} model bytes to {output}', flush=True)
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model-path', 'manifest', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    export_bundle(**vars(parser.parse_args()))
