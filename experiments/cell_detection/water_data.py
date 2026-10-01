"""User-labeled water cells, preserving native circles and instrument identity."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import numpy as np

from detector import Circle,patches,read_image
from hybrid_data import BalancedTriplets,augment_training,sha256


def check_manual_manifest(manifest):
    scenes=manifest['scenes'];ids=set();groups=set()
    for scene in scenes:
        if scene['id'] in ids or scene['group'] in groups:raise ValueError('One original image per instrument is required.')
        ids.add(scene['id']);groups.add(scene['group'])
        if scene['partition']!='training' or scene['origin']!='user_manually_labeled_recording':
            raise ValueError('Only the new user-labeled training images may enter this adaptation.')
        if not scene.get('negative_review_complete') or not scene['negatives'] or len(scene['targets'])<2:
            raise ValueError('Each instrument needs user positives and explicit reviewed negatives.')
        if scene.get('complete_labels',False):raise ValueError('These manual frames do not establish complete negative labels.')
        for kind in ('targets','negatives'):
            known=set()
            for row in scene[kind]:
                identity=row['id']
                if type(identity) is not int or identity<0 or identity in known:raise ValueError('Circle IDs must be unique nonnegative integers.')
                known.add(identity);circle=Circle(float(row['x']),float(row['y']),float(row['radius']))
                if not(0<=circle.x<scene['width'] and 0<=circle.y<scene['height']):raise ValueError('Manual circle centers must be inside their original image.')
        pos=[Circle(float(r['x']),float(r['y']),float(r['radius'])) for r in scene['targets']]
        neg=[Circle(float(r['x']),float(r['y']),float(r['radius'])) for r in scene['negatives']]
        for i,a in enumerate(pos):
            if any(np.hypot(a.x-b.x,a.y-b.y)<a.radius+b.radius for b in pos[i+1:]+neg):
                raise ValueError('Overlapping manual positives or positive/negative circles need review.')
    return scenes


def build_manual_crops(scenes,folder,variants=8,seed=61003):
    """Square context crops and isotropic augmentation keep every own radius."""
    for scene in scenes:
        if sha256(scene['source'])!=scene['sha256']:raise ValueError('Manual source pixels changed.')
    count=sum(len(s['targets'])+len(s['negatives']) for s in scenes)*variants
    values=np.lib.format.open_memmap(folder/'crops.npy',mode='w+',dtype=np.uint8,shape=(count,96,96,3))
    rng=np.random.default_rng(seed);records=[];index=0
    for scene in scenes:
        image=read_image(scene['source'])
        if image.shape[:2]!=(scene['height'],scene['width']):raise ValueError('Manual image dimensions changed.')
        for label,kind in ((1,'targets'),(0,'negatives')):
            for row in scene[kind]:
                original=Circle(float(row['x']),float(row['y']),float(row['radius']))
                for variant in range(variants):
                    jitter=Circle(original.x+float(rng.uniform(-.06,.06))*original.radius,
                                  original.y+float(rng.uniform(-.06,.06))*original.radius,
                                  original.radius*float(rng.uniform(.96,1.04)))
                    values[index]=augment_training(patches(image,[jitter])[0],rng)
                    records.append({'index':index,'scene_id':scene['id'],'group':scene['group'],'domain':'real',
                                    'split':'fit','label':label,'object_id':f"{kind}:{row['id']}",'variant':variant,
                                    'source_circle':asdict(original),'circle':asdict(jitter),
                                    'label_source':'user_positive' if label else 'explicit_reviewed_negative'})
                    index+=1
        print('Manual variants',scene['id'],(len(scene['targets'])+len(scene['negatives']))*variants,flush=True)
    values.flush();del values
    (folder/'crop-index.json').write_text(json.dumps(records)+'\n')
    return records


class WaterTriplets(BalancedTriplets):
    """Cycle positive object IDs, so all manual cells receive an actual update."""
    def __init__(self,records,split):
        super().__init__(records,split);self.objects={};self.object_order={};self.object_cursor={}
        self.updated=set();self.rows={r['index']:r for r in records}
        for domain,groups in self.domains.items():
            for group,frames in groups.items():
                for scene,positive,_ in frames:
                    pool={}
                    for row in positive:pool.setdefault(row['object_id'],[]).append(row)
                    self.objects[(domain,group,scene)]=pool

    def sample(self,rng,count):
        # Reuse recording/frame balancing; substitute different cycled positive
        # objects from the same frame, retaining the sampled reviewed negative.
        samples=super().sample(rng,count)
        for row in samples:
            source=self.rows[int(row[0])];key=(source['domain'],source['group'],source['scene_id']);pool=self.objects[key]
            names=sorted(pool)
            def next_object():
                if self.object_cursor.get(key,0)>=len(self.object_order.get(key,[])):
                    self.object_order[key]=rng.permutation(len(names));self.object_cursor[key]=0
                name=names[int(self.object_order[key][self.object_cursor[key]])];self.object_cursor[key]+=1
                choices=pool[name];return choices[int(rng.integers(len(choices)))]
            anchor=next_object();positive=next_object()
            while positive['object_id']==anchor['object_id']:positive=next_object()
            row[0]=anchor['index'];row[1]=positive['index']
        return samples

    def mark_updated(self,samples):
        for index in samples[:,:2].ravel():
            row=self.rows[int(index)]
            self.updated.add((row['domain'],row['group'],row['scene_id'],row['object_id']))

    def object_coverage(self):
        result={}
        for (domain,group,scene),pool in self.objects.items():
            result.setdefault(domain,{})[group]={'objects':len(pool),
              'updated_objects':sum((domain,group,scene,identity) in self.updated for identity in pool)}
        return result

    def all_manual_updated(self):
        return all(row['objects']==row['updated_objects'] for row in self.object_coverage().get('real',{}).values())
