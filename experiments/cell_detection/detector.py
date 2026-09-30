"""Experimental single-image detection. No dependency on Icescopy state or UI.

Coordinates and radii are always original-image pixels. Scores rank suggestions;
they are not calibrated probabilities of a well containing liquid.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math

import cv2
import numpy as np
from scipy.ndimage import maximum_filter


@dataclass(frozen=True)
class Circle:
    x: float
    y: float
    radius: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.x, self.y, self.radius)) or self.radius <= 0:
            raise ValueError('Circle coordinates must be finite and radius positive.')


def preprocess_image(raw, color_order='RGB'):
    """Normalize exactly one decoded frame; channel order must be explicit.

    Accept uint8/uint16 or finite floating-point grayscale, RGB/BGR and
    RGBA/BGRA arrays. Alpha is ignored, as with read_image. The same percentile
    scaling is used for image files and video arrays. No earlier frames enter
    this calculation.
    """
    if color_order not in ('RGB', 'BGR'):
        raise ValueError('color_order must be RGB or BGR.')
    raw = np.asarray(raw)
    if raw.dtype not in (np.uint8, np.uint16, np.float32, np.float64):
        raise ValueError('Expected uint8, uint16, float32 or float64 frame values.')
    if not raw.size or not np.isfinite(raw).all():
        raise ValueError('Frame values must be nonempty and finite.')
    if raw.ndim == 2:
        rgb = np.repeat(raw[..., None], 3, axis=2)
    elif raw.ndim == 3 and raw.shape[2] in (3, 4):
        rgb = raw[..., :3] if color_order == 'RGB' else raw[..., 2::-1]
    else:
        raise ValueError('Expected a grayscale, RGB, or RGBA image.')
    rgb = rgb.astype(np.float32)
    lo, hi = np.percentile(rgb, [1, 99])
    if hi <= lo:
        lo, hi = float(rgb.min()), float(rgb.max())
    return np.clip((rgb - lo) / max(hi - lo, 1e-6), 0, 1).astype(np.float32)


def read_image(path):
    raw = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise ValueError(f'Cannot read image: {path}')
    return preprocess_image(raw, color_order='BGR')


def validate_examples(image, examples):
    if not examples:
        raise ValueError('Mark at least one example cell first.')
    h, w = image.shape[:2]
    if any(not (0 <= c.x < w and 0 <= c.y < h) for c in examples):
        raise ValueError('Example centers must be inside the image.')


def same_object(a, b):
    # Suppress shifted circles inside one well, not just coincident centers.
    # Touching circles remain separate. This assumes examples mark the interior
    # of a droplet/well, rather than a large region enclosing several objects.
    return math.hypot(a.x-b.x, a.y-b.y) < .9 * (a.radius + b.radius)


def radial_support(gray, radius):
    """Agreement of edge directions with a circular rim, for either polarity.

    Normalize each gradient before averaging around the ring. A faint complete
    rim can then outrank a strong straight edge. The denominator floor prevents
    nearly flat pixels from contributing arbitrary directions.
    """
    smooth = cv2.GaussianBlur(gray, (0, 0), .8)
    dx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    dy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.sqrt(dx*dx + dy*dy)
    floor = max(.005, float(np.median(magnitude)))
    dx, dy = dx/(magnitude+floor), dy/(magnitude+floor)
    support = np.zeros_like(gray)
    for factor in (.85, 1.1, 1.4, 1.75):
        r = max(2., radius*factor)
        extent = int(np.ceil(r+3))
        yy, xx = np.mgrid[-extent:extent+1, -extent:extent+1].astype(np.float32)
        distance = np.sqrt(xx*xx+yy*yy)
        ring = np.exp(-.5*((distance-r)/1.2)**2)
        ring /= ring.sum()
        kx, ky = ring*xx/np.maximum(distance,1), ring*yy/np.maximum(distance,1)
        response = np.abs(cv2.filter2D(dx,-1,kx)+cv2.filter2D(dy,-1,ky))
        support = np.maximum(support,response)
    return support


def exclude_existing(circles, existing):
    return [c for c in circles if not any(same_object(c, old) for old in existing)]


def propose(image, radius, limit=1600):
    """Broad circular/spot proposals, using only the supplied example radius.

    A proposal says nothing about sample occupancy. Both contrast polarities are
    searched so freezing-induced brightness changes do not erase locations.
    """
    scale = min(1., 12. / radius)
    rgb = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    r = radius * scale
    support = radial_support(gray,r)
    peaks = []
    size = max(3, int(round(r * 1.6)) | 1)
    mask = (support == maximum_filter(support,size=size)) & (support > .12)
    ys,xs = np.nonzero(mask)
    peaks.extend((float(support[y,x]),float(x),float(y)) for y,x in zip(ys,xs))
    for factor in (.65, .9, 1.2, 1.6):
        sigma = max(1., r * factor / 1.414)
        response = np.abs(cv2.GaussianBlur(gray, (0, 0), sigma) -
                          cv2.GaussianBlur(gray, (0, 0), sigma * 1.6))
        size = max(3, int(round(r * 1.6)) | 1)
        mask = (response == maximum_filter(response, size=size)) & (response > .0015)
        ys, xs = np.nonzero(mask)
        peaks.extend((float(support[y,x]),float(x),float(y)) for y,x in zip(ys,xs))
    enhanced = cv2.createCLAHE(clipLimit=2., tileGridSize=(16, 16)).apply(np.uint8(gray * 255))
    circles = cv2.HoughCircles(enhanced, cv2.HOUGH_GRADIENT, dp=1, minDist=max(5, 1.6*r),
                               param1=90, param2=12, minRadius=max(3, round(.7*r)),
                               maxRadius=max(4, round(1.8*r)))
    if circles is not None:
        peaks.extend((float(support[min(round(y),gray.shape[0]-1),min(round(x),gray.shape[1]-1)]),
                      float(x),float(y)) for x,y,_ in circles[0])
    selected = []
    for strength, x, y in sorted(peaks, reverse=True):
        candidate = Circle(x/scale, y/scale, radius)
        # Keep alternative nearby centers for scoring; only the final detections
        # and protected user circles use the stricter overlap exclusion above.
        if not any(math.hypot(candidate.x-old.x,candidate.y-old.y)<.9*radius for old in selected):
            selected.append(candidate)
            if len(selected) == limit:
                break
    return selected


def patches(image, circles, size=96, extent=2.25):
    result = []
    for c in circles:
        side = max(5, int(round(2*c.radius*extent)) | 1)
        # Reflect padding is defined for edge cells; no wrapping to the far edge.
        left, top = int(round(c.x)) - side//2, int(round(c.y)) - side//2
        x0, y0, x1, y1 = max(0,left), max(0,top), min(image.shape[1],left+side), min(image.shape[0],top+side)
        crop = image[y0:y1, x0:x1]
        crop = cv2.copyMakeBorder(crop, max(0,-top), max(0,top+side-image.shape[0]),
                                  max(0,-left), max(0,left+side-image.shape[1]), cv2.BORDER_REFLECT_101)
        result.append(cv2.resize(crop, (size,size), interpolation=cv2.INTER_AREA))
    return np.asarray(result, dtype=np.float32).reshape(-1,size,size,3)


def unit_rows(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


def patch_descriptors(batch):
    """Keep polarity and interior appearance as well as edge shape."""
    appearance, edges, profiles = [], [], []
    yy, xx = np.mgrid[-1:1:32j, -1:1:32j]
    distance = np.sqrt(xx**2 + yy**2)
    for patch in batch:
        gray = cv2.cvtColor(cv2.resize(patch,(32,32)), cv2.COLOR_RGB2GRAY)
        smooth = cv2.GaussianBlur(gray,(0,0),.7)
        dx = cv2.Sobel(smooth,cv2.CV_32F,1,0,ksize=3)
        dy = cv2.Sobel(smooth,cv2.CV_32F,0,1,ksize=3)
        edge = np.sqrt(dx*dx+dy*dy)
        appearance.append((smooth-smooth.mean()).ravel())
        edges.append((edge-edge.mean()).ravel())
        p=[]
        for low,high in zip(np.linspace(0,1.3,14)[:-1],np.linspace(0,1.3,14)[1:]):
            values=smooth[(distance>=low)&(distance<high)]
            p.extend([float(values.mean()),float(values.std())])
        profiles.append(p)
    return unit_rows(np.array(appearance,dtype=np.float32)), unit_rows(np.array(edges,dtype=np.float32)), np.array(profiles,dtype=np.float32)


class Encoder:
    """Optional, CPU-only small pretrained network. Imported only for ML tests."""
    def __init__(self, threads=4):
        import torch
        from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
        torch.set_num_threads(threads)
        self.torch = torch
        self.model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1).eval()

    def input_tensor(self, batch):
        """Exact shared network input for original inference and fine-tuning."""
        t=self.torch
        values=np.asarray(batch,dtype=np.float32).copy()
        lo=np.percentile(values,1,axis=(1,2,3),keepdims=True)
        hi=np.percentile(values,99,axis=(1,2,3),keepdims=True)
        values=np.clip((values-lo)/np.maximum(hi-lo,1e-5),0,1).astype(np.float32)
        x=t.from_numpy(values.transpose(0,3,1,2)).contiguous()
        return (x-t.tensor([.485,.456,.406])[None,:,None,None])/t.tensor([.229,.224,.225])[None,:,None,None]

    def encode(self, batch):
        outputs=[]
        t=self.torch
        with t.inference_mode():
            for start in range(0,len(batch),64):
                x=self.input_tensor(batch[start:start+64])
                y=self.model.features(x)
                y=self.model.avgpool(y).flatten(1)
                outputs.append(y.numpy())
        return unit_rows(np.concatenate(outputs))


def feature_bank(image, circles, encoder=None):
    batch=patches(image,circles)
    gray,edges,profiles=patch_descriptors(batch)
    result={'gray':gray,'edges':edges,'profiles':profiles}
    if encoder is not None:
        result['embedding']=encoder.encode(batch)
    return result


def pair_features(candidates, examples):
    gray=candidates['gray'] @ examples['gray'].T
    edges=candidates['edges'] @ examples['edges'].T
    a,b=candidates['profiles'],examples['profiles']
    delta=np.abs(a[:,None,:]-b[None,:,:])
    fields=[gray,edges,np.mean(delta,axis=2),np.max(delta,axis=2)]
    if 'embedding' in candidates:
        fields.append(candidates['embedding'] @ examples['embedding'].T)
    return np.stack(fields,axis=2)


def scores(candidates, examples, method='template', head=None):
    pair=pair_features(candidates,examples)
    if method=='template':
        return np.max(.75*np.maximum(pair[:,:,0],0)+.25*np.maximum(pair[:,:,1],0),axis=1)
    if method=='embedding':
        return np.max(pair[:,:,-1],axis=1)
    if method=='learned':
        if head is None:
            raise ValueError('A trained pair classifier is required.')
        x=(pair-np.asarray(head['mean']))/np.asarray(head['scale'])
        logits=x@np.asarray(head['weights'])+head['bias']
        return np.max(1/(1+np.exp(-np.clip(logits,-30,30))),axis=1)
    raise ValueError('Unknown method.')


def detect(image, examples, existing=(), method='template', threshold=.75, encoder=None, head=None):
    validate_examples(image,examples)
    protected=list(existing)+list(examples)
    radius=float(np.median([c.radius for c in examples]))
    # Known cells do not need image features or classification. This also
    # protects every prior/manual cell, independently of example selection.
    candidates=exclude_existing(propose(image,radius),protected)
    if not candidates:
        return []
    bank=feature_bank(image,candidates,encoder)
    support=feature_bank(image,examples,encoder)
    values=scores(bank,support,method,head)
    ranked=sorted(zip(candidates,values),key=lambda pair:float(pair[1]),reverse=True)
    accepted=[]
    for circle,score in ranked:
        if score<threshold or any(same_object(circle,c) for c in protected):
            continue
        if not any(same_object(circle,c) for c,_ in accepted):
            accepted.append((circle,float(score)))
    return [{'circle':asdict(c),'score':s} for c,s in accepted]
