"""Real-plus-synthetic updates, with synthetic-only validation and frozen prefix."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import time

import cv2
import numpy as np

from detector import Encoder
from hybrid_data import BalancedTriplets,build_real_crops,check_real_manifest,load_synthetic_records,plan_real_crops,sha256
from neural_model import adaptation_loss,batchnorm_buffers,changed_tensors,prefix_state,save_checkpoint,suffix_embeddings,tensor_hash,trainable_suffix
from neural_train import batch_embeddings,cache_prefix


CONFIG={'learning_rate':1e-4,'weight_decay':1e-4,'epochs':6,'steps_per_epoch':60,
        'batch_triplets':32,'margin':.2,'teacher_preservation':.1,'gradient_clip':5.,
        'threads':4,'seed':61001,'patience':2,'min_validation_improvement':1e-4,
        'first_trainable_block':10,'real_fit_augmentations':4,'maximum_crops':24000,
        'training_domain':'reviewed_real_plus_synthetic','checkpoint_selection':'separate_synthetic_validation',
        'sampling':'Half real/half synthetic per batch; cycle shuffled recordings and frames; selected checkpoint must have used every training frame.',
        'threshold_objective':'Predeclared F2 on separate synthetic calibration, misses cost four times extras.'}


def combine_cache(folder,synthetic_cache,synthetic_records,real_folder,real_records):
    """Copy validated fixed-layer arrays into new files, never changing a source."""
    records=copy.deepcopy(synthetic_records)
    for row in real_records:
        updated=dict(row,index=len(records));records.append(updated)
    for name in ('prefix.npy','teacher.npy'):
        a=np.load(synthetic_cache/name,mmap_mode='r');b=np.load(real_folder/name,mmap_mode='r')
        if len(a)!=len(synthetic_records) or len(b)!=len(real_records) or a.shape[1:]!=b.shape[1:]:
            raise ValueError('Prefix cache shapes do not match crop records.')
        out=np.lib.format.open_memmap(folder/name,mode='w+',dtype=np.float32,shape=(len(a)+len(b),*a.shape[1:]))
        out[:len(a)]=a;out[len(a):]=b;out.flush();del out
    (folder/'crop-index.json').write_text(json.dumps(records)+'\n')
    return records


def verify_original_cache(encoder,folder):
    """Recompute eight dispersed original crops before reusing fixed features."""
    crops=np.load(folder/'crops.npy',mmap_mode='r');cached=np.load(folder/'prefix.npy',mmap_mode='r')
    teacher=np.load(folder/'teacher.npy',mmap_mode='r');ids=np.linspace(0,len(crops)-1,8).astype(int)
    prefix,suffix=trainable_suffix(encoder)
    with encoder.torch.no_grad():
        actual=prefix(encoder.input_tensor(np.asarray(crops[ids],np.float32)/255))
        target=suffix_embeddings(suffix,actual).cpu().numpy()
    differences={'prefix_max_abs_difference':float(np.max(np.abs(actual.cpu().numpy()-cached[ids]))),
                 'teacher_max_abs_difference':float(np.max(np.abs(target-teacher[ids])))}
    if any(not np.isfinite(v) or v>1e-5 for v in differences.values()):
        raise ValueError('Synthetic cached features are incompatible with the original encoder/preprocessing.')
    return dict(differences,crop_indices=ids.tolist(),absolute_tolerance=1e-5,compatible=True)


def train_hybrid(encoder,records,folder,source_metadata,config=None):
    config=dict(CONFIG if config is None else config);t=encoder.torch
    t.manual_seed(config['seed']);rng=np.random.default_rng(config['seed']);_,suffix=trainable_suffix(encoder)
    before={name:value.detach().cpu().clone() for name,value in encoder.model.features.state_dict().items()}
    frozen=tensor_hash(prefix_state(encoder.model.features));bn=tensor_hash(batchnorm_buffers(encoder.model.features))
    prefix=np.load(folder/'prefix.npy',mmap_mode='r');teacher=np.load(folder/'teacher.npy',mmap_mode='r')
    fit=BalancedTriplets(records,'fit');validation=BalancedTriplets(records,'validation')
    fixed=validation.sample(np.random.default_rng(config['seed']+1),640);np.save(folder/'validation-triplets.npy',fixed)
    optimizer=t.optim.AdamW(suffix.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
    def val_loss():
        rows=[]
        with t.no_grad():
            for first in range(0,len(fixed),config['batch_triplets']):
                values,target,local=batch_embeddings(suffix,prefix,teacher,fixed[first:first+config['batch_triplets']])
                loss,_,_=adaptation_loss(values,target,local,config['margin'],config['teacher_preservation']);rows.append(float(loss))
        return float(np.mean(rows))
    initial=val_loss();history=[];best_loss=float('inf');best_epoch=None;best_state=None;stale=0;start=time.perf_counter()
    print('Initial separate synthetic validation',round(initial,6),flush=True)
    for epoch in range(1,config['epochs']+1):
        epoch_start=time.perf_counter();losses=[]
        for step in range(config['steps_per_epoch']):
            triplets=fit.sample(rng,config['batch_triplets']);optimizer.zero_grad(set_to_none=True)
            values,target,local=batch_embeddings(suffix,prefix,teacher,triplets)
            loss,ranking,preserve=adaptation_loss(values,target,local,config['margin'],config['teacher_preservation'])
            loss.backward();t.nn.utils.clip_grad_norm_(suffix.parameters(),config['gradient_clip']);optimizer.step()
            losses.append([float(loss.detach()),float(ranking.detach()),float(preserve.detach())])
            if (step+1)%20==0:print('Hybrid pass',epoch,'step',step+1,'/',config['steps_per_epoch'],flush=True)
        val=val_loss();eligible=fit.full_coverage();row={'epoch':epoch,'train_loss':float(np.mean(np.asarray(losses)[:,0])),
                           'ranking_loss':float(np.mean(np.asarray(losses)[:,1])),
                           'preservation_loss':float(np.mean(np.asarray(losses)[:,2])),
                           'validation_loss':val,'seconds':time.perf_counter()-epoch_start,
                           'checkpoint_eligible':eligible,'frame_update_coverage':fit.coverage()}
        history.append(row);print('Hybrid pass complete',json.dumps(row),flush=True)
        if eligible and val<best_loss-config['min_validation_improvement']:
            best_loss=val;best_epoch=epoch;best_state={n:v.detach().cpu().clone() for n,v in encoder.model.features.state_dict().items()};stale=0
        elif eligible:stale+=1
        (folder/'history.json').write_text(json.dumps(history,indent=2)+'\n')
        if eligible and stale>=config['patience']:break
    if best_state is None:raise RuntimeError('No checkpoint covered every training frame within the fixed compute budget.')
    encoder.model.features.load_state_dict(best_state);changes=changed_tensors(before,encoder.model.features.state_dict())
    metadata={'config':config,'best_epoch':best_epoch,'initial_validation_loss':initial,'best_validation_loss':best_loss,
              'history':history,'training_seconds':time.perf_counter()-start,
              'frozen_prefix_sha256':frozen,'batchnorm_buffers_sha256':bn,
              'frozen_prefix_unchanged':tensor_hash(prefix_state(encoder.model.features))==frozen,
              'batchnorm_buffers_unchanged':tensor_hash(batchnorm_buffers(encoder.model.features))==bn,
              'changed_tensor_l2_norms':changes,'changed_convolution_tensors':{n:v for n,v in changes.items() if before[n].ndim==4},
              'fit_groups':{domain:sorted(groups) for domain,groups in fit.domains.items()},
              'selected_checkpoint_frame_update_coverage':history[best_epoch-1]['frame_update_coverage'],
              'validation_groups':{domain:sorted(groups) for domain,groups in validation.domains.items()},
              'source':source_metadata,
              'note':'ImageNet initialization. Real training recordings and procedural fit scenes update weights; only separate synthetic validation selects them. Outer real evaluation images are never opened for fitting or choices.'}
    if not changes or not metadata['changed_convolution_tensors'] or not metadata['frozen_prefix_unchanged'] or not metadata['batchnorm_buffers_unchanged']:
        raise RuntimeError('Hybrid updates violated the convolution/frozen-layer contract.')
    save_checkpoint(folder/'encoder.pt',encoder,metadata)
    (folder/'training-report.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('synthetic-labels','synthetic-cache','real-labels','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--split-manifest',type=Path)
    args=parser.parse_args();real_manifest=json.loads(args.real_labels.read_text())
    split=json.loads(args.split_manifest.read_text()) if args.split_manifest else None
    real=check_real_manifest(real_manifest,split);old,old_source=load_synthetic_records(args.synthetic_labels,args.synthetic_cache)
    _,real_count=plan_real_crops(real,CONFIG['real_fit_augmentations'],CONFIG['seed'])
    if len(old)+real_count>CONFIG['maximum_crops']:raise ValueError('Planned combined crop bank exceeds the declared24k limit.')
    args.output.mkdir(parents=True,exist_ok=False);cv2.setNumThreads(CONFIG['threads'])
    (args.output/'config.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
    encoder=Encoder(CONFIG['threads']);compatibility=verify_original_cache(encoder,args.synthetic_cache)
    real_folder=args.output/'real-crops';real_folder.mkdir()
    rows=build_real_crops(real,real_folder,CONFIG['real_fit_augmentations'],CONFIG['seed'])
    cache=cache_prefix(encoder,real_folder,rows)
    records=combine_cache(args.output,args.synthetic_cache,old,real_folder,rows)
    source={'real_manifest_sha256':sha256(args.real_labels),'synthetic_manifest_sha256':sha256(args.synthetic_labels),
            'split_manifest_sha256':sha256(args.split_manifest) if args.split_manifest else sha256(args.real_labels),
            'synthetic_cache':dict(old_source,path=str(args.synthetic_cache.resolve())),
            'synthetic_cache_compatibility':compatibility,
            'real_cache':cache,'real_scene_hashes':{s['id']:s['sha256'] for s in real if s['partition']=='training'},
            'training_recordings':sorted({s['group'] for s in real if s['partition']=='training'}),
            'evaluation_recordings':sorted({s['group'] for s in real if s['partition']=='evaluation'}),
            'crop_counts':{domain:{'positive':sum(r['domain']==domain and r['split']=='fit' and r['label']==1 for r in records),
                                  'negative':sum(r['domain']==domain and r['split']=='fit' and r['label']==0 for r in records)} for domain in ('real','synthetic')},
            'combined_prefix_sha256':sha256(args.output/'prefix.npy'),'combined_teacher_sha256':sha256(args.output/'teacher.npy')}
    print('Hybrid bank',len(records),'crops',json.dumps(source['crop_counts']),flush=True)
    train_hybrid(encoder,records,args.output,source)


if __name__=='__main__':main()
