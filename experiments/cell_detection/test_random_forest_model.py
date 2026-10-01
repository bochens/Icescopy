"""Portable forest, synchronized circle masks and single-frame contracts."""
import copy
import errno
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
import icescopy_droplet_detection as rf


def small_scene():
    image=np.full((96,160,3),35,np.uint8)
    circles=[rf.Circle(32,40,10),rf.Circle(80,40,10),rf.Circle(128,40,10)]
    for circle in circles:cv2.circle(image,(int(circle.x),int(circle.y)),10,(220,220,220),-1)
    return image,circles


class ForestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image,circles=small_scene()
        with patch.dict(rf.TRAINING,{'trees':8,'augmentation_tiles_per_image':4}):
            cls.model=rf.fit_model([{'image':image,'circles':circles}])

    def test_color_and_depth_paths(self):
        raw,circles=small_scene();raw[:,:,0]//=2
        np.testing.assert_array_equal(rf.preprocess_image(raw),rf.preprocess_image(raw[:,:,::-1],'BGR'))
        normalized=rf.preprocess_image(np.uint16(raw[:,:,1])*200)
        self.assertEqual(normalized.dtype,np.float32)
        np.testing.assert_array_equal(normalized[:,:,0],normalized[:,:,2])

    def test_boundary_padding_ignored_and_partial_interior_positive(self):
        valid=np.ones((64,64),bool);valid[:8]=False
        labels=rf.training_labels([rf.Circle(30,30,10),rf.Circle(2,52,8)],valid)
        self.assertEqual(labels[15,15],1)
        self.assertEqual(labels[15,20],-1)
        self.assertEqual(labels[0,20],-1)
        self.assertEqual(labels[26,1],1)
        self.assertEqual(labels[20,28],0)

    def test_affine_augmentation_keeps_isotropic_geometry(self):
        raw,circles=small_scene();image=rf.preprocess_image(raw)
        tile,valid,transformed,radius,matrix=rf._augment(image,circles,circles[1],np.random.default_rng(41))
        linear=matrix[:,:2];gram=linear@linear.T
        np.testing.assert_allclose(gram,np.eye(2)*gram[0,0],atol=1e-6)
        for original,changed in zip(circles,transformed):
            np.testing.assert_allclose([changed.x,changed.y],matrix@[original.x,original.y,1],atol=1e-5)
            self.assertAlmostEqual(changed.radius,radius,places=5)
        labels=rf.training_labels(transformed,valid)
        self.assertTrue((labels[~valid[::2,::2]]==-1).all())

    def test_portable_scores_match_real_sklearn_forest(self):
        from sklearn.ensemble import RandomForestClassifier
        rng=np.random.default_rng(8);x=rng.normal(size=(400,len(rf.FEATURE_NAMES))).astype(np.float32)
        y=(x[:,0]+x[:,5]>0).astype(int)
        classifier=RandomForestClassifier(n_estimators=7,max_depth=5,random_state=5).fit(x,y)
        model=copy.deepcopy(self.model);model['trees']=rf._export_trees(classifier)
        actual=rf.RandomForestDetector(model).predict_scores(x)
        np.testing.assert_allclose(actual,classifier.predict_proba(x)[:,1],atol=1e-7)

    def test_safe_json_roundtrip_no_overwrite_and_removable_drive(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'small.icescopy-model.json'
            with patch.object(rf.os,'link',side_effect=OSError(errno.ENOTSUP,'unsupported')):
                rf.save_model(self.model,path)
            self.assertEqual(rf.load_model(path),self.model)
            original=path.read_bytes()
            with self.assertRaises(FileExistsError):rf.save_model(self.model,path)
            self.assertEqual(path.read_bytes(),original)
            with patch.object(rf.os,'link',side_effect=FileExistsError(errno.EEXIST,'exists')):
                with self.assertRaises(FileExistsError):rf.save_model(self.model,Path(directory)/'racing.json')

    def test_invalid_numeric_and_cyclic_trees_rejected(self):
        for change in ('nan','cycle','feature'):
            model=copy.deepcopy(self.model);tree=model['trees'][0]
            if change=='nan':tree['probability'][0]=float('nan')
            elif change=='cycle':tree['left'][0]=0
            else:tree['feature'][0]=len(rf.FEATURE_NAMES)+1
            with self.assertRaises(ValueError):rf.validate_model(model)

    def test_dense_detection_and_protection(self):
        image,circles=small_scene();detector=rf.RandomForestDetector(self.model)
        result=detector.predict(image,examples=[circles[0]])
        self.assertEqual(len(result),2)
        self.assertTrue(all(min(np.hypot(row['circle']['x']-c.x,row['circle']['y']-c.y) for c in circles[1:])<3 for row in result))
        self.assertEqual(detector.predict(image,examples=[circles[0]],protected=circles),[])
        with self.assertRaises(rf.CancelledError):detector.predict(image,cancelled=lambda:True)

    def test_hard_mining_covers_each_region_without_positive_or_padding(self):
        features=np.zeros((32,32,len(rf.FEATURE_NAMES)),np.float32)
        features[:,:,0]=np.arange(1024).reshape(32,32)
        labels=np.zeros((32,32),np.int8);labels[:3]=-1;labels[12:20,12:20]=1
        scores=np.zeros((32,32),np.float32)
        scores[4:9,4:9]=.8;scores[23:27,23:27]=.9
        scores[13:19,13:19]=1;scores[:3]=1
        image=np.zeros((64,64,3),np.float32)
        with patch.object(rf.cv2,'HoughCircles',return_value=None):
            samples,focus,stats=rf._hard_negative_regions(image,features,labels,scores,12,np.random.default_rng(3))
        indices=samples[:,0].astype(int)
        self.assertTrue((labels.ravel()[indices]==0).all())
        self.assertEqual(stats['false_positive_regions'],2)
        self.assertEqual(stats['false_positive_regions_sampled'],2)
        self.assertEqual(len(focus),2)
        self.assertTrue((indices//32<12).any() and (indices//32>20).any())
        self.assertIn(6*32+6,indices)  # Interior core, not just a bounding-box edge.

    def test_missing_training_extra_has_actionable_message(self):
        real_import=__import__
        def without_sklearn(name,*args,**kwargs):
            if name.startswith('sklearn'):raise ImportError('not installed')
            return real_import(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=without_sklearn):
            with self.assertRaisesRegex(RuntimeError,'Icescopy\[training\]'):rf.fit_model([])


if __name__=='__main__':unittest.main()
