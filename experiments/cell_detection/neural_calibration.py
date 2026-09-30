"""Exact synthetic threshold selection from saved, unrounded candidate scores."""
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from benchmark import evaluate,example_trials,subset
from detector import scores


OLD_THRESHOLDS=np.linspace(.3,.999,100)


def accepted_prefix_counts(item,values,seed_ids,minimum=.3):
    """Count matches at each distinct accepted score, with evaluator semantics.

    Greedy duplicate removal visits scores in descending order. Lower-scoring
    circles never affect earlier choices, so filtering its full accepted order
    gives exactly the same detections at every higher threshold. Equal scores
    enter together under the evaluator's >= comparison and unchanged sort order.
    Hungarian matching is recomputed for each distinct prefix: a new circle may
    change an earlier assignment, so counting only its nearest target is wrong.
    """
    accepted=evaluate(item,values,seed_ids,minimum)['accepted']
    ordered=np.asarray(values,dtype=float)[accepted]
    remaining=[i for i in range(len(item['truth'])) if i not in seed_ids]
    ends=np.r_[np.flatnonzero(np.diff(ordered))+1,len(ordered)] if len(ordered) else []
    events=[];last_tp=last_fp=0
    radius=item['truth'][0].radius
    for end in ends:
        distance=item['distance'][np.ix_(accepted[:end],remaining)]
        valid=distance<radius
        if distance.size:
            rows,cols=linear_sum_assignment(np.where(valid,distance/radius,10000.))
            tp=int(valid[rows,cols].sum())
        else:tp=0
        fp=int(end)-tp
        events.append((float(ordered[end-1]),tp-last_tp,fp-last_fp))
        last_tp,last_fp=tp,fp
    return events,len(remaining)


def selection_key(tp,fp,remaining,threshold):
    precision=tp/max(1,tp+fp);recall=tp/max(1,remaining)
    return (precision>=.99,recall if precision>=.99 else precision,recall,
            float(threshold),precision,int(tp),int(fp),int(remaining))


def exact_calibrate(prepared,index,head):
    """Highest recall at >=99% aggregate precision, using synthetic data only.

    Every distinct accepted score is a threshold event. The old 100 thresholds
    are retained, so the exact search cannot worsen its selection objective.
    This changes only numerical threshold resolution, not fitting or labels.
    """
    events=[];cached=[];remaining=0;families={};score_values=[]
    for item in prepared:
        scene=item['scene']
        if (scene['split']!='calibration' or not scene['recording'].startswith('neural-synthetic-') or
                not scene.get('complete_labels',False)):
            raise ValueError('Threshold calibration requires separate synthetic calibration groups with complete labels.')
        family=scene['rendering']['family'];families.setdefault(family,{'found':0,'false_detections':0,'remaining':0})
        for ids in example_trials(len(item['truth'])):
            values=scores(item['banks'][index],subset(item['examples'][index],ids),'learned',head)
            if not np.isfinite(values).all():raise ValueError('Calibration scores must be finite.')
            trial_events,n=accepted_prefix_counts(item,values,ids)
            events.extend((score,tp,fp,family) for score,tp,fp in trial_events)
            score_values.extend(score for score,_,_ in trial_events)
            remaining+=n;families[family]['remaining']+=n;cached.append((item,ids,values,trial_events,n))
    if not cached:raise ValueError('Calibration needs at least one synthetic scene.')
    thresholds=np.unique(np.r_[OLD_THRESHOLDS,score_values,1.])[::-1]
    events.sort(key=lambda row:row[0],reverse=True)
    tp=fp=position=0;choices=[];best=None;best_family=None
    for threshold in thresholds:
        while position<len(events) and events[position][0]>=threshold:
            _,dtp,dfp,family=events[position];tp+=dtp;fp+=dfp
            families[family]['found']+=dtp;families[family]['false_detections']+=dfp;position+=1
        choice=selection_key(tp,fp,remaining,threshold);choices.append(choice)
        if best is None or choice>best:
            best=choice;best_family={name:dict(counts) for name,counts in families.items()}
    old_best=max(choice for choice in choices if choice[3] in OLD_THRESHOLDS)
    # Verify against the unchanged evaluator at sampled old thresholds, the
    # selected thresholds, and score quantiles including boundaries near 1.
    probes=np.unique(np.r_[OLD_THRESHOLDS[[0,25,50,75,98,99]],best[3],old_best[3],1.,
                           np.quantile(score_values,np.linspace(0,1,9)) if score_values else []])
    by_scene={}
    for trial in cached:by_scene.setdefault(trial[0]['scene']['id'],[]).append(trial)
    verified=[trial for trials in by_scene.values() for trial in (trials[0],trials[-1])]
    for threshold in probes:
        for item,ids,values,trial_events,n in verified:
            result=evaluate(item,values,ids,threshold)
            actual=selection_key(result['found'],result['false_detections'],result['remaining'],threshold)
            expected=selection_key(sum(e[1] for e in trial_events if e[0]>=threshold),
                                   sum(e[2] for e in trial_events if e[0]>=threshold),n,threshold)
            if actual!=expected:
                raise AssertionError('Exact prefix calibration disagrees with the original evaluator.')
    if best<old_best:raise AssertionError('Refined calibration worsened the old-grid objective.')
    for counts in best_family.values():
        counts['precision']=counts['found']/max(1,counts['found']+counts['false_detections'])
        counts['recall']=counts['found']/max(1,counts['remaining'])
    result={'threshold':best[3],'precision':best[4],'recall':best[2],'found':best[5],
            'false_detections':best[6],'remaining':best[7],'by_family':best_family,
            'groups':sorted({p['scene']['group'] for p in prepared}),
            'selection':'Highest recall at aggregate precision >=99%, otherwise highest precision; separate generated calibration scenes only.',
            'search':{'method':'Exact accepted-score prefix sweep, >= comparison; all old thresholds retained.',
                      'threshold_count':len(thresholds),'accepted_score_events':len(events),
                      'accepted_score_quantiles':np.quantile(score_values,[0,.25,.5,.75,.9,.99,1]).tolist() if score_values else [],
                      'old_grid_best':{'threshold':old_best[3],'precision':old_best[4],'recall':old_best[2],
                                       'found':old_best[5],'false_detections':old_best[6]},
                      'evaluator_verified_thresholds':len(probes),'evaluator_verified_trials':len(verified),
                      'objective_no_worse_than_old_grid':True}}
    head['threshold']=best[3];head['calibration']=result
    return result
