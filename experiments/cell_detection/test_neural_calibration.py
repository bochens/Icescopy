"""Threshold ties, duplicate exclusion, and reassignment contract checks."""
import unittest

import numpy as np

from benchmark import evaluate
from detector import Circle
from neural_calibration import accepted_prefix_counts,exact_calibrate


class ExactCalibrationTests(unittest.TestCase):
    def test_prefix_counts_match_hungarian_with_ties_and_duplicate_circles(self):
        # The first circle can match either target; adding the second requires
        # the assignment to be reconsidered. A higher-scored nearby duplicate
        # is suppressed using the same sort order as ordinary evaluation.
        truth=[Circle(50,0,1),Circle(0,0,1),Circle(1.8,0,1)]
        circles=[Circle(.9,0,1),Circle(-.9,0,1),Circle(10,0,1),Circle(.95,0,1)]
        values=np.array([.9995,.9992,.9988,.9995])
        distance=np.linalg.norm(np.array([[c.x,c.y] for c in circles])[:,None,:]-
                                np.array([[c.x,c.y] for c in truth])[None,:,:],axis=2)
        item={'truth':truth,'circles':circles,'distance':distance,'scene':{'complete_labels':True}}
        events,remaining=accepted_prefix_counts(item,values,[0])
        self.assertEqual(remaining,2)
        for threshold in [.3,1.,*values,*np.nextafter(values,np.inf)]:
            actual=evaluate(item,values,[0],threshold)
            self.assertEqual(sum(tp for score,tp,_ in events if score>=threshold),actual['found'])
            self.assertEqual(sum(fp for score,_,fp in events if score>=threshold),actual['false_detections'])
        self.assertEqual(evaluate(item,values,[0],.9992)['found'],2)

    def test_exact_calibration_rejects_real_or_incomplete_labels(self):
        for recording,complete in [('A',True),('neural-synthetic-pcr',False)]:
            item={'scene':{'split':'calibration','recording':recording,'complete_labels':complete}}
            with self.assertRaisesRegex(ValueError,'synthetic calibration groups'):
                exact_calibrate([item],0,{})


if __name__=='__main__':unittest.main()
