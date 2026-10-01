"""Reviewed real circles and procedural crops, with recording-level separation."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re

import cv2
import numpy as np

from detector import Circle,patches,read_image
from neural_train import check_manifest


def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_real_manifest(manifest,split_manifest=None):
    scenes=manifest['scenes'];groups={};image_sides={};ids=set()
    if split_manifest is not None:
        assignments={s['id']:(s['group'],s['partition'],s['sha256']) for s in split_manifest['scenes']}
        if len(assignments)!=len(split_manifest['scenes']):raise ValueError('Duplicate scene in split manifest.')
    else:assignments=None
    for scene in scenes:
        sid=scene['id'];group=scene['group'];side=scene['partition']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',sid) or sid in ids:
            raise ValueError('Scene IDs must be unique safe filenames.')
        ids.add(sid)
        if side not in ('training','evaluation') or not isinstance(group,str) or not group:
            raise ValueError('Each real scene needs its recording group and training/evaluation partition.')
        if group in groups and groups[group]!=side:raise ValueError('A recording group crosses training and evaluation.')
        groups[group]=side
        if scene.get('use_for_head_fit',side=='training') and side!='training':
            raise ValueError('An evaluation frame cannot enter scoring-model fitting.')
        if scene.get('use_for_evaluation',side=='evaluation') and side!='evaluation':
            raise ValueError('A training frame cannot enter outer evaluation.')
        if scene['sha256'] in image_sides and image_sides[scene['sha256']]!=side:
            raise ValueError('Identical image pixels cross training and evaluation.')
        image_sides[scene['sha256']]=side
        if assignments is not None and assignments.get(sid)!=(group,side,scene['sha256']):
            raise ValueError('Real labels disagree with the fixed split manifest.')
        if not scene.get('origin') or not scene.get('label_provenance') or type(scene['complete_labels']) is not bool:
            raise ValueError('Real labels need origin, review provenance and an explicit completeness flag.')
        if not scene['targets']:raise ValueError('A real scene needs reviewed positive circles.')
        for kind in ('targets','negatives'):
            circles=scene.get(kind,[]);known=set()
            for index,row in enumerate(circles):
                identity=row.get('id',index)
                if type(identity) is not int or identity<0 or identity in known:raise ValueError('Circle IDs must be unique nonnegative integers within each label class.')
                known.add(identity)
                c=Circle(float(row['x']),float(row['y']),float(row['radius']))
                if not(0<=c.x<scene['width'] and 0<=c.y<scene['height']):raise ValueError('Annotated centers must be inside the source image.')
        radii=[float(t['radius']) for t in scene['targets']]
        if side=='training' and max(radii)-min(radii)>1e-6:
            raise ValueError('Each real training scene needs one common supplied-example measurement radius.')
        positive=np.array([[t['x'],t['y']] for t in scene['targets']],float)
        if len(positive)>1:
            distance=np.linalg.norm(positive[:,None,:]-positive[None,:,:],axis=2)
            np.fill_diagonal(distance,np.inf)
            if distance.min()<radii[0]:raise ValueError('Overlapping or duplicate positive centers need review.')
        for negative in scene.get('negatives',[]):
            if np.any(np.linalg.norm(positive-[negative['x'],negative['y']],axis=1)<radii[0]+negative['radius']):
                raise ValueError('A reviewed negative circle overlaps a positive measurement circle.')
        if side=='training' and (len(scene['targets'])<2 or not scene.get('negatives')):
            raise ValueError('Each real training frame needs two positives and explicit reviewed negatives; unmarked areas are never negatives.')
    if assignments is not None and ids!=set(assignments):raise ValueError('Split and label manifests must name the same scenes.')
    counts={side:sum(v==side for v in groups.values()) for side in ('training','evaluation')}
    if not counts['training'] or counts['training']!=counts['evaluation']:
        raise ValueError('The recording groups must be split equally between training and evaluation.')
    return scenes


def augment_training(patch,rng,*,translate=True):
    """Bounded transforms retain the entire central measurement circle.

    Cropping varies context via an affine scale/translation, not object labels.
    The transformed measurement disk stays inside the output even at extremes.
    Exposure/color changes and grayscale never change filled/empty assignment.
    """
    if rng.random()<.5:patch=patch[:,::-1]
    if rng.random()<.5:patch=patch[::-1]
    angle=float(rng.choice([0,90,180,270])+rng.uniform(-12,12))
    scale=float(rng.uniform(.90,1.10));shift=rng.uniform(-3,3,2) if translate else np.zeros(2)
    matrix=cv2.getRotationMatrix2D((47.5,47.5),angle,scale);matrix[:,2]+=shift
    result=cv2.warpAffine(patch,matrix,(96,96),borderMode=cv2.BORDER_REFLECT_101)
    contrast=float(rng.uniform(.85,1.15));exposure=float(rng.uniform(.85,1.15))
    result=(result-.5)*contrast+.5;result=np.clip(result*exposure,0,1)
    result=np.power(result,float(rng.uniform(.85,1.15)))
    if rng.random()<.3:
        gray=cv2.cvtColor(result.astype(np.float32),cv2.COLOR_RGB2GRAY);result=np.repeat(gray[:,:,None],3,axis=2)
    else:result=result*rng.uniform(.90,1.10,3)[None,None,:]
    if rng.random()<.5:result=cv2.GaussianBlur(result,(0,0),float(rng.uniform(.2,.7)))
    return np.uint8(np.clip(result,0,1)*255)


def plan_real_crops(scenes,variants=4,seed=61001):
    """Select recording-consistent object IDs before reading image pixels."""
    training=[s for s in scenes if s['partition']=='training'];rng=np.random.default_rng(seed)
    count=0;plans=[];permutations={}
    for scene in training:
        plan=scene.get('training_crop_plan',{});selected=[]
        nvariants=int(plan.get('variants',variants))
        if nvariants<1:raise ValueError('Training variants must be positive.')
        for label,kind,key in ((1,'targets','positive_count'),(0,'negatives','negative_count')):
            rows=scene[kind];requested=int(plan.get(key,len(rows)))
            if not 1<=requested<=len(rows) or (label and requested<2):raise ValueError('Training object sample count is incompatible with labels.')
            if requested==len(rows):chosen=list(range(len(rows)))
            else:
                identity=(scene['group'],kind)
                if identity not in permutations:permutations[identity]=rng.permutation(len(rows))
                order=permutations[identity]
                if len(order)!=len(rows):raise ValueError('Propagated recording labels need the same object list in every sampled frame.')
                if type(scene.get('frame_index0')) is not int or scene['frame_index0']<0:
                    raise ValueError('Subsampled recording frames need verified nonnegative integer frame_index0.')
                start=int(scene['frame_index0'])*requested
                chosen=[int(order[(start+i)%len(order)]) for i in range(requested)]
            selected.extend((label,kind,number,rows[number]) for number in chosen)
        count+=len(selected)*nvariants;plans.append((scene,selected,nvariants))
    return plans,count


def build_real_crops(scenes,folder,variants=4,seed=61001):
    """Only training pixels and explicit positive/negative labels enter here."""
    plans,count=plan_real_crops(scenes,variants,seed);rng=np.random.default_rng(seed+1)
    for scene,_,_ in plans:
        if sha256(scene['source'])!=scene['sha256']:raise ValueError('Real training source pixels changed.')
    values=np.lib.format.open_memmap(folder/'crops.npy',mode='w+',dtype=np.uint8,shape=(count,96,96,3))
    records=[];index=0
    for scene,selected,nvariants in plans:
        image=read_image(scene['source'])
        if image.shape[:2]!=(scene['height'],scene['width']):raise ValueError('Training image dimensions differ from labels.')
        radius=float(scene['targets'][0]['radius'])
        for label,kind,number,row in selected:
            circle=Circle(float(row['x']),float(row['y']),radius)
            for variant in range(nvariants):
                jitter=Circle(circle.x+float(rng.uniform(-.06,.06))*radius,
                              circle.y+float(rng.uniform(-.06,.06))*radius,
                              radius*float(rng.uniform(.96,1.04)))
                values[index]=augment_training(patches(image,[jitter])[0],rng)
                records.append({'index':index,'scene_id':scene['id'],'group':scene['group'],'domain':'real',
                                'split':'fit','label':label,'object_id':f"{kind}:{row.get('id',number)}",'variant':variant,
                                'circle':asdict(jitter),'label_source':'explicit_reviewed_circle'})
                index+=1
        if scene.get('frame_index0',0)%50==0:print('Real crops',scene['id'],len(selected)*nvariants,flush=True)
    values.flush();del values
    (folder/'crop-index.json').write_text(json.dumps(records)+'\n')
    return records


def load_synthetic_records(labels_path,cache_folder):
    """Validate the earlier original-network cache before copying its arrays."""
    scenes=check_manifest(json.loads(Path(labels_path).read_text()));by_id={s['id']:s for s in scenes}
    metadata=json.loads((cache_folder/'training-report.json').read_text())['source']
    if metadata['manifest_sha256']!=sha256(labels_path):raise ValueError('Synthetic labels changed since prefix caching.')
    for name,key in (('prefix.npy','prefix_sha256'),('teacher.npy','teacher_sha256')):
        if sha256(cache_folder/name)!=metadata['cache'][key]:raise ValueError('Saved synthetic prefix/teacher cache changed.')
    rows=json.loads((cache_folder/'crop-index.json').read_text())
    if [r['index'] for r in rows]!=list(range(len(rows))):raise ValueError('Synthetic cache indices are not contiguous.')
    for row in rows:
        scene=by_id[row['scene_id']]
        if row['group']!=scene['group'] or row['split']!=scene['split'] or row['split'] not in ('fit','validation'):
            raise ValueError('Synthetic crop split metadata is incompatible.')
        expected={t['slot'] for t in scene['targets' if row['label'] else 'negatives']}
        if row['kind']!='background' and row['object_id'] not in expected:raise ValueError('Synthetic crop object label changed.')
        row['domain']='synthetic';row['object_id']=str(row['object_id'])
    return rows,metadata


class BalancedTriplets:
    """Half real and half synthetic, then equal recording and frame sampling."""
    def __init__(self,records,split):
        frames={}
        for row in records:
            if row['split']==split:frames.setdefault((row['domain'],row['group'],row['scene_id']),[]).append(row)
        self.domains={}
        for (domain,group,scene),rows in sorted(frames.items()):
            positives=[r for r in rows if r['label']==1];negatives=[r['index'] for r in rows if r['label']==0]
            if len({r['object_id'] for r in positives})<2 or not negatives:
                raise ValueError('Each sampled frame needs different filled objects and reviewed negatives.')
            self.domains.setdefault(domain,{}).setdefault(group,[]).append((scene,positives,negatives))
        if split=='fit' and set(self.domains)!={'real','synthetic'}:raise ValueError('Hybrid fit requires both real and synthetic crops.')
        if split=='validation' and set(self.domains)!={'synthetic'}:raise ValueError('This planned validation must remain synthetic-only.')
        self.group_order={};self.group_cursor={};self.frame_order={};self.frame_cursor={};self.seen=set()

    def sample(self,rng,count):
        domains=sorted(self.domains);rows=[]
        for i in range(count):
            domain=domains[i%len(domains)];groups=self.domains[domain];names=sorted(groups)
            if self.group_cursor.get(domain,0)>=len(self.group_order.get(domain,[])):
                self.group_order[domain]=rng.permutation(len(names));self.group_cursor[domain]=0
            group=names[int(self.group_order[domain][self.group_cursor[domain]])];self.group_cursor[domain]+=1
            frames=groups[group];key=(domain,group)
            if self.frame_cursor.get(key,0)>=len(self.frame_order.get(key,[])):
                self.frame_order[key]=rng.permutation(len(frames));self.frame_cursor[key]=0
            scene,positive,negative=frames[int(self.frame_order[key][self.frame_cursor[key]])];self.frame_cursor[key]+=1
            self.seen.add((domain,group,scene))
            anchor=positive[int(rng.integers(len(positive)))];other=[r for r in positive if r['object_id']!=anchor['object_id']]
            target=other[int(rng.integers(len(other)))];neg=negative[int(rng.integers(len(negative)))]
            rows.append((anchor['index'],target['index'],neg))
        return np.asarray(rows,np.int64)

    def coverage(self):
        return {domain:{group:{'frames':len(frames),'updated_frames':sum((domain,group,scene) in self.seen for scene,_,_ in frames)}
                        for group,frames in groups.items()} for domain,groups in self.domains.items()}

    def full_coverage(self):
        return all(row['updated_frames']==row['frames'] for groups in self.coverage().values() for row in groups.values())
