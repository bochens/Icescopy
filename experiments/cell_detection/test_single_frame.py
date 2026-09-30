"""Current-frame and ID contracts; accuracy belongs in the image benchmark."""
import copy
from dataclasses import asdict
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import detector
from detector import Circle, preprocess_image, read_image
from single_frame import detect_current_frame, validate_state


def small_frame():
    raw=np.full((144,208,3),45,np.uint8)
    circles=[Circle(40,44,10),Circle(104,44,10),Circle(166,100,10)]
    for c in circles:
        cv2.circle(raw,(int(c.x),int(c.y)),14,(130,130,130),-1)
        cv2.circle(raw,(int(c.x),int(c.y)),10,(215,215,215),-1)
        cv2.circle(raw,(int(c.x-3),int(c.y-3)),3,(170,170,170),-1)
    return raw,circles


class SingleFrameTests(unittest.TestCase):
    def test_file_and_rgb_bgr_arrays_use_same_scaling(self):
        raw,_=small_frame()
        raw[:,:,0]//=2
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'frame.png'
            cv2.imwrite(str(path),raw[:,:,::-1])
            np.testing.assert_array_equal(read_image(path),preprocess_image(raw,'RGB'))
        np.testing.assert_array_equal(preprocess_image(raw,'RGB'),preprocess_image(raw[:,:,::-1],'BGR'))
        gray=np.uint16(raw[:,:,1])*200
        normalized=preprocess_image(gray)
        self.assertEqual(normalized.dtype,np.float32)
        np.testing.assert_array_equal(normalized[:,:,0],normalized[:,:,2])
        for bad in [np.zeros((0,10),np.uint8),np.full((10,10),np.nan,np.float32),np.zeros((10,10),bool)]:
            with self.assertRaises(ValueError):preprocess_image(bad)

    def test_real_small_scene_repeated_and_brightness_changed_frame(self):
        raw,circles=small_frame()
        first=detect_current_frame(raw,[circles[0]],threshold=.80)
        self.assertGreaterEqual(len(first['suggestions']),1)
        state=copy.deepcopy(first['state'])
        second=detect_current_frame(raw,example_ids=first['example_ids'],state=state,threshold=.80)
        self.assertEqual(second['suggestions'],[])
        self.assertEqual(second['state'],state)
        changed=np.uint8(raw.astype(np.float32)*.65+25)
        third=detect_current_frame(changed,example_ids=first['example_ids'],state=state,threshold=.80)
        self.assertEqual(third['suggestions'],[])
        self.assertEqual([c['id'] for c in third['state']['cells']],[c['id'] for c in state['cells']])
        self.assertEqual(state,first['state'])

    def test_complete_updated_positions_keep_ids_on_moved_frame(self):
        raw,circles=small_frame()
        state=detect_current_frame(raw,[circles[0]],existing=circles[1:],threshold=1)['state']
        positions=[{'id':row['id'],'circle':dict(row['circle'],x=row['circle']['x']+6)} for row in state['cells']]
        moved=cv2.warpAffine(raw,np.float32([[1,0,6],[0,1,0]]),(raw.shape[1],raw.shape[0]),borderValue=(45,45,45))
        result=detect_current_frame(moved,state=state,example_ids=[0],current_positions=positions,threshold=.8)
        self.assertEqual(result['suggestions'],[])
        self.assertEqual([c['id'] for c in result['state']['cells']],[c['id'] for c in state['cells']])
        self.assertEqual(result['state']['cells'][0]['circle']['x'],state['cells'][0]['circle']['x']+6)

    def test_existing_not_example_is_excluded_before_features(self):
        raw,circles=small_frame()
        seen=[]
        original=detector.feature_bank
        def record(image,bank,encoder=None):
            seen.extend(bank)
            return original(image,bank,encoder)
        with patch.object(detector,'feature_bank',side_effect=record):
            result=detect_current_frame(raw,[circles[0]],existing=[circles[1]],threshold=.8)
        self.assertFalse(any(detector.same_object(c,circles[1]) for c in seen))
        self.assertTrue(any(row['circle']==asdict(circles[1]) for row in result['state']['cells']))
        self.assertFalse(any(detector.same_object(Circle(**row['circle']),circles[1]) for row in result['suggestions']))

    def test_invalid_updates_and_detector_errors_do_not_modify_state(self):
        raw,circles=small_frame()
        state=detect_current_frame(raw,[circles[0]],existing=circles[1:],threshold=1)['state']
        before=copy.deepcopy(state)
        positions=[{'id':row['id'],'circle':dict(row['circle'],x=row['circle']['x']+1)} for row in state['cells']]
        for invalid in [positions[:-1],positions+[positions[0]],
                        [dict(row,id=row['id']+100) for row in positions]]:
            with self.assertRaises(ValueError):
                detect_current_frame(raw,state=state,example_ids=[0],current_positions=invalid)
            self.assertEqual(state,before)
        with self.assertRaisesRegex(ValueError,'changed frame size'):
            detect_current_frame(raw[:120,:],state=state,example_ids=[0])
        def broken(*args):raise RuntimeError('Intentional detector failure after validation')
        with self.assertRaises(RuntimeError):
            detect_current_frame(raw,state=state,example_ids=[0],current_positions=positions,detector=broken)
        self.assertEqual(state,before)

    def test_explicit_delete_never_reuses_id_and_bad_schema_rejected(self):
        raw,circles=small_frame()
        first=detect_current_frame(raw,[circles[0]],existing=circles[1:],threshold=1)
        removed=first['state']['cells'][0]['id']
        result=detect_current_frame(raw,[circles[1]],state=first['state'],remove_ids=[removed],threshold=1)
        self.assertGreaterEqual(max(c['id'] for c in result['state']['cells']),first['state']['next_id'])
        self.assertNotIn(removed,[c['id'] for c in result['state']['cells']])
        for alteration in [{'version':2},{'next_id':0},{'cells':[dict(first['state']['cells'][0],id=-1)]}]:
            with self.assertRaises(ValueError):validate_state(dict(first['state'],**alteration))

    def test_offscreen_known_cell_stays_known_but_cannot_be_example(self):
        raw,circles=small_frame()
        result=detect_current_frame(raw,[circles[0]],existing=[Circle(-10,70,10)],threshold=1)
        state=result['state']
        self.assertEqual(state['cells'][0]['id'],0)
        self.assertEqual(state['cells'][0]['circle']['x'],-10)
        again=detect_current_frame(raw,state=state,example_ids=result['example_ids'],threshold=1)
        self.assertEqual(again['state'],state)
        with self.assertRaisesRegex(ValueError,'inside the image'):
            detect_current_frame(raw,state=state,example_ids=[0])


if __name__=='__main__':unittest.main()
