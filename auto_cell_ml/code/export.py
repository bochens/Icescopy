"""Export the app's two small inference graphs and a default training reference."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

import numpy as np
import torch

if __package__:
    from . import data
    from .model import load_model, export_runtime_onnx
else:
    import data
    from model import load_model, export_runtime_onnx


def pack_bundle(folder, archive):
    """Create one portable inference file; no Python code or training data."""
    folder, archive = Path(folder), Path(archive)
    if archive.exists():
        raise FileExistsError(archive)
    if archive.suffix != '.icescopy-model':
        raise ValueError('Model bundles must use the .icescopy-model extension')
    metadata = json.loads((folder / 'droplet_detector.json').read_text())
    for key in ('model_id', 'version'):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f'Model requires {key}')
    names = ['droplet_detector.json']
    for key, digest in (('model_file', 'sha256'), ('reference_model_file', 'reference_sha256')):
        name = metadata[key]
        if Path(name).name != name or '/' in name or '\\' in name or name in names:
            raise ValueError('Graph names must be distinct local filenames')
        if data._hash(folder / name) != metadata[digest]:
            raise ValueError(f'Graph hash mismatch: {name}')
        names.append(name)
    names.extend(name for name in ('README.md', 'TORCHVISION-LICENSE.txt') if (folder / name).is_file())
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in names:
            bundle.write(folder / name, name)
    return archive


def save_trainable_checkpoint(model, metadata, path, *, model_id, version, name):
    """Share weights and architecture without private source names or labels."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    public = {key: metadata[key] for key in ('format', 'architecture', 'crop_size', 'stride',
              'parameters', 'pretrained_sha256', 'normalization') if key in metadata}
    public.update(model_id=model_id, setup=model_id, version=version, name=name,
                  total_real_epochs=metadata.get('total_real_epochs', metadata.get('epochs')),
                  state_dict={key: value.detach().cpu() for key, value in model.state_dict().items()})
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents replacing another training checkpoint.
    with path.open('xb') as stream:
        torch.save(public, stream)
    return path


def export_bundle(model_path, manifest, output, *, version, model_id='general-droplets', name='General droplets', archive=None, trainable=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+-]*', version):
        raise ValueError('Use a version code such as 1.0.0')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', model_id) or not name.strip():
        raise ValueError('Supply a model name and a lowercase model ID such as general-droplets')
    model_path, manifest, output = map(Path, (model_path, manifest, output))
    if output.exists():
        raise FileExistsError(output)
    for destination in (archive, trainable):
        if destination is not None and Path(destination).exists():
            raise FileExistsError(destination)
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
    config = {'format': 'icescopy-droplet-onnx-v2', 'name': name, 'model_id': model_id, 'version': version,
              'model_file': detector.name, 'sha256': data._hash(detector),
              'reference_model_file': reference.name, 'reference_sha256': data._hash(reference),
              'tile_size': metadata['crop_size'], 'example_size': 64, 'stride': model.stride,
              'threshold': 0.5, 'default_reference': default_reference, 'default_radius': default_radius,
              'default_reference_source': 'Equal-weight mean of each training setup positive descriptor mean',
              'training_model_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
              'total_real_epochs': metadata.get('total_real_epochs', metadata['epochs']),
              'parameters': metadata['parameters']}
    (output / 'droplet_detector.json').write_text(json.dumps(config, indent=2, allow_nan=False) + '\n')
    shutil.copyfile(Path(__file__).resolve().parents[2] / 'resources/models/TORCHVISION-LICENSE.txt',
                    output / 'TORCHVISION-LICENSE.txt')
    (output / 'README.md').write_text(
        f'# {name} {version}\n\nModel ID: {model_id}. Format: {config["format"]}.\n\n'
        'Load the .icescopy-model file in Icescopy Preferences → ML. '
        'This contains inference networks, not training images or executable Python code. '
        'The encoder was initialized from TorchVision MobileNetV3-Small; its license is included.\n')
    if archive is not None:
        pack_bundle(output, archive)
    if trainable is not None:
        save_trainable_checkpoint(model, metadata, trainable, model_id=model_id, version=version, name=name)
    print(f'Exported {detector.stat().st_size + reference.stat().st_size:,} model bytes to {output}', flush=True)
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model-path', 'manifest', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--version', required=True, help='Independent model release version, such as 1.0.0')
    parser.add_argument('--model-id', default='general-droplets')
    parser.add_argument('--name', default='General droplets')
    parser.add_argument('--archive', type=Path, help='Optional separate .icescopy-model file')
    parser.add_argument('--trainable', type=Path, help='Optional shareable .pt checkpoint without private data metadata')
    export_bundle(**vars(parser.parse_args()))
