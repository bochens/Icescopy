"""Recording separation, crop labels, sampling coverage and augmentation."""
import copy
import hashlib
import tempfile
from pathlib import Path
import unittest

import cv2
import numpy as np

from hybrid_data import BalancedTriplets,augment_training,build_real_crops,check_real_manifest,plan_real_crops


def scene(sid,group,partition):
    return {'id':sid,'group':group,'partition':partition,'source':'unused.png','sha256':sid,
            'width':96,'height':96,'targets':[{'id':i,'x':10+10*i,'y':30,'radius':3} for i in range(8)],
            'negatives':[{'id':i,'x':10+10*i,'y':70,'radius':3,'kind':'background'} for i in range(4)],
            'complete_labels':False,'origin':'test_picture','label_provenance':'Explicit contract fixture.'}


class HybridDataTests(unittest.TestCase):
    def test_recording_and_identical_image_cannot_cross_partition(self):
        a=scene('a','g1','training');b=scene('b','g2','evaluation')
        check_real_manifest({'scenes':[a,b]})
        for change in ({'group':'g1'},{'sha256':'a'},{'use_for_head_fit':True}):
            bad=dict(b,**change)
            with self.assertRaises(ValueError):check_real_manifest({'scenes':[a,bad]})
        with self.assertRaisesRegex(ValueError,'explicit reviewed negatives'):
            check_real_manifest({'scenes':[dict(a,negatives=[]),b]})

    def test_frame_index0_cycles_object_ids(self):
        frames=[]
        for i in range(8):
            s=scene('frame'+str(i),'recording','training');s['frame_index0']=i
            s['training_crop_plan']={'positive_count':2,'negative_count':1,'variants':1};frames.append(s)
        plans,count=plan_real_crops(frames,seed=1)
        positive=[{row['id'] for label,_,_,row in selected if label} for _,selected,_ in plans]
        self.assertEqual(count,24);self.assertNotEqual(positive[0],positive[1])
        self.assertEqual(set.union(*positive),set(range(8)))
        with self.assertRaisesRegex(ValueError,'frame_index0'):
            plan_real_crops([dict(frames[0],frame_index0=None)])

    def test_balanced_sampling_covers_frames_and_keeps_triplets_in_one_frame(self):
        records=[]
        for domain,groups in [('real',{'r0':9,'r1':1,'r2':1}),('synthetic',{'s0':1,'s1':1})]:
            for group,n in groups.items():
                for frame in range(n):
                    for object_id in range(6):
                        records.append({'index':len(records),'domain':domain,'group':group,'scene_id':f'{group}-{frame}',
                                        'split':'fit','label':int(object_id<4),'object_id':str(object_id)})
        sampler=BalancedTriplets(records,'fit');samples=sampler.sample(np.random.default_rng(20),96)
        domains=[];groups=[]
        for anchor,positive,negative in samples:
            a,p,n=[records[i] for i in (anchor,positive,negative)]
            self.assertEqual(a['scene_id'],p['scene_id']);self.assertEqual(a['scene_id'],n['scene_id'])
            self.assertNotEqual(a['object_id'],p['object_id']);self.assertEqual((a['label'],p['label'],n['label']),(1,1,0))
            domains.append(a['domain']);groups.append(a['group'])
        self.assertEqual(domains.count('real'),48);self.assertEqual(domains.count('synthetic'),48)
        self.assertEqual([groups.count(g) for g in ('r0','r1','r2')],[16,16,16]);self.assertTrue(sampler.full_coverage())

    def test_real_crop_builder_never_opens_evaluation_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);image=np.zeros((96,96,3),np.uint8)
            for i in range(8):cv2.circle(image,(10+10*i,30),3,(180,180,180),-1)
            source=root/'source.png';cv2.imwrite(str(source),image)
            a=scene('a','g1','training');a.update(source=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest())
            b=scene('b','g2','evaluation');b['source']=str(root/'absent-evaluation.png')
            rows=build_real_crops([a,b],root,variants=1)
            self.assertEqual(len(rows),12);self.assertTrue(all(r['scene_id']=='a' for r in rows))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),a['sha256'])

    def test_augmentation_retains_whole_marked_disk_and_varies_color(self):
        patch=np.zeros((96,96,3),np.float32);cv2.circle(patch,(48,48),21,(1,1,1),-1)
        rng=np.random.default_rng(42);changed=False
        for _ in range(30):
            result=augment_training(patch,rng);ys,xs=np.where(result.mean(axis=2)>140)
            self.assertGreater(len(xs),800);self.assertGreater(xs.min(),10);self.assertLess(xs.max(),86)
            self.assertGreater(ys.min(),10);self.assertLess(ys.max(),86)
            changed|=not np.array_equal(result[:,:,0],result[:,:,2])
        self.assertTrue(changed)


if __name__=='__main__':unittest.main()
