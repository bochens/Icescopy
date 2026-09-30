"""Compare example-guided methods without using evaluation labels for fitting."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment, minimize

from detector import Circle, Encoder, feature_bank, pair_features, propose, read_image, same_object, scores


def subset(bank, indices):
    return {key:value[indices] for key,value in bank.items()}


def prepare(scene, encoder, folder):
    source=Path(scene['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=scene['sha256']:
        raise ValueError('Input changed since labels were recorded.')
    start=time.perf_counter()
    image=read_image(source)
    radius=float(scene['targets'][0]['radius'])
    # The first example fixes measurement radius for this pilot. No grid, counts,
    # target locations or other recording frames enter candidate generation.
    truth=[Circle(float(t['x']),float(t['y']),radius) for t in scene['targets']]
    candidates=propose(image,radius)
    bank=feature_bank(image,candidates,encoder)
    examples=feature_bank(image,truth,encoder)
    elapsed=time.perf_counter()-start
    preview=cv2.cvtColor(np.uint8(image*255),cv2.COLOR_RGB2BGR)
    scale=min(1.,1400/image.shape[1])
    preview=cv2.resize(preview,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(folder/f"{scene['id']}.jpg"),preview,[cv2.IMWRITE_JPEG_QUALITY,92])
    np.savez_compressed(folder/f"{scene['id']}-features.npz",**{'candidate_'+k:v for k,v in bank.items()},
                        **{'example_'+k:v for k,v in examples.items()},
                        circles=np.array([[c.x,c.y,c.radius] for c in candidates]))
    distance=np.linalg.norm(np.array([[c.x,c.y] for c in candidates])[:,None,:]-
                            np.array([[c.x,c.y] for c in truth])[None,:,:],axis=2)
    print(scene['id'],len(candidates),'proposals; reference locations reached',int((distance.min(axis=0)<radius).sum()),
          '/',len(truth),'in',round(elapsed,2),'s',flush=True)
    return dict(scene=scene,truth=truth,circles=candidates,bank=bank,examples=examples,
                distance=distance,seconds=elapsed,preview_scale=scale)


def fit_head(prepared):
    rows,labels=[],[]
    for item in prepared:
        if item['scene']['split']!='development':
            continue
        if not item['scene'].get('complete_labels',True):
            raise ValueError('Training negatives require complete reviewed labels.')
        n=len(item['truth'])
        # Diverse training exemplars; examples themselves are excluded from pairs.
        ids=np.unique(np.linspace(0,n-1,min(16,n)).astype(int))
        pair=pair_features(item['bank'],subset(item['examples'],ids))
        nearest=item['distance'].min(axis=1)
        radius=item['truth'][0].radius
        allowed=(nearest<radius*.8)|(nearest>radius*2.)
        for j,seed in enumerate(ids):
            keep=allowed & (item['distance'][:,seed]>radius*1.2)
            rows.append(pair[keep,j,:]);labels.append((nearest[keep]<radius*.8).astype(float))
    if not rows:
        raise ValueError('No development recording supplied.')
    x=np.concatenate(rows);y=np.concatenate(labels)
    mean=x.mean(axis=0);scale=np.maximum(x.std(axis=0),1e-6);x=(x-mean)/scale
    weights=np.where(y==1,.5/max(1,y.sum()),.5/max(1,(1-y).sum()))
    def objective(w):
        logits=x@w[:-1]+w[-1]
        p=1/(1+np.exp(-np.clip(logits,-30,30)))
        loss=np.sum(weights*(np.logaddexp(0,logits)-y*logits))+.003*np.dot(w[:-1],w[:-1])
        error=weights*(p-y)
        gradient=np.r_[x.T@error+.006*w[:-1],error.sum()]
        return loss,gradient
    fitted=minimize(objective,np.zeros(x.shape[1]+1),jac=True,method='L-BFGS-B',options={'maxiter':150})
    if not fitted.success:
        raise RuntimeError('Classifier did not converge: '+fitted.message)
    return dict(mean=mean.tolist(),scale=scale.tolist(),weights=fitted.x[:-1].tolist(),bias=float(fitted.x[-1]),
                training_pairs=len(y),positive_pairs=int(y.sum()),negative_pairs=int((1-y).sum()),
                training_recordings=sorted({p['scene']['recording'] for p in prepared if p['scene']['split']=='development'}),
                features=['gray_correlation','edge_correlation','mean_profile_difference','max_profile_difference','neural_similarity'],
                note='Small learned classifier over fixed MobileNetV3-Small and image-matching features. Not a calibrated occupancy probability.')


def evaluate(item, values, seed_ids, threshold):
    truth=item['truth'];circles=item['circles'];seeds=[truth[i] for i in seed_ids]
    indices=[int(i) for i in np.argsort(-values) if values[i]>=threshold and not any(same_object(circles[i],s) for s in seeds)]
    kept=[]
    for i in indices:
        if not any(same_object(circles[i],circles[j]) for j in kept): kept.append(i)
    remaining=[i for i in range(len(truth)) if i not in seed_ids]
    matched=[]
    if kept and remaining:
        distance=item['distance'][np.ix_(kept,remaining)]
        valid=distance < truth[0].radius
        cost=np.where(valid,distance/truth[0].radius,10000.)
        rows,cols=linear_sum_assignment(cost)
        matched=[(kept[r],remaining[c],float(distance[r,c])) for r,c in zip(rows,cols) if valid[r,c]]
    tp=len(matched);unknown=len(kept)-tp
    complete=item['scene'].get('complete_labels',True)
    negatives=[Circle(float(c['x']),float(c['y']),float(c['radius']))
               for c in item['scene'].get('negatives',[])]
    matched_candidates={m[0] for m in matched}
    known_negative_count=sum(any(np.hypot(circles[i].x-n.x,circles[i].y-n.y)<n.radius
                                 for n in negatives) for i in kept if i not in matched_candidates)
    return dict(seeds=seed_ids,threshold=float(threshold),found=tp,remaining=len(remaining),
                missed=len(remaining)-tp,false_detections=unknown if complete else None,
                unmatched_suggestions=unknown,precision=tp/len(kept) if kept and complete else None,
                known_negative_detections=known_negative_count if negatives else None,
                recall=tp/len(remaining) if remaining else 1.,
                duplicate_existing=sum(any(same_object(circles[i],s) for s in seeds) for i in kept),
                mean_center_error_pixels=float(np.mean([m[2] for m in matched])) if matched else None,
                accepted=kept,missed_ids=[i for i in remaining if i not in {m[1] for m in matched}])


def example_trials(n):
    ids=np.unique(np.linspace(0,n-1,min(n,10)).astype(int)).tolist()
    return [[i] for i in ids]+[[ids[i],ids[(i+len(ids)//2)%len(ids)]] for i in range(len(ids)//2)]


def benchmark(prepared,head,fixed_thresholds=None):
    methods=['template','embedding','learned']
    # Choose one threshold per method on development recordings only, then freeze it.
    thresholds=dict(fixed_thresholds or {})
    for method in ([] if fixed_thresholds is not None else methods):
        choices=[]
        for threshold in np.linspace(.3,.99,70):
            tp=fp=remaining=0
            for item in prepared:
                if item['scene']['split']!='development':continue
                for ids in example_trials(len(item['truth']))[:4]:
                    value=scores(item['bank'],subset(item['examples'],ids),method,head)
                    result=evaluate(item,value,ids,threshold)
                    tp+=result['found'];fp+=result['false_detections'];remaining+=result['remaining']
            precision=tp/max(1,tp+fp);recall=tp/max(1,remaining)
            choices.append((precision>=.99, recall if precision>=.99 else precision,recall,float(threshold),precision))
        best=max(choices)
        thresholds[method]={'threshold':best[3],'development_precision':best[4],'development_recall':best[2]}
    reports=[]
    for item in prepared:
        scene=item['scene']
        entry={k:scene[k] for k in ['id','recording','split','width','height','label_status','complete_labels']}
        entry.update(seconds=item['seconds'],radius=item['truth'][0].radius,
                     negatives=scene.get('negatives',[]),
                     proposal_reference_coverage=int((item['distance'].min(axis=0)<item['truth'][0].radius).sum()),
                     preview_scale=item['preview_scale'],truth=[asdict(c) for c in item['truth']],
                     proposals=[asdict(c) for c in item['circles']],results=[])
        for method in methods:
            for ids in example_trials(len(item['truth'])):
                value=scores(item['bank'],subset(item['examples'],ids),method,head)
                result=evaluate(item,value,ids,thresholds[method]['threshold'])
                result.update(method=method,scores=np.round(value,5).tolist())
                entry['results'].append(result)
        reports.append(entry)
    return {'thresholds':thresholds,'scenes':reports}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reference-report',type=Path,
                        help='Evaluate with the model and thresholds of this report, without fitting anything')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    scenes=json.loads(args.labels.read_text())['scenes']
    cv2.setNumThreads(4)
    encoder=Encoder()
    prepared=[prepare(scene,encoder,args.output) for scene in scenes]
    reference=json.loads(args.reference_report.read_text()) if args.reference_report else None
    head=reference['model'] if reference is not None else fit_head(prepared)
    (args.output/'pair-model.json').write_text(json.dumps(head,indent=2)+'\n')
    print('Fixed classifier trained from' if reference else 'Trained pair classifier from',
          head['training_pairs'],'pairs on recording',head['training_recordings'],flush=True)
    report=benchmark(prepared,head,reference['thresholds'] if reference else None)
    report.update(model=head,label_file_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),
                  reference_report_sha256=hashlib.sha256(args.reference_report.read_bytes()).hexdigest() if reference else None,
                  limitations=['Read label_status for the origin and confirmation of each picture\'s labels.',
                               'With incomplete annotations, unmatched proposals are unknown unless explicitly labeled as negatives.',
                               'Training uses development recordings only; reference-report evaluation does not refit the model or thresholds.',
                               'Recordings inspected during algorithm development are exploratory evaluations, not blind tests.',
                               'Preparation time includes cached features for every reference circle, not only one or two examples.',
                               'No video tracking, session training feature or application integration.'])
    (args.output/'report.json').write_text(json.dumps(report)+'\n')
    for scene in report['scenes']:
        for method in ['template','embedding','learned']:
            for count in [1,2]:
                results=[r for r in scene['results'] if r['method']==method and len(r['seeds'])==count]
                print(scene['id'],method,count,'examples: mean found',round(np.mean([r['found'] for r in results]),1),
                      'mean missed',round(np.mean([r['missed'] for r in results]),1),
                      'mean unmatched',round(np.mean([r['unmatched_suggestions'] for r in results]),1),flush=True)


if __name__=='__main__':main()
