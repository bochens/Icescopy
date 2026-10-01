"""Small user-trained droplet segmentation, with numeric JSON forest models.

Training images must mark every droplet to keep. Circle interiors are positive,
circle boundaries are ignored, and other source pixels supply background. The
optional scikit-learn package is imported only by fit_model; inference needs
NumPy and OpenCV. No neural model or circle-finder proposal gates detection.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import errno
import math
import os
from pathlib import Path
import tempfile
import time
import shutil

import cv2
import numpy as np


MODEL_VERSION = 1
FEATURE_VERSION = 1
FEATURE_NAMES = ['gray','red','green','blue']
FEATURE_NAMES += [f'gray_mean_{s}' for s in ('015','035','070','120')]
FEATURE_NAMES += [f'gray_std_{s}' for s in ('025','060','100')]
FEATURE_NAMES += [f'gradient_{s}' for s in ('015','035','070')]
FEATURE_NAMES += [f'laplacian_{s}' for s in ('015','035','070')]
FEATURE_NAMES += ['contrast_015_035','contrast_035_070','contrast_070_120','red_minus_green','blue_minus_green']
INFERENCE = {'normalized_radius':12.,'stride':2,'maximum_working_pixels':2_000_000,
             'minimum_component_radius_fraction':.20,'positive_radius_fraction':.75,
             'ignored_boundary_radius_fraction':1.25}
TRAINING = {'trees':64,'maximum_depth':12,'minimum_leaf_samples':6,'threads':4,
            'seed':73001,'augmentation_tiles_per_image':32,'tile_size':160,
            'samples_per_class_per_tile':200,'samples_per_class_original':2000}
MAX_FILE_BYTES = 50*1024*1024
MAX_TREES = 256
MAX_NODES = 500_000


class CancelledError(RuntimeError):
    """The caller canceled a training or current-frame detection operation."""


@dataclass(frozen=True)
class Circle:
    x: float
    y: float
    radius: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.x,self.y,self.radius)) or self.radius <= 0:
            raise ValueError('Circle coordinates must be finite and radius positive.')


def _circle(row):
    if isinstance(row,dict):return Circle(float(row['x']),float(row['y']),float(row['radius']))
    return Circle(float(row.x),float(row.y),float(row.radius))


def same_object(a,b):
    a,b=_circle(a),_circle(b)
    return math.hypot(a.x-b.x,a.y-b.y) < .9*(a.radius+b.radius)


def _check_cancelled(cancelled):
    if cancelled is not None and cancelled():raise CancelledError('Operation canceled.')


def preprocess_image(raw,color_order='RGB'):
    """Normalize one uint8/uint16/float gray or RGB/BGR(A) frame to RGB float32."""
    if color_order not in ('RGB','BGR'):raise ValueError('color_order must be RGB or BGR.')
    raw=np.asarray(raw)
    if raw.dtype not in (np.uint8,np.uint16,np.float32,np.float64) or not raw.size or not np.isfinite(raw).all():
        raise ValueError('Expected a nonempty finite uint8, uint16 or floating-point frame.')
    if raw.ndim==2:rgb=np.repeat(raw[...,None],3,axis=2)
    elif raw.ndim==3 and raw.shape[2] in (3,4):rgb=raw[...,:3] if color_order=='RGB' else raw[...,2::-1]
    else:raise ValueError('Expected grayscale, RGB, BGR or RGBA/BGRA pixels.')
    rgb=rgb.astype(np.float32);lo,hi=np.percentile(rgb,[1,99])
    if hi<=lo:lo,hi=float(rgb.min()),float(rgb.max())
    return np.clip((rgb-lo)/max(hi-lo,1e-6),0,1).astype(np.float32)


def _image(raw):
    raw=np.asarray(raw)
    if raw.dtype==np.float32 and raw.ndim==3 and raw.shape[2]==3:
        if not raw.size or not np.isfinite(raw).all() or raw.min()<0 or raw.max()>1:
            raise ValueError('Normalized RGB pixels must be finite and between zero and one.')
        return raw
    return preprocess_image(raw,'RGB')


def _prepare(image,radius):
    scale=INFERENCE['normalized_radius']/radius
    pixels=image.shape[0]*image.shape[1]*scale*scale
    if pixels>INFERENCE['maximum_working_pixels']:
        scale*=math.sqrt(INFERENCE['maximum_working_pixels']/pixels)
    matrix=np.array([[scale,0,(scale-1)/2],[0,scale,(scale-1)/2]],np.float32)
    shape=(max(1,math.ceil(image.shape[1]*scale)),max(1,math.ceil(image.shape[0]*scale)))
    resized=cv2.warpAffine(image,matrix,shape,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(.5,.5,.5))
    valid=cv2.warpAffine(np.ones(image.shape[:2],np.uint8),matrix,shape,flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)>0
    return resized,valid,scale


def feature_field(image,radius):
    """Dense radius-scaled intensity/edge/texture; never include image position."""
    gray=cv2.cvtColor(np.asarray(image,np.float32),cv2.COLOR_RGB2GRAY)
    means=[cv2.GaussianBlur(gray,(0,0),max(.5,radius*s),borderType=cv2.BORDER_REPLICATE) for s in (.15,.35,.7,1.2)]
    fields=[gray,image[...,0],image[...,1],image[...,2],*means]
    for s in (.25,.6,1.):
        sigma=max(.5,radius*s);mean=cv2.GaussianBlur(gray,(0,0),sigma,borderType=cv2.BORDER_REPLICATE)
        square=cv2.GaussianBlur(gray*gray,(0,0),sigma,borderType=cv2.BORDER_REPLICATE)
        fields.append(np.sqrt(np.maximum(0,square-mean*mean)))
    gradients=[];laplacians=[]
    for mean in means[:3]:
        dx=cv2.Sobel(mean,cv2.CV_32F,1,0,ksize=3,borderType=cv2.BORDER_REPLICATE)
        dy=cv2.Sobel(mean,cv2.CV_32F,0,1,ksize=3,borderType=cv2.BORDER_REPLICATE)
        gradients.append(np.hypot(dx,dy));laplacians.append(cv2.Laplacian(mean,cv2.CV_32F,ksize=3,borderType=cv2.BORDER_REPLICATE))
    fields.extend(gradients);fields.extend(laplacians)
    fields.extend([means[i]-means[i+1] for i in range(3)])
    fields.extend([image[...,0]-image[...,1],image[...,2]-image[...,1]])
    step=INFERENCE['stride']
    return np.stack([f[::step,::step] for f in fields],axis=-1).astype(np.float32)


def transform_circles(circles,matrix):
    scale=float(np.hypot(matrix[0,0],matrix[0,1]))
    return [Circle(float(matrix[0]@[c.x,c.y,1]),float(matrix[1]@[c.x,c.y,1]),c.radius*scale) for c in circles]


def training_labels(circles,valid):
    """Complete keep labels; ignore boundaries, padding and truncated droplets."""
    step=INFERENCE['stride'];yy,xx=np.mgrid[:valid.shape[0]:step,:valid.shape[1]:step]
    labels=np.where(valid[::step,::step],0,-1).astype(np.int8)
    positive=[]
    for c in circles:
        distance=(xx-c.x)**2+(yy-c.y)**2
        labels[distance <= (INFERENCE['ignored_boundary_radius_fraction']*c.radius)**2]=-1
        angles=np.linspace(0,2*np.pi,16,endpoint=False)
        sx=np.rint(np.r_[c.x,c.x+c.radius*np.cos(angles)]).astype(int)
        sy=np.rint(np.r_[c.y,c.y+c.radius*np.sin(angles)]).astype(int)
        whole=(sx>=0).all() and (sy>=0).all() and (sx<valid.shape[1]).all() and (sy<valid.shape[0]).all()
        if whole and valid[sy,sx].all():positive.append(distance <= (INFERENCE['positive_radius_fraction']*c.radius)**2)
    for inside in positive:labels[inside & valid[::step,::step]]=1
    return labels


def _augment(image,circles,focus,rng):
    size=TRAINING['tile_size'];radius=float(np.median([c.radius for c in circles]))
    scale=INFERENCE['normalized_radius']/radius*float(rng.uniform(.75,1.25))
    angle=float(rng.uniform(-np.pi,np.pi));linear=scale*np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    if rng.random()<.5:linear[0]*=-1
    if rng.random()<.5:linear[1]*=-1
    location=rng.uniform(size*.3,size*.7,2);matrix=np.c_[linear,location-linear@[focus.x,focus.y]].astype(np.float32)
    tile=cv2.warpAffine(image,matrix,(size,size),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(.5,.5,.5))
    valid=cv2.warpAffine(np.ones(image.shape[:2],np.uint8),matrix,(size,size),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)>0
    tile=np.clip((tile-.5)*float(rng.uniform(.8,1.2))+.5,0,1)
    tile=np.clip(tile*float(rng.uniform(.8,1.2))+float(rng.uniform(-.03,.03)),0,1)**float(rng.uniform(.85,1.15))
    tile=np.clip(tile*rng.uniform(.9,1.1,(1,1,3)),0,1).astype(np.float32)
    if rng.random()<.25:tile=np.repeat(cv2.cvtColor(tile,cv2.COLOR_RGB2GRAY)[...,None],3,axis=2)
    if rng.random()<.4:tile=cv2.GaussianBlur(tile,(0,0),float(rng.uniform(.2,.7)))
    return tile,valid,transform_circles(circles,matrix),radius*scale,matrix


def _samples(features,labels,rng,limit):
    chunks=[];classes=[]
    for value in (0,1):
        indices=np.flatnonzero(labels.ravel()==value)
        if len(indices):
            selected=rng.choice(indices,min(len(indices),limit),replace=False)
            chunks.append(features.reshape(-1,len(FEATURE_NAMES))[selected]);classes.append(np.full(len(selected),value,np.uint8))
    return (np.concatenate(chunks),np.concatenate(classes)) if chunks else (np.empty((0,len(FEATURE_NAMES)),np.float32),np.empty(0,np.uint8))


def fit_model(scenes,progress=None,cancelled=None):
    """Fit complete positive annotations; no separate negative sample input.

    scenes contain RGB arrays, Circle lists and optional source_key strings.
    All crop geometry transforms pixels and circles together. Background is
    derived only under the explicit instruction to mark every wanted droplet.
    """
    _check_cancelled(cancelled)
    try:
        from sklearn.ensemble import RandomForestClassifier
        import sklearn
    except ImportError as error:
        raise RuntimeError('Training support is not installed. Install Icescopy with the training extra '
                           '(python -m pip install "Icescopy[training]").') from error
    start=time.perf_counter();rng=np.random.default_rng(TRAINING['seed']);xs=[];ys=[];radii=[];circle_count=0
    scenes=list(scenes)
    if not scenes:raise ValueError('Select at least one image with marked droplet circles.')
    report=progress or (lambda text:None)
    for index,scene in enumerate(scenes):
        _check_cancelled(cancelled);image=_image(scene['image']);circles=[_circle(c) for c in scene['circles']]
        if not circles:raise ValueError('Every training image needs at least one marked droplet.')
        if any(not (0<=c.x<image.shape[1] and 0<=c.y<image.shape[0]) for c in circles):
            raise ValueError('Training circle centers must lie inside their linked image.')
        radius=float(np.median([c.radius for c in circles]));radii.extend(c.radius for c in circles);circle_count+=len(circles)
        report(f'Measuring training image {index+1}/{len(scenes)}.')
        working,valid,scale=_prepare(image,radius)
        matrix=np.array([[scale,0,(scale-1)/2],[0,scale,(scale-1)/2]],np.float32)
        labels=training_labels(transform_circles(circles,matrix),valid)
        features=feature_field(working,radius*scale)
        # Include every original circle's interior before random background
        # sampling, so a dense image cannot erase small labeled objects.
        yy,xx=np.mgrid[:working.shape[0]:2,:working.shape[1]:2]
        for c in transform_circles(circles,matrix):
            points=np.flatnonzero((((xx-c.x)**2+(yy-c.y)**2)<=(.7*c.radius)**2).ravel() & (labels.ravel()==1))
            if not len(points):raise ValueError('A marked droplet is truncated or too small to supervise safely.')
            selected=rng.choice(points,min(16,len(points)),replace=False)
            xs.append(features.reshape(-1,len(FEATURE_NAMES))[selected]);ys.append(np.ones(len(selected),np.uint8))
        x,y=_samples(features,labels,rng,TRAINING['samples_per_class_original']);xs.append(x);ys.append(y)
        focus_order=rng.permutation(len(circles))
        for variant in range(TRAINING['augmentation_tiles_per_image']):
            _check_cancelled(cancelled)
            if variant and variant%len(circles)==0:focus_order=rng.permutation(len(circles))
            focus=circles[int(focus_order[variant%len(circles)])]
            tile,valid,transformed,r,matrix=_augment(image,circles,focus,rng)
            x,y=_samples(feature_field(tile,r),training_labels(transformed,valid),rng,TRAINING['samples_per_class_per_tile'])
            xs.append(x);ys.append(y)
    _check_cancelled(cancelled);x=np.concatenate(xs);y=np.concatenate(ys)
    if set(np.unique(y))!={0,1}:raise ValueError('Training images need marked droplets and visible background outside their boundaries.')
    feature_seconds=time.perf_counter()-start;report(f'Training a small forest on {len(y):,} labeled image points.')
    classifier=RandomForestClassifier(n_estimators=TRAINING['trees'],max_depth=TRAINING['maximum_depth'],
          min_samples_leaf=TRAINING['minimum_leaf_samples'],max_features='sqrt',class_weight='balanced_subsample',
          n_jobs=TRAINING['threads'],random_state=TRAINING['seed'])
    fit_start=time.perf_counter();classifier.fit(x,y);fit_seconds=time.perf_counter()-fit_start;_check_cancelled(cancelled)
    trees=_export_trees(classifier)
    stats={'images':len(scenes),'circles':circle_count,'samples':len(y),'positive_samples':int((y==1).sum()),
           'negative_samples':int((y==0).sum()),'augmentation_tiles':len(scenes)*TRAINING['augmentation_tiles_per_image'],
           'feature_seconds':feature_seconds,'fit_seconds':fit_seconds,'total_seconds':time.perf_counter()-start,
           'sklearn_version':sklearn.__version__,'parameters':dict(TRAINING),
           'negative_source':'Outside all marked circles plus ignored boundary band; complete keep annotations required.'}
    model={'model_version':MODEL_VERSION,'feature_version':FEATURE_VERSION,'feature_names':list(FEATURE_NAMES),
           'inference':dict(INFERENCE),'default_radius':float(np.median(radii)),'threshold':.5,'trees':trees,
           'feature_importances':classifier.feature_importances_.tolist(),'training_stats':stats}
    validate_model(model);report(f'Training finished in {stats["total_seconds"]:.1f} seconds.')
    return model


def _export_trees(classifier):
    trees=[]
    for estimator in classifier.estimators_:
        tree=estimator.tree_;values=tree.value[:,0,:];probability=values[:,1]/values.sum(1)
        trees.append({'left':tree.children_left.tolist(),'right':tree.children_right.tolist(),'feature':tree.feature.tolist(),
                      'threshold':tree.threshold.tolist(),'probability':probability.tolist()})
    return trees


def validate_model(model):
    """Validate bounded numeric trees; no executable Python object is loaded."""
    required={'model_version','feature_version','feature_names','inference','default_radius','threshold','trees','feature_importances','training_stats'}
    if not isinstance(model,dict) or set(model)!=required:raise ValueError('Malformed droplet model.')
    if (model['model_version']!=MODEL_VERSION or model['feature_version']!=FEATURE_VERSION
            or model['feature_names']!=FEATURE_NAMES or model['inference']!=INFERENCE):
        raise ValueError('Incompatible droplet feature/model version.')
    for name in ('default_radius','threshold'):
        v=model[name]
        if type(v) not in (int,float) or not math.isfinite(v):raise ValueError(f'Invalid model {name}.')
    if not .01<=model['default_radius']<=1e5 or not 0<=model['threshold']<=1:raise ValueError('Invalid model radius or cutoff.')
    trees=model['trees']
    if not isinstance(trees,list) or not 1<=len(trees)<=MAX_TREES:raise ValueError('Invalid forest tree count.')
    total=0
    for tree in trees:
        if not isinstance(tree,dict) or set(tree)!={'left','right','feature','threshold','probability'}:raise ValueError('Malformed numeric tree.')
        n=len(tree['left']) if isinstance(tree['left'],list) else 0;total+=n
        if not n or total>MAX_NODES or any(not isinstance(tree[k],list) or len(tree[k])!=n for k in tree):raise ValueError('Invalid tree dimensions.')
        parents=np.zeros(n,np.int32);depth=np.zeros(n,np.int32)
        for i,(left,right,feature,threshold,probability) in enumerate(zip(tree['left'],tree['right'],tree['feature'],tree['threshold'],tree['probability'])):
            if any(type(v) is not int for v in (left,right,feature)):raise ValueError('Tree indices must be integers.')
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in (threshold,probability)) or not 0<=probability<=1:raise ValueError('Invalid tree numeric value.')
            if left==right==-1:
                if feature!=-2:raise ValueError('Invalid leaf feature.')
            elif 0<=feature<len(FEATURE_NAMES) and i<left<n and i<right<n and left!=right:
                parents[left]+=1;parents[right]+=1
                depth[left]=depth[i]+1;depth[right]=depth[i]+1
                if depth[left]>32:raise ValueError('Tree depth exceeds the supported bound.')
            else:raise ValueError('Invalid or cyclic tree children.')
        if parents[0]!=0 or (parents[1:]!=1).any():raise ValueError('Tree nodes must form one connected tree.')
    importances=model['feature_importances']
    if not isinstance(importances,list) or len(importances)!=len(FEATURE_NAMES) or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in importances):
        raise ValueError('Invalid feature importance values.')
    if not isinstance(model['training_stats'],dict):raise ValueError('Invalid training statistics.')
    return model


def save_model(model,path,overwrite=False):
    validate_model(model);path=Path(path)
    if path.exists() and not overwrite:raise FileExistsError(f'Model already exists: {path}')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,prefix=path.name+'.',suffix='.tmp',delete=False) as handle:
            temporary=Path(handle.name);json.dump(model,handle,separators=(',',':'),allow_nan=False)
        if temporary.stat().st_size>MAX_FILE_BYTES:raise ValueError('Model exceeds the supported file size.')
        if overwrite:os.replace(temporary,path)
        else:
            try:os.link(temporary,path)
            except OSError as error:
                # Some removable drives cannot create hard links. Exclusive
                # creation still protects an existing model; EEXIST is never
                # treated as an unsupported-filesystem error.
                unsupported={errno.EPERM,errno.ENOSYS,errno.ENOTSUP,errno.EOPNOTSUPP}
                if error.errno not in unsupported:raise
                created=False
                try:
                    with path.open('xb') as destination:
                        created=True
                        with temporary.open('rb') as source:shutil.copyfileobj(source,destination)
                except BaseException:
                    if created:path.unlink(missing_ok=True)
                    raise
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def load_model(path):
    path=Path(path)
    if path.stat().st_size>MAX_FILE_BYTES:raise ValueError('Model file is too large.')
    def unique_keys(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate JSON model key.')
            result[k]=v
        return result
    try:
        with path.open(encoding='utf-8') as handle:model=json.load(handle,object_pairs_hook=unique_keys)
        return validate_model(model)
    except (json.JSONDecodeError,RecursionError,UnicodeError) as error:
        raise ValueError('Invalid droplet model JSON.') from error


class RandomForestDetector:
    def __init__(self,model):
        self.model=validate_model(model)
        self.trees=[{k:np.asarray(v,np.float64 if k in ('threshold','probability') else np.int32) for k,v in tree.items()} for tree in model['trees']]

    def predict_scores(self,features,cancelled=None):
        features=np.asarray(features,np.float32)
        if features.ndim!=2 or features.shape[1]!=len(FEATURE_NAMES) or not np.isfinite(features).all():raise ValueError('Invalid dense forest features.')
        output=np.zeros(len(features),np.float64)
        for tree in self.trees:
            _check_cancelled(cancelled);nodes=np.zeros(len(features),np.int32)
            while True:
                _check_cancelled(cancelled)
                active=np.flatnonzero(tree['left'][nodes]>=0)
                if not len(active):break
                current=nodes[active];left=features[active,tree['feature'][current]]<=tree['threshold'][current]
                nodes[active]=np.where(left,tree['left'][current],tree['right'][current])
            output+=tree['probability'][nodes]
        return (output/len(self.trees)).astype(np.float32)

    def predict_field(self,image,examples=(),cancelled=None):
        _check_cancelled(cancelled);image=_image(image);examples=[_circle(c) for c in examples]
        if len(examples)>2 or any(not (0<=c.x<image.shape[1] and 0<=c.y<image.shape[0]) for c in examples):raise ValueError('Supply zero, one or two in-frame example circles.')
        radius=float(np.median([c.radius for c in examples])) if examples else self.model['default_radius']
        working,valid,scale=_prepare(image,radius);features=feature_field(working,radius*scale)
        _check_cancelled(cancelled);shape=features.shape[:2]
        scores=self.predict_scores(features.reshape(-1,len(FEATURE_NAMES)),cancelled).reshape(shape)
        scores[~valid[::2,::2]]=0
        return scores,{'scale':scale,'radius':radius,'stride':2,'image_shape':list(image.shape[:2])}

    def predict(self,image,examples=(),protected=(),cancelled=None):
        field,geometry=self.predict_field(image,examples,cancelled);_check_cancelled(cancelled)
        mask=(field>=self.model['threshold']).astype(np.uint8)
        count,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
        scale=geometry['scale'];radius=geometry['radius'];step=geometry['stride']
        minimum=max(2.,np.pi*(INFERENCE['minimum_component_radius_fraction']*radius*scale/step)**2)
        accepted=[];known=[_circle(c) for c in list(protected)+list(examples)]
        for label in range(1,count):
            _check_cancelled(cancelled)
            if stats[label,cv2.CC_STAT_AREA]<minimum:continue
            left,top,width,height=stats[label,:4]
            ys,xs=np.where(labels[top:top+height,left:left+width]==label)
            ys+=top;xs+=left;weights=field[ys,xs]
            x=(step*float(np.average(xs,weights=weights))+.5)/scale-.5
            y=(step*float(np.average(ys,weights=weights))+.5)/scale-.5
            circle=Circle(x,y,radius);score=float(weights.mean())
            if 0<=x<geometry['image_shape'][1] and 0<=y<geometry['image_shape'][0] and not any(same_object(circle,c) for c in known):
                accepted.append((circle,score))
        result=[]
        for circle,score in sorted(accepted,key=lambda row:row[1],reverse=True):
            if not any(same_object(circle,prior) for prior,_ in result):result.append((circle,score))
        return [{'circle':asdict(c),'score':score} for c,score in result]
