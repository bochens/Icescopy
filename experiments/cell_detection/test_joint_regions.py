"""Annotation-level loss, center coverage and resume provenance contracts."""
import copy
import tempfile
from pathlib import Path
import unittest

import cv2
import numpy as np
import torch

from joint_data import targets_for, tile_bank
from joint_model import HALO, TILE, JointNetwork, save_joint
from joint_train import initialize_resume, reviewed_region_bce, select_validation_weights
from neural_model import prefix_state, tensor_hash


class ReviewedRegionTests(unittest.TestCase):
    def target(self, shape=(1,1,5,5)):
        return {'heat':torch.zeros(shape),'mask':torch.ones(shape),
                'reviewed_empty_regions':torch.zeros(shape,dtype=torch.uint8),
                'reviewed_invalid_points':torch.full((shape[0],1,2),-1)}

    def test_easy_pixels_do_not_dilute_a_false_peak(self):
        logits=torch.full((1,1,5,5),-12.);logits[0,0,2,2]=float(np.log(.4/.6));logits.requires_grad_()
        small=self.target();small['reviewed_empty_regions'][0,0,2,2]=1
        large=self.target();large['reviewed_empty_regions'][:]=1
        first,*_=reviewed_region_bce(logits,small);second,*_=reviewed_region_bce(logits,large)
        self.assertAlmostEqual(float(first.detach()),-np.log(.6),places=6)
        self.assertEqual(float(first.detach()),float(second.detach()))
        first_grad=torch.autograd.grad(first,logits,retain_graph=True)[0]
        second_grad=torch.autograd.grad(second,logits)[0]
        torch.testing.assert_close(first_grad,second_grad)
        self.assertAlmostEqual(float(second_grad[0,0,2,2]),.4,places=6)

    def test_empty_and_invalid_categories_keep_total_weight_one(self):
        logits=torch.full((1,1,5,5),float(np.log(.2/.8)))
        logits[0,0,2,2]=float(np.log(.4/.6));logits.requires_grad_()
        target=self.target();target['reviewed_empty_regions'][0,0,2,2]=1
        target['reviewed_invalid_points']=torch.tensor([[[1,1],[1,2],[1,3]]])
        loss,empty,invalid,ne,ni=reviewed_region_bce(logits,target)
        self.assertEqual((ne,ni),(1,3))
        self.assertAlmostEqual(float(loss.detach()),(-np.log(.6)-np.log(.8))/2,places=6)
        gradient=torch.autograd.grad(loss,logits)[0]
        self.assertAlmostEqual(float(gradient[0,0,2,2]),.4/2,places=6)
        self.assertAlmostEqual(float(gradient[0,0,1,1]),.2/6,places=6)

    def test_unknown_padding_and_true_gaussian_conflicts_are_not_punished(self):
        logits=torch.zeros((1,1,5,5),requires_grad=True);target=self.target()
        target['reviewed_empty_regions'][:]=1
        target['mask'][:]=0;target['mask'][0,0,2,2]=1
        target['heat'][0,0,2,2]=.3
        target['reviewed_invalid_points']=torch.tensor([[[2,2],[0,0],[-1,-1]]])
        loss,_,_,ne,ni=reviewed_region_bce(logits,target)
        self.assertEqual((ne,ni),(0,0));loss.backward()
        self.assertEqual(float(logits.grad.abs().sum()),0.)

    def test_overlapping_empty_annotations_are_preserved_individually(self):
        logits=torch.zeros((1,1,5,5));target=self.target()
        target['reviewed_empty_regions']=torch.ones((1,2,5,5),dtype=torch.uint8)
        _,_,_,ne,_=reviewed_region_bce(logits,target)
        self.assertEqual(ne,2)


