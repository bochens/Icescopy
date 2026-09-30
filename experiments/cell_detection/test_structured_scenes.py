"""Check label integrity for simulated holders, independent of detector output."""
import unittest
import numpy as np

from structured_scenes import render


class StructuredSceneTests(unittest.TestCase):
    def test_tray_slots_partition_into_filled_and_empty(self):
        raw,filled,empty,meta=render('pcr',1103)
        self.assertEqual(raw.dtype,np.uint16)
        self.assertEqual(len(filled)+len(empty),96)
        self.assertEqual(len({p['slot'] for p in filled+empty}),96)
        self.assertEqual(sum(p['row']==1 for p in filled),12)
        self.assertEqual(sum(p['row']==3 for p in empty),12)
        self.assertFalse({p['slot'] for p in filled}&{p['slot'] for p in empty})

    def test_glare_variant_preserves_occupancy_and_has_no_mirrored_tray(self):
        _,a,b,_=render('pocket',4409)
        image,c,d,meta=render('pocket',4409,condition='glare')
        self.assertEqual([(v['slot'],v['state']) for v in a+b],[(v['slot'],v['state']) for v in c+d])
        self.assertTrue(any(v['row']==2 and v['column']==4 for v in c))
        self.assertLess(float(image[:8,:8].mean())/65535,.13)
        for v in c+d:
            self.assertTrue(0<v['x']<image.shape[1] and 0<v['y']<image.shape[0])
            self.assertLessEqual(v['radius'],min(v['ellipse_axes'])+1e-6)


if __name__=='__main__':unittest.main()
