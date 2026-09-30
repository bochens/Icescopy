"""Descriptor and split contracts; do not claim image accuracy from unit tests."""
import subprocess
import sys
import unittest

import numpy as np

from detector import Circle
from fast_benchmark import CALIBRATION_SEEDS, FORBIDDEN_SEEDS, TRAIN_SEEDS
from fast_model import FEATURE_NAMES, LOCAL_NAMES, feature_bank, pair_features


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


if __name__=='__main__':unittest.main()
