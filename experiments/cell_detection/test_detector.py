"""Contract checks; image accuracy is measured separately by the benchmark."""
import unittest
import tempfile
from pathlib import Path

import cv2
import numpy as np

from detector import Circle, detect, exclude_existing, patches, read_image, same_object, validate_examples
from benchmark import evaluate


class DetectorContractTests(unittest.TestCase):
    def test_no_examples_is_explicit_error(self):
        with self.assertRaisesRegex(ValueError,'at least one'):
            detect(np.zeros((64,64,3),np.float32),[])

    def test_existing_circle_excluded_even_if_not_an_example(self):
        old=Circle(30,30,8)
        candidates=[Circle(30,30,15),Circle(33,30,8),Circle(49,30,8)]
        self.assertEqual(exclude_existing(candidates,[old]),[candidates[-1]])

    def test_touching_droplets_are_separate(self):
        self.assertFalse(same_object(Circle(20,20,10),Circle(40,20,10)))
        self.assertFalse(same_object(Circle(20,20,4),Circle(36,20,12)))

    def test_shifted_rim_does_not_create_second_circle_in_same_well(self):
        self.assertTrue(same_object(Circle(20,20,8),Circle(30,20,8)))

    def test_invalid_geometry_and_outside_examples(self):
        for radius in [0,-1,float('nan')]:
            with self.assertRaises(ValueError):Circle(0,0,radius)
        with self.assertRaises(ValueError):
            validate_examples(np.zeros((20,20,3)),[Circle(20,4,3)])

    def test_16bit_values_preserve_contrast(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'frame.png'
            a=np.tile(np.linspace(1000,50000,32,dtype=np.uint16),(32,1))
            cv2.imwrite(str(path),a)
            out=read_image(path)
            self.assertEqual(out.dtype,np.float32)
            self.assertGreater(float(out[:,25].mean()-out[:,5].mean()),.5)
            self.assertEqual(path.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')

    def test_edge_crop_does_not_wrap_far_side(self):
        image=np.zeros((64,64,3),np.float32);image[:,:20]=1
        patch=patches(image,[Circle(0,20,4)],size=24)[0]
        self.assertGreater(patch.mean(),.95)

    def test_seed_not_counted_and_duplicate_predictions_penalized(self):
        truth=[Circle(20,20,5),Circle(40,20,5)]
        circles=[truth[0],Circle(39,20,5),Circle(42,20,5),Circle(90,20,5)]
        distance=np.linalg.norm(np.array([[c.x,c.y] for c in circles])[:,None]-np.array([[c.x,c.y] for c in truth])[None],axis=2)
        item={'truth':truth,'circles':circles,'distance':distance,'scene':{'complete_labels':True}}
        result=evaluate(item,np.array([1,.95,.9,.85]),[0],.8)
        self.assertEqual(result['remaining'],1)
        self.assertEqual(result['found'],1)
        self.assertEqual(result['false_detections'],1)
        self.assertEqual(result['duplicate_existing'],0)
        item['scene']['complete_labels']=False
        result=evaluate(item,np.array([1,.95,.9,.85]),[0],.8)
        self.assertIsNone(result['false_detections'])
        self.assertIsNone(result['precision'])
        self.assertEqual(result['unmatched_suggestions'],1)
        self.assertIsNone(result['known_negative_detections'])
        item['scene']['negatives']=[{'x':90,'y':20,'radius':5}]
        result=evaluate(item,np.array([1,.95,.9,.85]),[0],.8)
        self.assertEqual(result['known_negative_detections'],1)
        self.assertIsNone(result['precision'])


if __name__=='__main__':unittest.main()
