"""Training-state and synthetic-label contracts, not real accuracy tests."""
import tempfile
from pathlib import Path
import unittest

import numpy as np

from detector import Circle,Encoder,patches,preprocess_image
from neural_model import FineTunedEncoder,adaptation_loss,batchnorm_buffers,changed_tensors,prefix_state,save_checkpoint,suffix_embeddings,tensor_hash,trainable_suffix
from neural_synthetic import FAMILIES,SEEDS,render,scene_style
from neural_train import Triplets
from structured_scenes import render as old_render


class NeuralSyntheticTests(unittest.TestCase):
    def test_styles_balanced_within_every_family_and_split(self):
        all_groups=set()
        for split in SEEDS:
            for family in FAMILIES:
                styles=[scene_style(split,family,i) for i in range(len(SEEDS[split][family]))]
                self.assertEqual(sum(mode=='transmitted' for mode,_ in styles),len(styles)//2)
                self.assertGreaterEqual(sum(neutral for _,neutral in styles),len(styles)//2)
                for seed in SEEDS[split][family]:
                    self.assertNotIn((family,seed),all_groups);all_groups.add((family,seed))

    def test_illumination_cannot_change_filled_empty_assignment(self):
        a,filled_a,empty_a,_=render('pocket',130100,optical_mode='transmitted',neutral=True)
        b,filled_b,empty_b,_=render('pocket',130100,optical_mode='reflected',neutral=False)
        self.assertEqual([(c['slot'],c['state']) for c in filled_a+empty_a],[(c['slot'],c['state']) for c in filled_b+empty_b])
        np.testing.assert_array_equal(a[:,:,0],a[:,:,2])
        radii={c['radius'] for c in filled_a+empty_a};self.assertEqual(len(radii),1)
        for c in filled_a+empty_a:
            self.assertLessEqual(c['radius'],min(c['ellipse_axes'])+1e-6)
            self.assertTrue(0<c['x']<a.shape[1] and 0<c['y']<a.shape[0])

    def test_triplets_use_same_scene_but_different_positive_objects(self):
        rows=[{'index':i,'group':f'g{g}','split':'fit','label':int(i%3!=2),'object_id':i%3}
              for g in range(2) for i in range(g*6,(g+1)*6)]
        sampled=Triplets(rows,'fit').sample(np.random.default_rng(10),100)
        for anchor,positive,negative in sampled:
            a,p,n=rows[anchor],rows[positive],rows[negative]
            self.assertEqual(a['group'],p['group']);self.assertEqual(a['group'],n['group'])
            self.assertNotEqual(a['object_id'],p['object_id'])
            self.assertEqual((a['label'],p['label'],n['label']),(1,1,0))


class NeuralWeightTests(unittest.TestCase):
    def test_actual_convolution_update_and_checkpoint_reload(self):
        raw,filled,empty,_=old_render('pcr',100099)
        image=preprocess_image(raw,'BGR')
        circles=[Circle(t['x'],t['y'],t['radius']) for t in [filled[0],filled[1],empty[0]]]
        batch=patches(image,circles)
        encoder=Encoder(4);t=encoder.torch
        prefix,suffix=trainable_suffix(encoder)
        before={n:v.detach().cpu().clone() for n,v in encoder.model.features.state_dict().items()}
        frozen=tensor_hash(prefix_state(encoder.model.features));bn=tensor_hash(batchnorm_buffers(encoder.model.features))
        with t.no_grad():
            cached=prefix(encoder.input_tensor(batch));teacher=suffix_embeddings(suffix,cached).detach()
        values=suffix_embeddings(suffix,cached);loss,_,_=adaptation_loss(values,teacher,t.tensor([[0,1,2]]))
        optimizer=t.optim.AdamW(suffix.parameters(),lr=1e-4)
        optimizer.zero_grad(set_to_none=True);loss.backward()
        gradient=sum(float(p.grad.norm()) for p in suffix.parameters() if p.ndim==4 and p.grad is not None)
        self.assertGreater(gradient,0);optimizer.step()
        changes=changed_tensors(before,encoder.model.features.state_dict())
        self.assertTrue(any(before[n].ndim==4 for n in changes))
        self.assertEqual(tensor_hash(prefix_state(encoder.model.features)),frozen)
        self.assertEqual(tensor_hash(batchnorm_buffers(encoder.model.features)),bn)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'encoder.pt'
            save_checkpoint(path,encoder,{'frozen_prefix_sha256':frozen,'batchnorm_buffers_sha256':bn,'training_domain':'synthetic_only'})
            restored=FineTunedEncoder(path,4)
            np.testing.assert_array_equal(encoder.encode(batch),restored.encode(batch))
            with self.assertRaisesRegex(ValueError,'already exists'):save_checkpoint(path,encoder,{})


if __name__=='__main__':unittest.main()