class RegionCoverageTests(unittest.TestCase):
    def scene(self,source='unused'):
        return {'id':'region','group':'region','source':source,'domain':'real','split':'validation',
          'complete_labels':False,'targets':[{'id':0,'x':100.,'y':100.,'radius':16.},
            {'id':1,'x':148.,'y':100.,'radius':16.}],
          'negatives':[{'id':0,'x':300.,'y':100.,'radius':16.},
            {'id':1,'x':348.,'y':100.,'radius':16.}],'center_negatives':[]}

    def test_disk_edge_in_core_does_not_count_as_center_coverage(self):
        scene=self.scene();scene['targets']=[{'id':0,'x':192.,'y':192.,'radius':16.}]
        scene['negatives']=[{'id':0,'x':HALO-4.,'y':192.,'radius':16.}]
        target,_,_,ids=targets_for(scene,np.array([[1,0,0],[0,1,0]],np.float32),np.ones((TILE,TILE),bool))
        self.assertTrue(target['reviewed_empty_regions'].any())
        self.assertEqual(ids,[])

    def test_validation_covers_each_known_empty_center_or_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'image.png';cv2.imwrite(str(source),np.zeros((384,512,3),np.uint8))
            scene=self.scene(str(source));success=Path(tmp)/'success';success.mkdir()
            rows=tile_bank([scene],success,real_validation_count=4)
            self.assertEqual({p for r in rows for p in r['positive_ids']},{0,1})
            self.assertEqual({p for r in rows for p in r['old_negative_ids']},{0,1})
            failed=Path(tmp)/'failed';failed.mkdir()
            with self.assertRaisesRegex(RuntimeError,'reviewed empty center'):
                tile_bank([scene],failed,real_validation_count=1)


class ResumeProvenanceTests(unittest.TestCase):
    def test_initial_weights_win_and_reload_unchanged_when_validation_regresses(self):
        network=JointNetwork();initial={n:v.clone() for n,v in network.state_dict().items()}
        initial_hash=tensor_hash(initial)
        with torch.no_grad():network.confidence.bias.add_(1.)
        selected,loss,improved=select_validation_weights(network,initial,1.,1.1,6)
        self.assertEqual((selected,loss,improved),(0,1.,False))
        self.assertEqual(initial_hash,tensor_hash(network.state_dict()))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'selected.pt';save_joint(path,network,{'selected_pass':0})
            saved=torch.load(path,map_location='cpu',weights_only=True)
            self.assertEqual(initial_hash,tensor_hash(saved['state_dict']))
        with torch.no_grad():network.confidence.bias.add_(1.)
        trained_hash=tensor_hash(network.state_dict())
        self.assertEqual(select_validation_weights(network,initial,1.,.9,6),(6,.9,True))
        self.assertEqual(trained_hash,tensor_hash(network.state_dict()))

    def test_same_spatial_sources_and_parent_prefix_required_before_loading(self):
        torch.manual_seed(4);network=JointNetwork();base=copy.deepcopy(network)
        source={'spatial_split':True,'real_manifest_sha256':'a','synthetic_manifest_sha256':'b',
          'parent_encoder_sha256':'c','scene_hashes':{'fit':'d','val':'e'},
          'scene_groups':{'fit':'fit','val':'val'},'cached_scene_splits':{'fit':'fit','val':'validation'}}
        metadata={'source':source,'selected_pass':17,'frozen_prefix_sha256':tensor_hash(prefix_state(network.backbone)),
                  'config':{'supervision_version':2},'selected_actual_update_coverage':{'fit':{'updated_positives':2}}}
        with torch.no_grad():network.confidence.bias.add_(.25)
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint=Path(tmp)/'joint.pt';save_joint(checkpoint,network,metadata)
            loaded=initialize_resume(base,checkpoint,source)
            self.assertEqual(loaded['inherited_supervision_version'],2)
            torch.testing.assert_close(base.confidence.bias,network.confidence.bias)
            unchanged=tensor_hash(base.state_dict())
            wrong=dict(source,real_manifest_sha256='different')
            with self.assertRaisesRegex(ValueError,'same spatial'):
                initialize_resume(base,checkpoint,wrong)
            self.assertEqual(unchanged,tensor_hash(base.state_dict()))
            corrupted=copy.deepcopy(network)
            with torch.no_grad():next(corrupted.backbone[0].parameters()).add_(1.)
            bad=Path(tmp)/'bad.pt';save_joint(bad,corrupted,metadata)
            with self.assertRaisesRegex(ValueError,'prefix differs'):
                initialize_resume(base,bad,source)
            self.assertEqual(unchanged,tensor_hash(base.state_dict()))


if __name__=='__main__':unittest.main()
