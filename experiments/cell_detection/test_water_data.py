"""Manual native-radius crop and actual-update coverage contracts."""
import json
import tempfile
from pathlib import Path
import unittest

import cv2
import numpy as np

from hybrid_data import augment_training,sha256
from water_data import WaterTriplets,build_manual_crops,check_manual_manifest


def manual_scene():
    return {'id':'water','group':'instrument','partition':'training','origin':'user_manually_labeled_recording',
            'complete_labels':False,'negative_review_complete':True,'width':128,'height':96,
            'targets':[{'id':0,'x':32,'y':32,'radius':3},{'id':1,'x':72,'y':32,'radius':6}],
            'negatives':[{'id':0,'x':104,'y':32,'radius':4}]}


class WaterDataTests(unittest.TestCase):
    def test_manual_native_radii_and_labels_survive_crop_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);picture=np.zeros((96,128,3),np.uint8)
            cv2.circle(picture,(32,32),3,(200,200,200),-1);cv2.circle(picture,(72,32),6,(200,200,200),-1)
            source=root/'source.png';cv2.imwrite(str(source),picture)
            scene=manual_scene();scene.update(source=str(source),sha256=sha256(source))
            check_manual_manifest({'scenes':[scene]});rows=build_manual_crops([scene],root,variants=2)
            self.assertEqual([r['source_circle']['radius'] for r in rows],[3,3,6,6,4,4])
            self.assertEqual([r['label'] for r in rows],[1,1,1,1,0,0])
            for row in rows:
                self.assertLessEqual(abs(row['circle']['radius']/row['source_circle']['radius']-1),.041)
            self.assertEqual(sha256(source),scene['sha256'])

    def test_partial_unmarked_areas_are_never_created_as_negatives(self):
        scene=manual_scene()
        with self.assertRaisesRegex(ValueError,'reviewed negatives'):
            check_manual_manifest({'scenes':[dict(scene,negatives=[])]})
        bad=dict(scene,origin='old_provisional_labels')
        with self.assertRaisesRegex(ValueError,'new user-labeled'):check_manual_manifest({'scenes':[bad]})
        with self.assertRaisesRegex(ValueError,'Overlapping'):
            check_manual_manifest({'scenes':[dict(scene,negatives=[{'id':0,'x':32,'y':32,'radius':4}])]})

    def test_cycled_positive_ids_need_successful_update_marking(self):
        records=[]
        for domain,group,n in [('real','large',160),('real','small',16),('synthetic','replay',10)]:
            for label,count in [(1,n),(0,3)]:
                for identity in range(count):
                    for variant in range(2):
                        records.append({'index':len(records),'domain':domain,'group':group,'scene_id':group,
                                        'split':'fit','label':label,'object_id':f'{label}:{identity}'})
        sampler=WaterTriplets(records,'fit');rng=np.random.default_rng(15)
        self.assertFalse(sampler.all_manual_updated())
        for _ in range(20):
            sampled=sampler.sample(rng,32)
            for a,p,n in sampled:
                self.assertNotEqual(records[a]['object_id'],records[p]['object_id'])
                self.assertEqual(records[a]['scene_id'],records[n]['scene_id'])
            sampler.mark_updated(sampled)
        self.assertTrue(sampler.all_manual_updated())
        self.assertEqual(sum(x['updated_objects'] for x in sampler.object_coverage()['real'].values()),176)

    def test_isotropic_augmentation_retains_circle_without_stretching(self):
        patch=np.zeros((96,96,3),np.float32);cv2.circle(patch,(48,48),21,(1,1,1),-1)
        rng=np.random.default_rng(30)
        for _ in range(30):
            result=augment_training(patch,rng);ys,xs=np.where(result.mean(axis=2)>140)
            self.assertGreater(xs.min(),10);self.assertLess(xs.max(),86)
            self.assertGreater(ys.min(),10);self.assertLess(ys.max(),86)
            ratio=(xs.max()-xs.min()+1)/(ys.max()-ys.min()+1)
            self.assertTrue(.90<ratio<1.10)


if __name__=='__main__':unittest.main()
