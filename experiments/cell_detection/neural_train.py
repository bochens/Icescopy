"""Synthetic-only suffix fine-tuning with an independent validation split.

Cache the frozen prefix once. Every triplet compares two different filled
objects and one labeled empty/background object from the same generated scene.
Neither real recordings nor calibration scenes supply neural gradients.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

from detector import Circle, Encoder, patches, propose, read_image, same_object
from neural_model import adaptation_loss, batchnorm_buffers, changed_tensors, prefix_state, save_checkpoint, suffix_embeddings, tensor_hash, trainable_suffix


CONFIG={'learning_rate':1e-4,'weight_decay':1e-4,'epochs':6,'steps_per_epoch':60,
        'batch_triplets':32,'margin':.2,'teacher_preservation':.1,'gradient_clip':5.,
        'threads':4,'seed':60930,'patience':2,'min_validation_improvement':1e-4,
        'first_trainable_block':10,'fit_augmentations':8,'validation_augmentations':2,
        'background_crops_per_scene':20,'maximum_crops':20000,'patch_size':96,
        'training_domain':'synthetic_only','checkpoint_selection':'separate_synthetic_validation'}


def check_manifest(manifest):
    scenes=manifest['scenes'];groups={}
    if len({s['id'] for s in scenes})!=len(scenes):raise ValueError('Scene IDs must be unique.')
    for scene in scenes:
        if (scene['split'] not in ('fit','validation','calibration') or not scene['complete_labels'] or
                not scene['recording'].startswith('neural-synthetic-') or
                scene['rendering'].get('pixels')!='Entirely procedural; no published or real recording pixels.'):
            raise ValueError('Neural fitting requires the procedural synthetic corpus with explicit labels and splits.')
        if scene['group'] in groups and groups[scene['group']]!=scene['split']:
            raise ValueError('One holder group cannot enter multiple splits.')
        groups[scene['group']]=scene['split']
        if not scene['targets'] or not scene['negatives']:raise ValueError('Every generated scene needs filled and empty objects.')
        radii=[t['radius'] for t in scene['targets']+scene['negatives']]
        if max(radii)-min(radii)>1e-6:raise ValueError('Each scene must use one supplied-example measurement radius.')
    return scenes


def augment(patch,rng):
    angle=float(rng.choice([0,90,180,270])+rng.uniform(-12,12))
    matrix=cv2.getRotationMatrix2D((47.5,47.5),angle,1.)
    result=cv2.warpAffine(patch,matrix,(96,96),borderMode=cv2.BORDER_REFLECT_101)
    if rng.random()<.6:result=cv2.GaussianBlur(result,(0,0),float(rng.uniform(.2,.8)))
    result=result*float(rng.uniform(.83,1.17))+float(rng.uniform(-.025,.025))
    return np.uint8(np.clip(result,0,1)*255)


def build_crop_bank(scenes,folder):
    rng=np.random.default_rng(CONFIG['seed']);plans=[];count=0
    for scene in scenes:
        if scene['split']=='calibration':continue
        source=Path(scene['source'])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=scene['sha256']:raise ValueError('Synthetic source changed.')
        image=read_image(source);radius=float(scene['targets'][0]['radius'])
        filled=[Circle(t['x'],t['y'],radius) for t in scene['targets']]
        empty=[Circle(t['x'],t['y'],radius) for t in scene['negatives']]
        backgrounds=[]
        for circle in propose(image,radius,limit=400):
            if not any(same_object(circle,c) for c in filled+empty+backgrounds):backgrounds.append(circle)
            if len(backgrounds)==CONFIG['background_crops_per_scene']:break
        objects=[(circle,1,t['slot'],'filled') for circle,t in zip(filled,scene['targets'])]
        objects += [(circle,0,t['slot'],'empty') for circle,t in zip(empty,scene['negatives'])]
        offset=max(t['slot'] for t in scene['targets']+scene['negatives'])+1
        objects += [(circle,0,offset+i,'background') for i,circle in enumerate(backgrounds)]
        variants=CONFIG['fit_augmentations'] if scene['split']=='fit' else CONFIG['validation_augmentations']
        plans.append((scene,objects,variants));count+=len(objects)*variants
    if count>CONFIG['maximum_crops']:raise ValueError('Planned crop count exceeds the fixed training limit.')
    values=np.lib.format.open_memmap(folder/'crops.npy',mode='w+',dtype=np.uint8,shape=(count,96,96,3))
    records=[];index=0
    for scene,objects,variants in plans:
        image=read_image(scene['source'])
        for circle,label,object_id,kind in objects:
            for variant in range(variants):
                jitter=Circle(circle.x+float(rng.normal(0,.08*circle.radius)),
                              circle.y+float(rng.normal(0,.08*circle.radius)),
                              circle.radius*float(rng.uniform(.94,1.06)))
                crop=patches(image,[jitter])[0]
                values[index]=augment(crop,rng)
                records.append({'index':index,'scene_id':scene['id'],'group':scene['group'],'split':scene['split'],
                                'label':label,'object_id':int(object_id),'kind':kind,'variant':variant,
                                'circle':asdict(jitter)})
                index+=1
        print('Crops',scene['id'],len(objects)*variants,flush=True)
    values.flush();del values
    (folder/'crop-index.json').write_text(json.dumps(records)+'\n')
    return records


def cache_prefix(encoder,folder,records):
    t=encoder.torch;prefix,suffix=trainable_suffix(encoder)
    crops=np.load(folder/'crops.npy',mmap_mode='r')
    with t.no_grad():shape=tuple(prefix(encoder.input_tensor(np.asarray(crops[:1],np.float32)/255)).shape[1:])
    prefix_values=np.lib.format.open_memmap(folder/'prefix.npy',mode='w+',dtype=np.float32,shape=(len(records),*shape))
    teacher=np.lib.format.open_memmap(folder/'teacher.npy',mode='w+',dtype=np.float32,shape=(len(records),576))
    start=time.perf_counter()
    with t.no_grad():
        for first in range(0,len(records),64):
            last=min(first+64,len(records))
            batch=encoder.input_tensor(np.asarray(crops[first:last],np.float32)/255)
            features=prefix(batch)
            prefix_values[first:last]=features.cpu().numpy()
            teacher[first:last]=suffix_embeddings(suffix,features).cpu().numpy()
            if first%2048==0:print('Cached frozen prefix',last,'/',len(records),flush=True)
    prefix_values.flush();teacher.flush();del prefix_values,teacher
    return {'seconds':time.perf_counter()-start,'crops':len(records),'prefix_shape':shape,
            'prefix_sha256':hashlib.sha256((folder/'prefix.npy').read_bytes()).hexdigest(),
            'teacher_sha256':hashlib.sha256((folder/'teacher.npy').read_bytes()).hexdigest()}


class Triplets:
    def __init__(self,records,split):
        grouped={}
        for row in records:
            if row['split']==split:grouped.setdefault(row['group'],[]).append(row)
        self.groups=[]
        for group,rows in sorted(grouped.items()):
            positive=[r for r in rows if r['label']==1];negative=[r['index'] for r in rows if r['label']==0]
            if len({r['object_id'] for r in positive})<2 or not negative:raise ValueError('A triplet group needs two filled objects and negatives.')
            self.groups.append((group,positive,negative))

    def sample(self,rng,count):
        rows=[]
        for _ in range(count):
            _,positive,negative=self.groups[int(rng.integers(len(self.groups)))]
            anchor=positive[int(rng.integers(len(positive)))]
            candidates=[r for r in positive if r['object_id']!=anchor['object_id']]
            other=candidates[int(rng.integers(len(candidates)))]
            rows.append([anchor['index'],other['index'],negative[int(rng.integers(len(negative)))]] )
        return np.asarray(rows,np.int64)


def batch_embeddings(suffix,all_prefix,all_teacher,triplets):
    import torch
    indices,inverse=np.unique(triplets,return_inverse=True)
    values=torch.from_numpy(np.asarray(all_prefix[indices]).copy())
    teacher=torch.from_numpy(np.asarray(all_teacher[indices]).copy())
    selected=torch.from_numpy(inverse.reshape(-1,3))
    return suffix_embeddings(suffix,values),teacher,selected


def train(encoder,records,folder,source_metadata):
    t=encoder.torch;t.manual_seed(CONFIG['seed']);rng=np.random.default_rng(CONFIG['seed'])
    _,suffix=trainable_suffix(encoder)
    before={name:value.detach().cpu().clone() for name,value in encoder.model.features.state_dict().items()}
    prefix_hash=tensor_hash(prefix_state(encoder.model.features));bn_hash=tensor_hash(batchnorm_buffers(encoder.model.features))
    prefix=np.load(folder/'prefix.npy',mmap_mode='r');teacher=np.load(folder/'teacher.npy',mmap_mode='r')
    fit=Triplets(records,'fit');validation=Triplets(records,'validation')
    fixed_validation=validation.sample(np.random.default_rng(CONFIG['seed']+1),640)
    np.save(folder/'validation-triplets.npy',fixed_validation)
    optimizer=t.optim.AdamW(suffix.parameters(),lr=CONFIG['learning_rate'],weight_decay=CONFIG['weight_decay'])
    history=[];best_loss=float('inf');best_state=None;best_epoch=None;stale=0;start=time.perf_counter()
    def validation_loss():
        values=[]
        with t.no_grad():
            for first in range(0,len(fixed_validation),CONFIG['batch_triplets']):
                embeddings,target,local=batch_embeddings(suffix,prefix,teacher,fixed_validation[first:first+CONFIG['batch_triplets']])
                value,_,_=adaptation_loss(embeddings,target,local,CONFIG['margin'],CONFIG['teacher_preservation'])
                values.append(float(value))
        return float(np.mean(values))
    initial_validation_loss=validation_loss()
    print('Initial synthetic validation loss',round(initial_validation_loss,6),flush=True)
    for epoch in range(1,CONFIG['epochs']+1):
        losses=[];epoch_start=time.perf_counter()
        for step in range(CONFIG['steps_per_epoch']):
            triplets=fit.sample(rng,CONFIG['batch_triplets'])
            optimizer.zero_grad(set_to_none=True)
            embeddings,target,local=batch_embeddings(suffix,prefix,teacher,triplets)
            loss,ranking,preservation=adaptation_loss(embeddings,target,local,CONFIG['margin'],CONFIG['teacher_preservation'])
            loss.backward();t.nn.utils.clip_grad_norm_(suffix.parameters(),CONFIG['gradient_clip']);optimizer.step()
            losses.append([float(loss.detach()),float(ranking.detach()),float(preservation.detach())])
            if (step+1)%20==0:print('Epoch',epoch,'step',step+1,'/',CONFIG['steps_per_epoch'],'loss',round(float(loss.detach()),5),flush=True)
        val=validation_loss();row={'epoch':epoch,'train_loss':float(np.mean(np.asarray(losses)[:,0])),
                'ranking_loss':float(np.mean(np.asarray(losses)[:,1])),'preservation_loss':float(np.mean(np.asarray(losses)[:,2])),
                'validation_loss':val,'seconds':time.perf_counter()-epoch_start}
        history.append(row);print('Epoch complete',json.dumps(row),flush=True)
        if val<best_loss-CONFIG['min_validation_improvement']:
            best_loss=val;best_epoch=epoch;best_state={name:value.detach().cpu().clone() for name,value in encoder.model.features.state_dict().items()};stale=0
        else:stale+=1
        (folder/'history.json').write_text(json.dumps(history,indent=2)+'\n')
        if stale>=CONFIG['patience']:break
    encoder.model.features.load_state_dict(best_state)
    changes=changed_tensors(before,encoder.model.features.state_dict())
    metadata={'config':CONFIG,'best_epoch':best_epoch,'initial_validation_loss':initial_validation_loss,'best_validation_loss':best_loss,'history':history,
              'training_seconds':time.perf_counter()-start,'frozen_prefix_sha256':prefix_hash,'batchnorm_buffers_sha256':bn_hash,
              'frozen_prefix_unchanged':tensor_hash(prefix_state(encoder.model.features))==prefix_hash,
              'batchnorm_buffers_unchanged':tensor_hash(batchnorm_buffers(encoder.model.features))==bn_hash,
              'changed_tensor_l2_norms':changes,'changed_convolution_tensors':{n:v for n,v in changes.items() if before[n].ndim==4},
              'fit_groups':[g[0] for g in fit.groups],'validation_groups':[g[0] for g in validation.groups],
              'source':source_metadata,'note':'All gradients and checkpoint selection use generated images only. No real recording, including A, enters new fitting.'}
    if not metadata['changed_convolution_tensors'] or not metadata['frozen_prefix_unchanged'] or not metadata['batchnorm_buffers_unchanged']:
        raise RuntimeError('Neural update failed the convolution/frozen-layer contract.')
    save_checkpoint(folder/'encoder.pt',encoder,metadata)
    (folder/'training-report.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads(args.labels.read_text());scenes=check_manifest(manifest)
    args.output.mkdir(parents=True,exist_ok=False);cv2.setNumThreads(CONFIG['threads'])
    (args.output/'config.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
    records=build_crop_bank(scenes,args.output)
    counts={split:{'filled':sum(r['split']==split and r['label']==1 for r in records),
                   'empty_background':sum(r['split']==split and r['label']==0 for r in records)} for split in ('fit','validation')}
    print('Crop counts',json.dumps(counts),flush=True)
    encoder=Encoder(CONFIG['threads']);cache=cache_prefix(encoder,args.output,records)
    source={'manifest_path':str(args.labels.resolve()),'manifest_sha256':hashlib.sha256(args.labels.read_bytes()).hexdigest(),
            'scene_hashes':{s['id']:s['sha256'] for s in scenes},'counts':counts,'cache':cache}
    metadata=train(encoder,records,args.output,source)
    print('Selected epoch',metadata['best_epoch'],'validation loss',round(metadata['best_validation_loss'],5),flush=True)


if __name__=='__main__':main()
