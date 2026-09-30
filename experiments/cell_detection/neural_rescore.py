"""Refine synthetic calibration and reuse a completed neural comparison's banks.

Calibration can finish before the source evaluation job. Evaluation then uses
only its saved features, preserving encoder weights and both fitted heads.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
from threadpoolctl import threadpool_limits

from detector import Circle,detect,preprocess_image
from neural_calibration import exact_calibrate
from neural_compare import report_entries
from neural_model import FineTunedEncoder
from neural_train import check_manifest


def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cached(scene,folder):
    """Reconstruct unrounded candidate/example banks without reopening pixels."""
    path=folder/(scene['id']+'-features.npz')
    with np.load(path,allow_pickle=False) as saved:
        names=('gray','edges','profiles','embedding')
        bank={name:saved['candidate_'+name] for name in names}
        examples={name:saved['example_'+name] for name in names}
        adapted=dict(bank,embedding=saved['adapted_candidate_embedding'])
        adapted_examples=dict(examples,embedding=saved['adapted_example_embedding'])
        coordinates=saved['circles']
    if coordinates.ndim!=2 or coordinates.shape[1]!=3 or not np.isfinite(coordinates).all():
        raise ValueError('Invalid cached circle geometry: '+scene['id'])
    radius=float(scene['targets'][0]['radius'])
    if not np.allclose(coordinates[:,2],radius):raise ValueError('Cached proposal radius changed: '+scene['id'])
    circles=[Circle(*map(float,c)) for c in coordinates]
    truth=[Circle(float(t['x']),float(t['y']),radius) for t in scene['targets']]
    for data,n in [(bank,len(circles)),(adapted,len(circles)),(examples,len(truth)),(adapted_examples,len(truth))]:
        if any(len(v)!=n or not np.isfinite(v).all() for v in data.values()):
            raise ValueError('Incompatible cached feature bank: '+scene['id'])
    distance=np.linalg.norm(coordinates[:,:2,None].transpose(0,2,1)-
                            np.array([[c.x,c.y] for c in truth])[None,:,:],axis=2)
    return {'scene':scene,'circles':circles,'truth':truth,'banks':(bank,adapted),
            'examples':(examples,adapted_examples),'distance':distance,'seconds':0.,
            'preview_scale':min(1.,1400/scene['width']),'cache_sha256':sha256(path)}


def calibrate_saved(args):
    import torch
    if args.output.exists():raise ValueError('Refined output already exists; choose a fresh directory.')
    synthetic=check_manifest(json.loads(args.synthetic_labels.read_text()))
    fit=[s for s in synthetic if s['split']=='fit'];cal=[s for s in synthetic if s['split']=='calibration']
    checkpoint_sha=sha256(args.checkpoint)
    payload=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
    if payload['metadata']['source']['manifest_sha256']!=sha256(args.synthetic_labels):
        raise ValueError('Synthetic label manifest differs from the saved training checkpoint.')
    head_paths=[args.source/'frozen-synthetic-head.json',args.source/'adapted-synthetic-head.json']
    heads=[json.loads(path.read_text()) for path in head_paths]
    for head,expected_sha in zip(heads,[None,checkpoint_sha]):
        if (head['training_domain']!='synthetic_only' or head['encoder_sha256']!=expected_sha or
                head['training_groups']!=sorted({s['group'] for s in fit}) or
                head['scene_hashes']!={s['id']:s['sha256'] for s in fit}):
            raise ValueError('Saved head does not match the synthetic corpus or encoder checkpoint.')
    items=[load_cached(s,args.source/'fitting') for s in cal]
    old=json.loads((args.source/'calibration.json').read_text())
    start=time.perf_counter()
    thresholds={'original':old['original']}
    for index,method in enumerate(('frozen_synthetic','adapted_synthetic')):
        with threadpool_limits(limits=4):thresholds[method]=exact_calibrate(items,index,heads[index])
        previous=thresholds[method]['search']['old_grid_best']
        if any(not np.isclose(previous[k],old[method][k],rtol=0,atol=1e-12) for k in previous):
            raise ValueError('Cached old-grid calibration does not reproduce the source run.')
        print(method,'synthetic calibration',json.dumps({k:thresholds[method][k] for k in
              ('threshold','precision','recall','found','false_detections')}),flush=True)
    args.output.mkdir(parents=True,exist_ok=False)
    for name,head in zip(('frozen-synthetic-head.json','adapted-synthetic-head.json'),heads):
        (args.output/name).write_text(json.dumps(head,indent=2)+'\n')
    (args.output/'calibration.json').write_text(json.dumps(thresholds,indent=2)+'\n')
    metadata={'source':str(args.source.resolve()),'synthetic_labels':str(args.synthetic_labels.resolve()),
              'synthetic_manifest_sha256':sha256(args.synthetic_labels),'encoder_checkpoint_sha256':checkpoint_sha,
              'source_head_hashes':{p.name:sha256(p) for p in head_paths},
              'source_calibration_sha256':sha256(args.source/'calibration.json'),
              'calibration_cache_hashes':{p['scene']['id']:p['cache_sha256'] for p in items},
              'calibration_seconds':time.perf_counter()-start,
              'source_comparison_checkpoint':'81260ed',
              'correction':'Exact threshold resolution chosen from synthetic calibration only, before reading real evaluation results.',
              'source_hashes':{name:sha256(Path(__file__).with_name(name)) for name in
                               ('neural_calibration.py','neural_rescore.py','neural_compare.py')}}
    guard={name:sha256(args.output/name) for name in
           ('calibration.json','frozen-synthetic-head.json','adapted-synthetic-head.json')}
    (args.output/'refined-artifact-hashes.json').write_text(json.dumps(guard,indent=2)+'\n')
    (args.output/'rescore-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('Saved refined synthetic calibration;',round(metadata['calibration_seconds'],2),'s',flush=True)


def evaluate_saved(args):
    metadata=json.loads((args.output/'rescore-metadata.json').read_text())
    if ((args.output/'report.json').exists() or (args.output/'evaluation').exists()):
        raise ValueError('Refined evaluation output already exists.')
    if (metadata['source']!=str(args.source.resolve()) or
            metadata['synthetic_manifest_sha256']!=sha256(args.synthetic_labels) or
            metadata['encoder_checkpoint_sha256']!=sha256(args.checkpoint)):
        raise ValueError('Refined calibration inputs changed.')
    for name,value in metadata['source_head_hashes'].items():
        if sha256(args.source/name)!=value:raise ValueError('Source fitted head changed.')
    if sha256(args.source/'calibration.json')!=metadata['source_calibration_sha256']:
        raise ValueError('Source calibration changed.')
    guard=json.loads((args.output/'refined-artifact-hashes.json').read_text())
    for name,value in guard.items():
        if sha256(args.output/name)!=value:raise ValueError('Saved refined calibration or head changed.')
    # Thresholds are already saved and fixed before any real report is read.
    thresholds=json.loads((args.output/'calibration.json').read_text())
    source_report_path=args.source/'evaluation'/'report.json'
    source_report=json.loads(source_report_path.read_text())
    for path in [args.synthetic_labels,args.real_labels,args.structured_labels]:
        expected=[value for name,value in source_report['input_hashes'].items() if Path(name).resolve()==path.resolve()]
        if expected!=[sha256(path)]:raise ValueError('Label manifest differs from source cached run: '+str(path))
    if source_report['encoder_checkpoint_sha256']!=metadata['encoder_checkpoint_sha256']:
        raise ValueError('Source cached encoder changed.')
    real=json.loads(args.real_labels.read_text())['scenes'];structured=json.loads(args.structured_labels.read_text())['scenes']
    original={s['id']:s for s in source_report['scenes']}
    items=[]
    for scene in real+structured:
        if sha256(scene['source'])!=scene['sha256']:raise ValueError('Evaluation source changed: '+scene['id'])
        entry=dict(scene,split='exploratory_real_evaluation') if scene in real else scene
        item=load_cached(entry,args.source/'evaluation')
        item['seconds']=original[scene['id']]['seconds'];items.append(item)
    heads={'original':source_report['models']['original'],
           'frozen_synthetic':json.loads((args.output/'frozen-synthetic-head.json').read_text()),
           'adapted_synthetic':json.loads((args.output/'adapted-synthetic-head.json').read_text())}
    for method in ('frozen_synthetic','adapted_synthetic'):
        old=copy.deepcopy(source_report['models'][method]);new=copy.deepcopy(heads[method])
        for model in (old,new):
            model.pop('threshold',None);model.pop('calibration',None)
        if old!=new:raise ValueError('Cached rescoring may not change fitted head weights.')
    entries=report_entries(items,heads,thresholds,None,None,timed_scenes=())
    for entry in entries:
        baseline=[r for r in original[entry['id']]['results'] if r['method']=='original']
        current=[r for r in entry['results'] if r['method']=='original']
        if baseline!=current:raise AssertionError('Cached original-baseline results changed.')
    # Only two final adapted calls are needed: no new crop or encoder preparation.
    load_start=time.perf_counter();encoder=FineTunedEncoder(args.checkpoint,4)
    model_load_seconds=time.perf_counter()-load_start;cv2.setNumThreads(4)
    timings=[]
    for item in items:
        scene=item['scene']
        if scene['id'] not in ('A-0','TAMU-A-0'):continue
        ids=[0,8] if scene['id']=='TAMU-A-0' else [0,len(item['truth'])//2]
        raw=cv2.imread(scene['source'],cv2.IMREAD_UNCHANGED)
        start=time.perf_counter();image=preprocess_image(raw,'BGR')
        additions=detect(image,[item['truth'][i] for i in ids],method='learned',
                         threshold=thresholds['adapted_synthetic']['threshold'],encoder=encoder,head=heads['adapted_synthetic'])
        timing={'scene':scene['id'],'method':'adapted_synthetic','seeds':ids,
                'seconds':time.perf_counter()-start,'suggestions':len(additions),
                'includes':'Current-frame normalization, proposals, protected-cell exclusion, crops, full CPU encoder, head, duplicate exclusion; image/model file loading excluded.'}
        timings.append(timing);print('Final adapted current-frame timing',scene['id'],round(timing['seconds'],2),'s',flush=True)
    report=copy.deepcopy(source_report)
    report.update(thresholds=thresholds,models=heads,scenes=entries,model_load_seconds=model_load_seconds,
                  single_frame_timings=timings,cached_rescoring=dict(metadata,source_report_sha256=sha256(source_report_path),
                  evaluation_cache_hashes={p['scene']['id']:p['cache_sha256'] for p in items},
                  evaluation_source_hashes={name:sha256(Path(__file__).with_name(name)) for name in
                                           ('neural_calibration.py','neural_rescore.py','neural_compare.py')},
                  original_baseline_exact_agreement=True))
    report['limitations']=[line for line in report['limitations'] if not line.startswith('Actual full-inference timings')]
    report['limitations'].append('Exact synthetic threshold correction preserves all neural/head weights and reuses unrounded cached features; final adapted two-example timings are measured on A-0 and TAMU-A-0.')
    (args.output/'report.json').write_text(json.dumps(report)+'\n')
    print('Report',args.output/'report.json',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('calibration','evaluation'),required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--synthetic-labels',type=Path,required=True)
    parser.add_argument('--real-labels',type=Path,required=True)
    parser.add_argument('--structured-labels',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.phase=='calibration':calibrate_saved(args)
    else:evaluate_saved(args)


if __name__=='__main__':main()
