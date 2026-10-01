"""Separate model releases preserve weights without publishing private data."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
from export import pack_bundle, save_trainable_checkpoint


class ExportTests(unittest.TestCase):
    def test_bundle_contains_only_named_graphs_metadata_and_license(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = {'model_id': 'test-droplets', 'version': '1.2.3'}
            for key, digest_key, name in [('model_file', 'sha256', 'query.onnx'),
                                         ('reference_model_file', 'reference_sha256', 'ref.onnx')]:
                (root / name).write_bytes(name.encode())
                config[key], config[digest_key] = name, hashlib.sha256(name.encode()).hexdigest()
            (root / 'droplet_detector.json').write_text(json.dumps(config))
            (root / 'TORCHVISION-LICENSE.txt').write_text('license')
            (root / 'private-source.png').write_bytes(b'private')
            archive = pack_bundle(root, root / 'test.icescopy-model')
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()), {'query.onnx', 'ref.onnx', 'droplet_detector.json', 'TORCHVISION-LICENSE.txt'})
                self.assertEqual(bundle.read('query.onnx'), b'query.onnx')
            with self.assertRaises(FileExistsError):
                pack_bundle(root, archive)
            (root / 'ref.onnx').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash'):
                pack_bundle(root, root / 'bad.icescopy-model')
            self.assertFalse((root / 'bad.icescopy-model').exists())

    def test_shareable_checkpoint_preserves_weights_but_excludes_private_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            model = torch.nn.Linear(2, 1)
            metadata = {'format': 'test', 'crop_size': 256, 'total_real_epochs': 60,
                        'source': [{'image': '/private/image.png'}], 'training_manifest_sha256': 'private',
                        'parent_provenance': {'source': 'private'}, 'setups': ['private']}
            path = save_trainable_checkpoint(model, metadata, Path(temp) / 'shared.pt',
                                             model_id='test', version='1.0.0', name='Test')
            saved = torch.load(path, weights_only=True)
            self.assertEqual(saved['total_real_epochs'], 60)
            self.assertEqual(saved['version'], '1.0.0')
            self.assertTrue({'source', 'training_manifest_sha256', 'parent_provenance', 'setups'}.isdisjoint(saved))
            for key, value in model.state_dict().items():
                torch.testing.assert_close(saved['state_dict'][key], value)
            with self.assertRaises(FileExistsError):
                save_trainable_checkpoint(model, metadata, path, model_id='test', version='1.0.0', name='Test')
