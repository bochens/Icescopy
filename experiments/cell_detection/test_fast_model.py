"""Descriptor and split contracts; do not claim image accuracy from unit tests."""
import subprocess
import sys
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from detector import Circle
from fast_benchmark import CALIBRATION_SEEDS, FORBIDDEN_SEEDS, TRAIN_SEEDS
from fast_model import FEATURE_NAMES, LOCAL_NAMES, RELATIVE_FEATURE_MASK, RELATIVE_FEATURE_NAMES, feature_bank, pair_features


class FastDescriptorTests(unittest.TestCase):
    def test_rotation_tolerance_and_polarity_are_distinct(self):
        yy,xx=np.mgrid[:97,:97]
        gray=(.2+.5*np.exp(-((xx-43)**2+(yy-47)**2)/80)+.2*np.exp(-((xx-55)**2+(yy-38)**2)/30)).astype(np.float32)
        image=np.repeat(gray[:,:,None],3,axis=2)
        circle=Circle(48,48,21)
        original=feature_bank(image,[circle])
        rotated=feature_bank(np.rot90(image).copy(),[circle])
        inverted=feature_bank(1-image,[circle])
        turn=pair_features(rotated,original)[0,0]
        inverse=pair_features(inverted,original)[0,0]
        self.assertEqual(len(turn),len(FEATURE_NAMES))
        self.assertGreater(turn[2],.995)
        self.assertGreater(turn[2],turn[0]+.03)
        self.assertLess(inverse[0],-.995)
        self.assertGreater(float(np.abs(original['local']-inverted['local']).max()),.2)
        self.assertEqual(original['local'].shape,(1,len(LOCAL_NAMES)))

    def test_training_and_calibration_seeds_are_independent_of_tests(self):
        train={seed for seeds in TRAIN_SEEDS.values() for seed in seeds}
        calibration=set(CALIBRATION_SEEDS.values())
        self.assertFalse(train & calibration)
        self.assertFalse((train | calibration) & FORBIDDEN_SEEDS)

    def test_empty_bank_has_defined_shapes(self):
        image=np.zeros((32,32,3),np.float32)
        bank=feature_bank(image,[])
        self.assertEqual(bank['gray'].shape,(0,1024))
        self.assertEqual(bank['local'].shape,(0,len(LOCAL_NAMES)))

    def test_fast_import_does_not_load_torch(self):
        program="import sys; sys.path.insert(0,'experiments/cell_detection'); import fast_model; assert 'torch' not in sys.modules"
        subprocess.run([sys.executable,'-c',program],check=True)

    def test_relative_features_are_exact_subset_with_no_absolute_blocks(self):
        yy,xx=np.mgrid[:64,:64]
        image=np.repeat((xx/63).astype(np.float32)[:,:,None],3,axis=2)
        candidates=feature_bank(image,[Circle(20,20,8),Circle(42,42,8)])
        examples=feature_bank(image,[Circle(30,30,8)])
        full=pair_features(candidates,examples)
        relative=pair_features(candidates,examples,'relative')
        np.testing.assert_array_equal(relative,full[:,:,RELATIVE_FEATURE_MASK])
        self.assertEqual(relative.shape,(2,1,43))
        self.assertEqual(len(RELATIVE_FEATURE_NAMES),43)
        self.assertFalse(any(n.startswith(('candidate_','example_')) for n in RELATIVE_FEATURE_NAMES))

    def test_changed_label_manifest_rejected_before_reused_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);prior=root/'prior';(prior/'evaluation').mkdir(parents=True)
            real=root/'real.json';structured=root/'structured.json'
            real.write_text(json.dumps({'scenes':[]}));structured.write_text(json.dumps({'scenes':[],'kind':'synthetic'}))
            old_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [real,structured]}
            (prior/'evaluation/report.json').write_text(json.dumps({'input_hashes':old_hashes}))
            real.write_text(json.dumps({'scenes':[],'coordinates_changed':True}))
            output=root/'new'
            result=subprocess.run([sys.executable,'experiments/cell_detection/fast_benchmark.py',
                                   '--real-labels',str(real),'--structured-labels',str(structured),
                                   '--reuse',str(prior),'--feature-mode','relative','--output',str(output)],
                                  capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('unchanged real and structured label manifests',result.stderr)
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
