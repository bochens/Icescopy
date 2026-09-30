"""Synthetic-only heads and calibration; real images enter evaluation only.

Compare the untouched original head, a newly fitted synthetic head on frozen
features, and the same fitting procedure on synthetically adapted features.
The matched frozen control distinguishes neural updates from new head fitting.
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
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

from benchmark import evaluate,example_trials,subset
from detector import Circle,Encoder,detect,pair_features,patch_descriptors,patches,preprocess_image,propose,read_image,scores,unit_rows
from neural_model import FIRST_TRAINABLE_BLOCK,FineTunedEncoder
from neural_train import check_manifest


TIMED_SCENES={'A-0','B-50','TAMU-A-0','pcr-glare'}


def comparison_banks(image,circles,frozen,adapted):
    """Identical crops/proposals; compute the unchanged prefix once per crop."""
    batch=patches(image,circles)
    gray,edges,profiles=patch_descriptors(batch)
    original_outputs=[];adapted_outputs=[];t=frozen.torch
    prefix=frozen.model.features[:FIRST_TRAINABLE_BLOCK]
    original_suffix=frozen.model.features[FIRST_TRAINABLE_BLOCK:]
    adapted_suffix=adapted.model.features[FIRST_TRAINABLE_BLOCK:]
    with t.inference_mode():
        for first in range(0,len(batch),64):
            features=prefix(frozen.input_tensor(batch[first:first+64]))
            original_outputs.append(frozen.model.avgpool(original_suffix(features)).flatten(1).numpy())
            adapted_outputs.append(adapted.model.avgpool(adapted_suffix(features)).flatten(1).numpy())
    shared={'gray':gray,'edges':edges,'profiles':profiles}
    return dict(shared,embedding=unit_rows(np.concatenate(original_outputs))),dict(shared,embedding=unit_rows(np.concatenate(adapted_outputs)))


def prepare(scene,frozen,adapted,folder):
    source=Path(scene['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=scene['sha256']:raise ValueError('Scene source changed: '+scene['id'])
    start=time.perf_counter();image=read_image(source)
    radius=float(scene['targets'][0]['radius'])
    truth=[Circle(float(t['x']),float(t['y']),radius) for t in scene['targets']]
    circles=propose(image,radius)
    banks=comparison_banks(image,circles,frozen,adapted)
    examples=comparison_banks(image,truth,frozen,adapted)
    elapsed=time.perf_counter()-start
    distance=np.linalg.norm(np.array([[c.x,c.y] for c in circles])[:,None,:]-
                            np.array([[c.x,c.y] for c in truth])[None,:,:],axis=2)
    preview=cv2.cvtColor(np.uint8(image*255),cv2.COLOR_RGB2BGR)
    scale=min(1.,1400/image.shape[1]);preview=cv2.resize(preview,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(folder/(scene['id']+'.jpg')),preview,[cv2.IMWRITE_JPEG_QUALITY,92])
    np.savez_compressed(folder/(scene['id']+'-features.npz'),
                        **{'candidate_'+k:v for k,v in banks[0].items()},
                        **{'example_'+k:v for k,v in examples[0].items()},
                        adapted_candidate_embedding=banks[1]['embedding'],adapted_example_embedding=examples[1]['embedding'],
                        circles=np.array([[c.x,c.y,c.radius] for c in circles]))
    print('Prepared',scene['id'],len(circles),'proposals;',round(elapsed,2),'s',flush=True)
    return {'scene':scene,'truth':truth,'circles':circles,'banks':banks,'examples':examples,
            'distance':distance,'seconds':elapsed,'preview_scale':scale}


def fit_synthetic_head(prepared,index,encoder_sha):
    """The existing five-measurement logistic objective, synthetic inputs only."""
    rows,labels=[],[]
    for item in prepared:
        scene=item['scene']
        if (scene['split']!='fit' or not scene['recording'].startswith('neural-synthetic-') or
                not scene['complete_labels'] or scene['rendering'].get('pixels')!='Entirely procedural; no published or real recording pixels.'):
            raise ValueError('Every new comparison-head training scene must be synthetic fit data.')
        n=len(item['truth']);ids=np.unique(np.linspace(0,n-1,min(16,n)).astype(int))
        pair=pair_features(item['banks'][index],subset(item['examples'][index],ids))
        nearest=item['distance'].min(axis=1);radius=item['truth'][0].radius
        allowed=(nearest<radius*.8)|(nearest>radius*2.)
        for j,seed in enumerate(ids):
            keep=allowed&(item['distance'][:,seed]>radius*1.2)
            rows.append(pair[keep,j]);labels.append((nearest[keep]<radius*.8).astype(float))
    x=np.concatenate(rows);y=np.concatenate(labels)
    mean=x.mean(axis=0);scale=np.maximum(x.std(axis=0),1e-6);x=(x-mean)/scale
    weights=np.where(y==1,.5/max(1,y.sum()),.5/max(1,(1-y).sum()))
    def objective(w):
        logits=x@w[:-1]+w[-1];p=1/(1+np.exp(-np.clip(logits,-30,30)))
        loss=np.sum(weights*(np.logaddexp(0,logits)-y*logits))+.003*np.dot(w[:-1],w[:-1])
        error=weights*(p-y)
        return loss,np.r_[x.T@error+.006*w[:-1],error.sum()]
    with threadpool_limits(limits=4):
        fitted=minimize(objective,np.zeros(x.shape[1]+1),jac=True,method='L-BFGS-B',options={'maxiter':150})
    if not fitted.success:raise RuntimeError('Synthetic comparison head failed to converge: '+fitted.message)
    return {'mean':mean.tolist(),'scale':scale.tolist(),'weights':fitted.x[:-1].tolist(),'bias':float(fitted.x[-1]),
            'training_pairs':len(y),'positive_pairs':int(y.sum()),'negative_pairs':int((1-y).sum()),
            'training_domain':'synthetic_only','training_groups':sorted({p['scene']['group'] for p in prepared}),
            'scene_hashes':{p['scene']['id']:p['scene']['sha256'] for p in prepared},'encoder_sha256':encoder_sha,
            'features':['gray_correlation','edge_correlation','mean_profile_difference','max_profile_difference','neural_similarity'],
            'note':'Same five-feature logistic objective and regularization for matched frozen and adapted encoders; no real image, including recording A, enters this new fitting.'}


def calibrate(prepared,index,head):
    cached=[]
    for item in prepared:
        if item['scene']['split']!='calibration' or not item['scene']['recording'].startswith('neural-synthetic-'):
            raise ValueError('Threshold calibration requires separate synthetic calibration groups.')
        for ids in example_trials(len(item['truth'])):
            cached.append((item,ids,scores(item['banks'][index],subset(item['examples'][index],ids),'learned',head)))
    choices=[]
    for threshold in np.linspace(.3,.999,100):
        tp=fp=remaining=0
        for item,ids,value in cached:
            r=evaluate(item,value,ids,threshold);tp+=r['found'];fp+=r['false_detections'];remaining+=r['remaining']
        precision=tp/max(1,tp+fp);recall=tp/max(1,remaining)
        choices.append((precision>=.99,recall if precision>=.99 else precision,recall,float(threshold),precision,tp,fp,remaining))
    best=max(choices);by_family={}
    for item,ids,value in cached:
        family=item['scene']['rendering']['family'];totals=by_family.setdefault(family,{'found':0,'false_detections':0,'remaining':0})
        r=evaluate(item,value,ids,best[3])
        for key in totals:totals[key]+=r[key]
    for totals in by_family.values():
        totals['precision']=totals['found']/max(1,totals['found']+totals['false_detections'])
        totals['recall']=totals['found']/max(1,totals['remaining'])
    result={'threshold':best[3],'precision':best[4],'recall':best[2],'found':best[5],'false_detections':best[6],
            'remaining':best[7],'groups':sorted({p['scene']['group'] for p in prepared}),'by_family':by_family,
            'selection':'Highest recall at aggregate precision >=99%, otherwise highest precision; separate generated calibration scenes only.'}
    head['threshold']=best[3];head['calibration']=result
    return result


def report_entries(prepared,heads,thresholds,frozen,adapted):
    report=[];indices={'original':0,'frozen_synthetic':0,'adapted_synthetic':1}
    for item in prepared:
        scene=item['scene'];entry={k:scene[k] for k in ['id','recording','split','width','height','label_status','complete_labels']}
        entry.update(seconds=item['seconds'],radius=item['truth'][0].radius,negatives=scene.get('negatives',[]),
                     proposal_reference_coverage=int((item['distance'].min(axis=0)<item['truth'][0].radius).sum()),
                     preview_scale=item['preview_scale'],truth=[asdict(c) for c in item['truth']],
                     proposals=[asdict(c) for c in item['circles']],results=[])
        trials=example_trials(len(item['truth']))
        if scene['id']=='TAMU-A-0' and [0,8] not in trials:trials.append([0,8])
        for method,index in indices.items():
            for ids in trials:
                values=scores(item['banks'][index],subset(item['examples'][index],ids),'learned',heads[method])
                r=evaluate(item,values,ids,thresholds[method]['threshold'])
                r.update(method=method,scores=np.round(values,5).tolist());entry['results'].append(r)
        if scene['id'] in TIMED_SCENES:
            raw=cv2.imread(scene['source'],cv2.IMREAD_UNCHANGED);timings=[]
            # Frozen control has the same full architecture as the original
            # baseline; measure it and the adapted version with one/two examples.
            for method,encoder in [('frozen_synthetic',frozen),('adapted_synthetic',adapted)]:
                for ids in ([0],[0,len(item['truth'])//2]):
                    selected=[item['truth'][i] for i in ids]
                    start=time.perf_counter();image=preprocess_image(raw,'BGR')
                    additions=detect(image,selected,method='learned',threshold=thresholds[method]['threshold'],encoder=encoder,head=heads[method])
                    timings.append({'method':method,'seeds':ids,'seconds':time.perf_counter()-start,'suggestions':len(additions),
                                    'includes':'Current-frame normalization, proposals, known-cell exclusion, candidate and supplied-example crops, full CPU encoder, pair head, duplicate exclusion; excludes image/model file loading.'})
            entry['single_frame_timings']=timings
        report.append(entry)
        for method in indices:
            rows=[r for r in entry['results'] if r['method']==method and len(r['seeds'])==2]
            print(scene['id'],method,'2 examples: found',round(float(np.mean([r['found'] for r in rows])),2),
                  'missed',round(float(np.mean([r['missed'] for r in rows])),2),
                  'unmatched',round(float(np.mean([r['unmatched_suggestions'] for r in rows])),2),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic-labels',type=Path,required=True)
    parser.add_argument('--real-labels',type=Path,required=True)
    parser.add_argument('--structured-labels',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--baseline-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();synthetic=check_manifest(json.loads(args.synthetic_labels.read_text()))
    baseline=json.loads(args.baseline_report.read_text())
    args.output.mkdir(parents=True,exist_ok=False);cv2.setNumThreads(4)
    start=time.perf_counter();frozen=Encoder(4);adapted=FineTunedEncoder(args.checkpoint,4);load_seconds=time.perf_counter()-start
    checkpoint_sha=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    if adapted.checkpoint_metadata['source']['manifest_sha256']!=hashlib.sha256(args.synthetic_labels.read_bytes()).hexdigest():
        raise ValueError('Comparison corpus differs from neural gradient/validation corpus.')
    fitting=args.output/'fitting';fitting.mkdir();evaluation=args.output/'evaluation';evaluation.mkdir()
    fit_items=[prepare(s,frozen,adapted,fitting) for s in synthetic if s['split']=='fit']
    control=fit_synthetic_head(fit_items,0,None);new=fit_synthetic_head(fit_items,1,checkpoint_sha)
    cal_items=[prepare(s,frozen,adapted,fitting) for s in synthetic if s['split']=='calibration']
    thresholds={'original':baseline['thresholds']['learned'],
                'frozen_synthetic':calibrate(cal_items,0,control),'adapted_synthetic':calibrate(cal_items,1,new)}
    heads={'original':baseline['model'],'frozen_synthetic':control,'adapted_synthetic':new}
    for name,head in [('frozen-synthetic-head.json',control),('adapted-synthetic-head.json',new)]:
        (args.output/name).write_text(json.dumps(head,indent=2)+'\n')
    (args.output/'calibration.json').write_text(json.dumps(thresholds,indent=2)+'\n')
    print('Synthetic-only heads and thresholds frozen',json.dumps({k:v['threshold'] for k,v in thresholds.items()}),flush=True)
    # Real files are first opened after every new fitting/selection/calibration
    # operation is finished. The original baseline retains its prior A-trained head.
    real=json.loads(args.real_labels.read_text())['scenes'];structured=json.loads(args.structured_labels.read_text())['scenes']
    if len({s['id'] for s in real+structured})!=len(real+structured):raise ValueError('Duplicate evaluation scene IDs.')
    test=[prepare(dict(s,split='exploratory_real_evaluation') if s in real else s,frozen,adapted,evaluation)
          for s in real+structured]
    report={'thresholds':thresholds,'models':heads,'encoder_checkpoint_sha256':checkpoint_sha,
            'model_load_seconds':load_seconds,'training':adapted.checkpoint_metadata,
            'input_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            [args.synthetic_labels,args.real_labels,args.structured_labels,args.baseline_report]},
            'scenes':report_entries(test,heads,thresholds,frozen,adapted),
            'limitations':['All new neural gradients, comparison heads, checkpoint selection and threshold calibration use generated data only.',
                           'Original is the preserved ImageNet encoder plus prior real-A-trained head/threshold; recording A is not an untouched baseline test.',
                           'Frozen_synthetic and adapted_synthetic use identical new head-fitting and threshold-calibration procedures, groups, crops and candidate proposals.',
                           'Every real result is exploratory. Incomplete IS/PKU annotations do not support precision or claims that unmatched circles are empty.',
                           'Procedural optics are approximations; useful synthetic results do not establish real liquid occupancy accuracy.',
                           'Preparation shares the frozen prefix and computes features for both encoders and every reference circle; it is not single-frame call timing.',
                           'Actual full-inference timings are measured on A-0, B-50, TAMU-A-0 and pcr-glare with one/two examples, including current-frame normalization.',
                           'No video tracking, motion inference, automatic keyframes, application integration or freezing-algorithm changes.']}
    (evaluation/'report.json').write_text(json.dumps(report)+'\n');print('Report',evaluation/'report.json',flush=True)


if __name__=='__main__':main()
