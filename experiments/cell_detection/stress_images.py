"""Create controlled artificial pictures for diagnostics, never real validation.

The labels describe the renderer's shapes, not a physical liquid measurement.
Each variant uses the same scene. Variants must stay together in any data split.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def render(seed=731, blur=0., color=False, illumination=False, dark=False):
    rng=np.random.default_rng(seed)
    h,w=420,560
    yy,xx=np.mgrid[:h,:w]
    base=.48 + (.12*xx/w-.12*yy/h if illumination else np.zeros((h,w)))
    gray=base.copy()
    labels=[];distractors=[]
    # Keep paired filled spots, unfilled rings, and smaller dark cutouts spread
    # across the picture. No target count or grid is supplied to the detector.
    kinds=np.array(['filled']*16+['empty_ring']*16+['small_hole']*16)
    rng.shuffle(kinds)
    for index,kind in enumerate(kinds):
        x=55+(index%8)*64+float(rng.uniform(-5,5))
        y=48+(index//8)*64+float(rng.uniform(-5,5))
        r=float(rng.uniform(9,11))
        distance=np.hypot(xx-x,yy-y)
        if kind=='filled':
            sign=-1 if dark else 1
            gray+=sign*.20*np.exp(-.5*(distance/(r*.76))**6)
            gray-=.055*np.exp(-.5*((distance-r)/1.1)**2)
            labels.append(dict(id=len(labels),x=x,y=y,radius=10))
        elif kind=='empty_ring':
            gray-=.14*np.exp(-.5*((distance-r)/1.1)**2)
            distractors.append(dict(kind=kind,x=x,y=y,radius=r))
        else:
            gray-=.25*np.exp(-.5*(distance/(r*.45))**6)
            distractors.append(dict(kind=kind,x=x,y=y,radius=r*.55))
    if blur:
        gray=cv2.GaussianBlur(gray.astype(np.float32),(0,0),blur)
    gray+=rng.normal(0,.012,gray.shape)
    gray=np.clip(gray,0,1)
    if color:
        # Different channel gains and a broad colored illumination gradient.
        rgb=np.stack([gray*.72,gray*.9,gray],axis=2)
        rgb[:,:,0]+=.08*xx/w
        raw=cv2.cvtColor(np.uint8(np.clip(rgb,0,1)*255),cv2.COLOR_RGB2BGR)
    else:
        raw=np.uint16(gray*65535)
    return raw,labels,distractors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    settings=[('clear_gray',{}),('blur_gray',{'blur':2.2}),
              ('uneven_color',{'color':True,'illumination':True}),
              ('blur_uneven_color',{'color':True,'illumination':True,'blur':2.2}),
              ('dark_gray',{'dark':True}),
              ('dark_blur_color',{'dark':True,'color':True,'illumination':True,'blur':2.2})]
    scenes=[]
    for name,parameters in settings:
        raw,targets,distractors=render(**parameters)
        path=args.output/(name+'.png')
        if not cv2.imwrite(str(path),raw):raise IOError('Failed to write synthetic picture.')
        scenes.append(dict(id='synthetic-'+name,recording='synthetic-scene-731',source=str(path.resolve()),
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest(),width=raw.shape[1],height=raw.shape[0],
                           split='synthetic_stress_only',targets=targets,distractors=distractors,complete_labels=True,
                           label_status='Artificial shapes: 16 filled spots, 16 empty rings and 16 smaller dark holes. All variants share one layout; these are diagnostics, not independent experiments or proof of real liquid occupancy.',
                           rendering=parameters))
    (args.output/'labels.json').write_text(json.dumps(dict(scenes=scenes),indent=2)+'\n')
    print(args.output/'labels.json')


if __name__=='__main__':main()
