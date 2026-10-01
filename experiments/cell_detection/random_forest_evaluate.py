"""Personalized dense forests: guarded fitting regions, unchanged held-out crops."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from icescopy_droplet_detection import Circle, RandomForestDetector, fit_model, save_model
from joint_metrics import measure_scene, summarize


def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_scene(scene):
    if sha256(scene['source'])!=scene['sha256']:raise ValueError('A source image changed after the spatial split.')
    raw=cv2.imread(scene['source'],cv2.IMREAD_UNCHANGED)
    if raw is None:raise ValueError('Cannot read linked source image.')
    if raw.shape[:2]!=(scene['height'],scene['width']):raise ValueError('Source dimensions differ from its labels.')
    if raw.ndim==3:raw=raw[:,:,2::-1]
    return raw


def validate_split(manifest):
    if manifest['format_version']!='joint-spatial-split-v1':raise ValueError('Expected the reviewed guarded spatial split.')
    groups={}
    for scene in manifest['scenes']:
        groups.setdefault(scene['instrument_id'],{})[scene['split']]=scene
    for scenes in groups.values():
        if set(scenes)!={'fit','validation','test'}:raise ValueError('Every setup must retain separate fit/validation/test regions.')
        ordered=sorted(scenes.values(),key=lambda s:s['source_bbox'][1])
        if any(a['source_bbox'][3]>=b['source_bbox'][1] for a,b in zip(ordered,ordered[1:])):
            raise ValueError('Source regions overlap or have no guard.')
        if len({s['original_sha256'] for s in ordered})!=1:raise ValueError('Regions must come from the declared same source.')
    return groups


def preview(raw,scene,predictions,seeds,metrics,path):
    if raw.dtype==np.uint16:
        image=np.uint8(np.clip(raw.astype(np.float32)/65535,0,1)*255)
    else:image=raw.copy()
    if image.ndim==2:image=np.repeat(image[...,None],3,axis=2)
    centered={row['prediction'] for row in metrics['centered_matches']}
    broad={row['prediction'] for row in metrics['matches']}
    for i,row in enumerate(predictions):
        c=row['circle'];color=(40,225,70) if i in centered else ((255,220,30) if i in broad else (255,125,30))
        cv2.circle(image,(round(c['x']),round(c['y'])),round(c['radius']),color,2)
    for i in seeds:
        c=scene['targets'][i];cv2.circle(image,(round(c['x']),round(c['y'])),round(c['radius']),(20,220,240),2)
    cv2.imwrite(str(path),image[:,:,::-1])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--instrument',help='Optional exact instrument ID; fit PCR first without changing the recipe.')
    args=parser.parse_args();manifest=json.loads(args.manifest.read_text());groups=validate_split(manifest)
    if args.instrument:
        if args.instrument not in groups:raise ValueError('Unknown instrument ID.')
        groups={args.instrument:groups[args.instrument]}
    args.output.mkdir(parents=True,exist_ok=False)
    rows=[];models={};started=time.perf_counter()
    for instrument,scenes in groups.items():
        # Only complete keep-circle geometry enters fitting. Supplied reviewed
        # negatives/invalid centers are intentionally evaluation-only.
        fitting=scenes['fit'];raw=read_scene(fitting)
        model=fit_model([{'image':raw,'circles':[Circle(c['x'],c['y'],c['radius']) for c in fitting['targets']],
                          'source_key':instrument}],progress=lambda text:print(text,flush=True))
        model_path=args.output/(instrument+'.icescopy-model.json');save_model(model,model_path)
        models[instrument]={'model_file':model_path.name,'model_bytes':model_path.stat().st_size,
                            'model_sha256':sha256(model_path),'fit_source_sha256':fitting['sha256'],
                            'training_stats':model['training_stats']}
        detector=RandomForestDetector(model)
        for split in ('validation','test'):
            scene=scenes[split];raw=read_scene(scene)
            truth=[Circle(c['x'],c['y'],c['radius']) for c in scene['targets']]
            trials=[[0],[0,len(truth)//2]] if len(truth)>1 else [[0]]
            for seeds in trials:
                examples=[truth[i] for i in seeds];t=time.perf_counter()
                predictions=detector.predict(raw,examples=examples,protected=examples)
                elapsed=time.perf_counter()-t
                # The user's current rule is a complete KEEP list: unmatched
                # regions are unwanted, without changing the old manifest.
                metrics=measure_scene(dict(scene,complete_labels=True),[row['circle'] for row in predictions],seeds)
                row={'scene_id':scene['id'],'instrument':instrument,'split':split,
                     'seconds':elapsed,'known_empty_hits':len(metrics['known_negative_indices']),
                     'scores':[p['score'] for p in predictions],**metrics}
                rows.append(row)
                preview(raw,scene,predictions,seeds,metrics,args.output/(scene['id']+f'-{len(seeds)}examples.png'))
                print(f"{scene['id']} {len(seeds)} examples: {metrics['centered']}/{metrics['remaining']} centered, "
                      f"{metrics['found']} found, {metrics['extras']} extras, {row['known_empty_hits']} known-empty hits, {elapsed:.3f}s",flush=True)
        report={'method':'Dense image-feature personalized random forest; no proposal gate or neural model.',
                'manifest_sha256':sha256(args.manifest),'models':models,'rows':rows,
                'test_two_example_summary':summarize([r for r in rows if r['split']=='test' and len(r['seeds'])==2]),
                'elapsed_seconds':time.perf_counter()-started,
                'fixed_choices':{'threshold':.5,'single_examples':[0],'pair_examples':'[0, middle]',
                                 'validation_tuning':False,'manual_negatives_used_for_fit':False},
                'limitations':['One source image per setup: held-out pixels, not unseen recordings.',
                               'All marked circles are treated as the complete keep list during fitting, per user instruction.',
                               'Under the current complete keep-list instruction, all unmatched additions are counted as unwanted.',
                               'These validation/test regions were inspected in earlier experiments; this is a fixed diagnostic comparison, not a fresh blind test.']}
        (args.output/'report.json').write_text(json.dumps(report,indent=2))
    print(f'Report saved: {args.output / "report.json"}',flush=True)


if __name__=='__main__':main()
