"""Complete user-circle supervision for one setup's small shared neural model.

No recording assignment, image loading or training is performed on import.
Every valid core position is supervised: a marked center is positive, other
positions are negative. This module never accepts separate negative labels.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from joint_model import CORE, HALO, NORMALIZED_RADIUS, PADDING_RGB, STRIDE, TILE, JointNetwork


CONFIG = {'seed':71003, 'threads':4, 'passes':12, 'steps_per_pass':60,
          'batch_size':4, 'learning_rate':1e-4, 'weight_decay':1e-4,
          'center_loss_weight':1., 'offset_loss_weight':1., 'radius_loss_weight':1.,
          'gradient_clip':5., 'threshold':.5,
          'supervision':'complete-user-center-offset-radius-v1'}


def original_network(weights, expected_sha256, seed=71003):
    """Load only the explicitly verified original ImageNet features, no decoder."""
    path=Path(weights)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('Original downloaded backbone weights changed.')
    saved=torch.load(path,map_location='cpu',weights_only=True)
    if not isinstance(saved,dict) or not any(k.startswith('classifier.') for k in saved):
        raise ValueError('Expected the original ImageNet MobileNet weight dictionary.')
    features={k.removeprefix('features.'):v for k,v in saved.items() if k.startswith('features.')}
    torch.manual_seed(seed);network=JointNetwork()
    network.backbone.load_state_dict(features,strict=True)
    return network


def transformed(circles,matrix):
    """One isotropic matrix moves both centers and their individual radii."""
    matrix=np.asarray(matrix,np.float32)
    linear=matrix[:,:2];scale=float(np.linalg.norm(linear[0]))
    if matrix.shape!=(2,3) or not np.isfinite(matrix).all() or scale<=0:
        raise ValueError('Expected a finite isotropic image transform.')
    if not np.allclose(linear@linear.T,np.eye(2)*scale*scale,rtol=1e-5,atol=1e-6):
        raise ValueError('Circle transforms must preserve aspect ratio.')
    return [dict(c,x=float(matrix[0]@[c['x'],c['y'],1]),
                   y=float(matrix[1]@[c['x'],c['y'],1]),radius=float(c['radius']*scale)) for c in circles]


def augment_image(image,circles,focus,rng):
    """Arbitrary rotations/flips/crops; constant padding has no supervision."""
    image=np.asarray(image,np.float32)
    radius=float(np.median([c['radius'] for c in circles]))
    scale=NORMALIZED_RADIUS/radius*float(rng.uniform(.75,1.25))
    angle=float(rng.uniform(-np.pi,np.pi))
    linear=scale*np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    if rng.random()<.5:linear[0]*=-1
    if rng.random()<.5:linear[1]*=-1
    location=rng.uniform(HALO+32,HALO+CORE-32,2)
    matrix=np.c_[linear,location-linear@[focus['x'],focus['y']]].astype(np.float32)
    tile=cv2.warpAffine(image,matrix,(TILE,TILE),flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,borderValue=PADDING_RGB)
    # Linear support must be wholly real source pixels; padded blends ignored.
    support=cv2.warpAffine(np.ones(image.shape[:2],np.float32),matrix,(TILE,TILE),
                           flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    valid=support>=.999
    tile=np.clip((tile-.5)*float(rng.uniform(.8,1.2))+.5,0,1)
    tile=np.clip(tile*float(rng.uniform(.78,1.22))+float(rng.uniform(-.03,.03)),0,1)
    tile=tile**float(rng.uniform(.85,1.18))
    tile=np.clip(tile*rng.uniform(.9,1.1,(1,1,3)),0,1).astype(np.float32)
    if rng.random()<.3:tile=np.repeat(tile.mean(2,keepdims=True),3,2)
    if rng.random()<.5:tile=cv2.GaussianBlur(tile,(0,0),float(rng.uniform(.2,.8)))
    tile[~valid]=PADDING_RGB
    return tile,valid,transformed(circles,matrix),matrix


def complete_targets(circles,valid,query_radius):
    """One true center per circle; all other valid core positions are negative.

    The halo is discarded just as in stitched inference. Source padding alone
    is invalid. A clipped circle whose known center remains in the real core
    still supplies center/offset/radius targets; its interior is never ignored.
    The small Gaussian softens nearby negative weighting without creating a
    second positive center. Individual supplied radii remain unchanged.
    """
    valid=np.asarray(valid,bool)
    if valid.shape!=(TILE,TILE) or not math.isfinite(query_radius) or query_radius<=0:
        raise ValueError('Expected a tile-validity mask and positive example radius.')
    size=TILE//STRIDE;yy,xx=np.mgrid[:size,:size].astype(np.float32)
    mask=valid[::STRIDE,::STRIDE].astype(np.float32)
    core=np.zeros_like(mask);core[HALO//STRIDE:(HALO+CORE)//STRIDE,HALO//STRIDE:(HALO+CORE)//STRIDE]=1
    mask*=core;heat=np.zeros_like(mask);center=np.zeros_like(mask)
    offset=np.zeros((2,size,size),np.float32);radius=np.zeros((1,size,size),np.float32)
    ids=[];clipped=[]
    for c in circles:
        if not all(math.isfinite(c[k]) for k in ('x','y','radius')) or c['radius']<=0:
            raise ValueError('User circles must have finite coordinates and positive radii.')
        x,y=int(math.floor(c['x']/STRIDE)),int(math.floor(c['y']/STRIDE))
        if not (0<=x<size and 0<=y<size) or not mask[y,x]:continue
        if center[y,x]:raise ValueError('Two marked centers fall in the same output location.')
        distance=(xx-x)**2+(yy-y)**2
        sigma=max(.65,c['radius']*.12/STRIDE)
        local=(STRIDE*xx-c['x'])**2+(STRIDE*yy-c['y'])**2 <= (.35*c['radius'])**2
        heat[local]=np.maximum(heat[local],np.exp(-distance[local]/(2*sigma*sigma)))
        heat[y,x]=1;center[y,x]=1
        offset[:,y,x]=[c['x']/STRIDE-x,c['y']/STRIDE-y]
        radius[0,y,x]=math.log(c['radius']/query_radius);ids.append(int(c['id']))
        if (c['x']-c['radius']<0 or c['y']-c['radius']<0
                or c['x']+c['radius']>=TILE or c['y']+c['radius']>=TILE):clipped.append(int(c['id']))
    return {'heat':heat[None],'mask':mask[None],'center_mask':center[None],
            'offset':offset,'radius':radius},ids,clipped


def complete_loss(predicted,target,config=CONFIG):
    """Focal center error plus direct fractional-position and log-radius error."""
    logits=predicted['logits'];heat=target['heat'];mask=target['mask']
    count=((heat==1)*mask).sum().clamp_min(1);probability=logits.sigmoid()
    positive=-(F.logsigmoid(logits)*(1-probability).pow(2)*(heat==1)*mask).sum()/count
    negative=-(F.logsigmoid(-logits)*probability.pow(2)*(1-heat).pow(4)*(heat<1)*mask).sum()/count
    centers=target['center_mask']
    offset=(F.smooth_l1_loss(predicted['offset'],target['offset'],reduction='none')*centers).sum()/(2*count)
    radius=(F.smooth_l1_loss(predicted['log_radius'],target['radius'],reduction='none')*centers).sum()/count
    total=config['center_loss_weight']*(positive+negative)+config['offset_loss_weight']*offset+config['radius_loss_weight']*radius
    return total,{key:float(value.detach()) for key,value in
                  [('total',total),('positive',positive),('negative',negative),('offset',offset),('radius',radius)]}
