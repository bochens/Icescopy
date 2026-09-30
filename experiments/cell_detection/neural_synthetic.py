"""Randomized procedural cold-stage appearances for synthetic-only training.

Published apparatus images guide geometry and optical modes, never supply
pixels, image patches or backgrounds. This is an approximation of appearance,
not a validated model of liquid optics. Labels are assigned before rendering.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from structured_scenes import noise_field, scene_geometry


FAMILIES=('pcr','grid','disc','pocket','stage')
SEEDS={split:{family:[100000+10000*i+offset+j for j in range(count)]
              for i,family in enumerate(FAMILIES)}
       for split,offset,count in [('fit',100,4),('validation',200,2),('calibration',300,2)]}
REFERENCES=[
    'https://amt.copernicus.org/articles/14/3131/2021/',
    'https://amt.copernicus.org/articles/12/6865/2019/',
    'https://amt.copernicus.org/articles/8/689/2015/amt-8-689-2015.pdf',
    'https://cif-cold-stage.github.io/overview/',
]


def geometry(family):
    if family!='stage':return scene_geometry(family)
    return (640,850),21,[(90+95*c,85+91*r,r,c) for r in range(6) for c in range(8)]


def scene_style(split,family,index):
    """Balance optical modes and neutral scenes even in the two-scene splits."""
    mode='transmitted' if index%2==0 else 'reflected'
    neutral=(index in (0,3)) if split=='fit' else (index==(FAMILIES.index(family)+('calibration'==split))%2)
    return mode,neutral


def render(family,seed,*,optical_mode=None,neutral=False):
    rng=np.random.default_rng(seed)
    shape,holder_radius,places=geometry(family);h,w=shape
    # Occupancy/positions use a separate random stream and are assigned before
    # any rendering, so changing illumination cannot change which wells fill.
    layout_rng=np.random.default_rng(seed+7000000)
    layout=[]
    for slot,(cx,cy,row,col) in enumerate(places):
        cx+=float(layout_rng.uniform(-1.3,1.3));cy+=float(layout_rng.uniform(-1.3,1.3))
        if family=='stage':cx+=float(layout_rng.uniform(-10,10));cy+=float(layout_rng.uniform(-10,10))
        filled=bool(layout_rng.random()<.70)
        if family in ('pcr','grid') and row==2:filled=False
        frozen=filled and bool(layout_rng.random()<.35)
        layout.append((slot,cx,cy,row,col,filled,frozen))
    mode=optical_mode or rng.choice(['transmitted','reflected'])
    if mode not in ('transmitted','reflected'):raise ValueError('Unknown optical mode.')
    ratio=float(rng.uniform(*{'pcr':(.44,.69),'grid':(.38,.64),'disc':(.37,.62),
                             'pocket':(.16,.29),'stage':(.75,.95)}[family]))
    fluid_radius=holder_radius*ratio
    angle=float(rng.uniform(-np.pi,np.pi))
    material=float(rng.uniform(.10,.27) if mode=='transmitted' else rng.uniform(.36,.67))
    recess=float(rng.uniform(.24,.43) if mode=='transmitted' else rng.uniform(.07,.23))
    rim_contrast=float(rng.uniform(.045,.18))
    meniscus=float(rng.uniform(.05,.22))
    color=rng.uniform(.65,1.22,3).astype(np.float32)
    color/=color.max()
    if neutral:color[:]=1
    yy,xx=np.mgrid[:h,:w]
    base=(material+.065*(xx/w-.5)+.035*np.cos(yy/h*np.pi)+noise_field(rng,shape,2,.014)).astype(np.float32)
    base+=noise_field(rng,shape,18,.016)
    if family=='disc':
        d=np.hypot(xx-w/2,yy-h/2);edge=np.exp(-.5*((d-391)/2.5)**2)
        base[d>397]=material*.45;base+=rim_contrast*edge
    elif family!='stage':
        border=np.minimum.reduce([xx-43,w-42-xx,yy-39,h-38-yy])
        base[border<0]=material*.45
        base+=rim_contrast*np.exp(-.5*((border-7)/2.7)**2)
    else:
        # Slide/oil-like, directionally lit texture without using real pixels.
        base+=.03*np.sin(xx*.012+yy*.005)+noise_field(rng,shape,.7,.009)
    targets=[];negatives=[];objects=[]
    for slot,cx,cy,row,col,filled,frozen in layout:
        half=int(np.ceil(holder_radius*1.7))
        x0,x1=max(0,int(cx)-half),min(w,int(cx)+half+1)
        y0,y1=max(0,int(cy)-half),min(h,int(cy)+half+1)
        py,px=np.mgrid[y0:y1,x0:x1].astype(np.float32)
        u,v=(px-cx)/holder_radius,(py-cy)/holder_radius
        distance=np.hypot(u,v);theta=np.arctan2(v,u)
        view=base[y0:y1,x0:x1]
        if family!='stage':
            inside=recess+.03*distance+.017*np.cos(theta-angle)
            opening=np.clip((1-distance)*25,0,1)
            view[:]=view*(1-opening)+inside*opening
            ring=np.exp(-.5*((distance-1.02)/.052)**2)
            view+=rim_contrast*ring*(.35+.7*np.cos(theta-angle))
            view+=rng.uniform(.015,.06)*np.exp(-.5*((distance-.78)/.045)**2)
            if family=='pcr':
                # Nested tube bottom and faint rounded-square interwell wall.
                square=(np.abs(u)**6+np.abs(v)**6)**(1/6)
                view+=.035*np.exp(-.5*((square-1.31)/.05)**2)
                view-=.025*np.exp(-distance*distance/.30)
        drop_x=cx+fluid_radius*.035*np.cos(angle);drop_y=cy+fluid_radius*.035*np.sin(angle)
        qx,qy=(px-drop_x)/fluid_radius,(py-drop_y)/fluid_radius
        q=np.hypot(qx,qy);phi=np.arctan2(qy,qx)
        if filled:
            if mode=='transmitted':
                level=float(rng.uniform(.57,.83) if not frozen else rng.uniform(.15,.37))
            elif frozen:
                # Reflected frost may brighten, or become darker and lose glint.
                level=float(rng.uniform(.47,.77) if rng.random()<.72 else rng.uniform(.11,.26))
            else:level=float(rng.uniform(.09,.29))
            surface=level+.025*q+.018*np.cos(phi-angle)*q
            local_angle=angle+float(rng.uniform(-.35,.35))
            highlight=float(rng.uniform(.06,.28))
            if rng.random()<.12:highlight=float(rng.uniform(.30,.48))
            if not frozen:
                # Rounded liquid surface: radial shading plus an off-center
                # specular crescent/glint, not a uniform filled disk.
                surface+=float(rng.uniform(-.06,.08))*np.exp(-q*q/.42)
                hx,hy=.42*np.cos(local_angle),.42*np.sin(local_angle)
                width=float(rng.uniform(.025,.12))
                surface+=highlight*np.exp(-((qx-hx)**2+(qy-hy)**2)/width)
                surface+=.03*np.cos(phi-local_angle)*np.exp(-.5*((q-.63)/.18)**2)
            if frozen:
                texture=rng.normal(0,.024,q.shape).astype(np.float32)
                texture=cv2.GaussianBlur(texture,(0,0),.45)
                surface+=texture+.035*np.exp(-q*q/.35)
            opening=np.clip((1-q)*20,0,1)
            view[:]=view*(1-opening)+surface*opening
            ring=np.exp(-.5*((q-.90)/.07)**2)
            crescent=np.clip(np.cos(phi-local_angle),0,1)**5
            view+=ring*(meniscus*crescent+.016)
            view-=.027*np.exp(-.5*((q-1.01)/.04)**2)
            if mode=='transmitted' and not frozen:
                view-=.19*np.exp(-q*q/.004)  # Tiny dark transmitted-light pinpoint.
            elif not frozen:
                view+=.14*np.exp(-((qx-.38*np.cos(angle))**2+(qy-.38*np.sin(angle))**2)/.022)
            else:
                view+=rng.uniform(.015,.07)*np.exp(-.5*((q-1.12)/.09)**2)
        elif family=='pcr':
            # Empty tube bottoms remain hard, plausible round negative objects.
            view+=.045*np.exp(-.5*((q-.88)/.10)**2)
            view-=.035*np.exp(-q*q/.5)
        elif family=='stage':
            # Smaller holes on the stage, not same-size manufactured droplets.
            small=fluid_radius*float(rng.uniform(.24,.56))
            hole=np.hypot(px-cx,py-cy)/small
            view-=rng.uniform(.07,.16)*np.clip((1-hole)*18,0,1)
            view+=.035*np.exp(-.5*((hole-1)/.06)**2)
        entry={'x':float(drop_x),'y':float(drop_y),'radius':float(fluid_radius*.78),
               'slot':slot,'row':row+1,'column':col+1,
               'state':'filled_frozen' if frozen else 'filled_liquid' if filled else 'empty',
               'holder_radius':float(holder_radius),'fluid_radius':float(fluid_radius)}
        (targets if filled else negatives).append(entry);objects.append(entry)
    # Modest reflections cross actual targets while retaining the liquid rim.
    crossed=objects[int(rng.integers(len(objects)))]
    slope=float(rng.uniform(-.8,.8))
    line=(yy-crossed['y'])-slope*(xx-crossed['x'])
    base+=float(rng.uniform(.025,.10))*np.exp(-.5*(line/rng.uniform(.8,2.2))**2)
    gx,gy=rng.uniform(.25,.8)*w,rng.uniform(.2,.8)*h
    base+=float(rng.uniform(.025,.18))*np.exp(-((xx-gx)**2/(w*.18)**2+(yy-gy)**2/(h*.19)**2))
    base*=.80+.27*xx/w+.06*np.sin(yy/h*np.pi)
    # Fit rotated image inside the canvas to retain every annotated object.
    rotation=float(rng.uniform(-20,20))
    affine=cv2.getRotationMatrix2D((w/2,h/2),rotation,.82)
    rotation_matrix=np.vstack([affine,[0,0,1]])
    src=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
    dst=src+np.float32([[rng.uniform(0,.035*w),rng.uniform(0,.03*h)],
                         [rng.uniform(-.04*w,0),rng.uniform(0,.03*h)],
                         [rng.uniform(-.04*w,0),rng.uniform(-.03*h,0)],
                         [rng.uniform(0,.035*w),rng.uniform(-.03*h,0)]])
    transform=cv2.getPerspectiveTransform(src,dst)@rotation_matrix
    base=cv2.warpPerspective(base,transform,(w,h),borderMode=cv2.BORDER_CONSTANT,borderValue=material*.45)
    blur=float(rng.uniform(.35,1.8))
    base=cv2.GaussianBlur(base,(0,0),blur)
    base+=rng.normal(0,float(rng.uniform(.002,.01)),shape).astype(np.float32)
    rgb=np.clip(base[:,:,None]*color[None,None,:],0,1)
    def mapped(entry):
        x,y,r=entry['x'],entry['y'],entry['radius']
        p=cv2.perspectiveTransform(np.float32([[[x,y],[x+1,y],[x,y+1]]]),transform)[0]
        axes=np.linalg.svd(np.column_stack([p[1]-p[0],p[2]-p[0]]),compute_uv=False)*r
        return dict(entry,x=float(p[0,0]),y=float(p[0,1]),ellipse_axes=axes.tolist(),radius=float(axes.min()))
    targets=[dict(mapped(t),id=i) for i,t in enumerate(targets)];negatives=[mapped(t) for t in negatives]
    # All trials within a scene use one inscribed measurement radius. True
    # transformed ellipse axes remain recorded, so first-target size cannot
    # silently supply information unavailable from another selected example.
    common_radius=min(t['radius'] for t in targets+negatives)
    targets=[dict(t,radius=common_radius) for t in targets]
    negatives=[dict(t,radius=common_radius) for t in negatives]
    metadata={'family':family,'seed':seed,'optical_mode':mode,'neutral_grayscale':bool(neutral),'fluid_well_radius_ratio':ratio,
              'illumination_angle':angle,'material_brightness':material,'recess_brightness':recess,
              'rim_contrast':rim_contrast,'meniscus_contrast':meniscus,'color_rgb':color.tolist(),
              'blur_sigma':blur,'rotation_degrees':rotation,'transform':transform.tolist(),
              'measurement_radius_rule':'One common inscribed fluid measurement radius per scene; transformed local ellipse axes retained.',
              'references':REFERENCES,'pixels':'Entirely procedural; no published or real recording pixels.'}
    return cv2.cvtColor(np.uint16(rgb*65535),cv2.COLOR_RGB2BGR),targets,negatives,metadata


def contacts(scenes,folder):
    canvases=[]
    for details in (False,True):
        canvas=np.full((740,1800,3),245,np.uint8)
        for i,scene in enumerate(scenes):
            raw=cv2.imread(scene['source'],cv2.IMREAD_UNCHANGED)
            image=np.uint8(raw/257)
            if details:
                center=scene['targets'][len(scene['targets'])//2]
                half=100 if scene['rendering']['family']!='pocket' else 125
                x,y=round(center['x']),round(center['y'])
                image=image[max(0,y-half):min(image.shape[0],y+half),max(0,x-half):min(image.shape[1],x+half)]
            else:
                for kind,color in [('targets',(70,240,70)),('negatives',(225,70,225))]:
                    for c in scene[kind]:cv2.circle(image,(round(c['x']),round(c['y'])),round(c['radius']),color,1,cv2.LINE_AA)
            tile=cv2.resize(image,(350,315),interpolation=cv2.INTER_AREA)
            row,col=divmod(i,5);x0,y0=col*360,row*370
            canvas[y0+47:y0+362,x0+5:x0+355]=tile
            text=f"{scene['rendering']['family']} {scene['rendering']['optical_mode']}"
            cv2.putText(canvas,text,(x0+5,y0+18),cv2.FONT_HERSHEY_SIMPLEX,.48,(25,25,25),1,cv2.LINE_AA)
            cv2.putText(canvas,f"{len(scene['targets'])} filled / {len(scene['negatives'])} empty",(x0+5,y0+37),cv2.FONT_HERSHEY_SIMPLEX,.45,(25,25,25),1,cv2.LINE_AA)
        path=folder/('contact-details.jpg' if details else 'contact-labels.jpg')
        cv2.imwrite(str(path),canvas,[cv2.IMWRITE_JPEG_QUALITY,95]);canvases.append(str(path.resolve()))
    return canvases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preview',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    scenes=[]
    plan=([('preview',family,SEEDS['fit'][family][0],mode,mode=='transmitted') for mode in ('transmitted','reflected') for family in FAMILIES]
          if args.preview else [(split,family,seed,*scene_style(split,family,i)) for split in SEEDS for family in FAMILIES for i,seed in enumerate(SEEDS[split][family])])
    for split,family,seed,mode,neutral in plan:
        raw,targets,negatives,metadata=render(family,seed,optical_mode=mode,neutral=neutral)
        name=f'{split}-{family}-{seed}'+(f'-{mode}' if mode else '')
        path=args.output/(name+'.png')
        if not cv2.imwrite(str(path),raw):raise IOError('Cannot write generated image.')
        scenes.append({'id':name,'recording':f'neural-synthetic-{family}-{seed}',
                       'group':f'neural-synthetic-{family}-{seed}','source':str(path.resolve()),
                       'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'width':raw.shape[1],'height':raw.shape[0],
                       'split':split,'targets':targets,'negatives':negatives,'complete_labels':True,
                       'rendering':metadata,'label_status':'Procedural filled/empty assignment before rendering; approximate cold-stage appearance.'})
    (args.output/'labels.json').write_text(json.dumps({'seeds':SEEDS,'scenes':scenes,'references':REFERENCES},indent=2)+'\n')
    if args.preview:print(json.dumps({'contacts':contacts(scenes,args.output),'scenes':len(scenes)}))
    else:print(json.dumps({'scenes':len(scenes),'counts':{split:{'filled':sum(len(s['targets']) for s in scenes if s['split']==split),'empty':sum(len(s['negatives']) for s in scenes if s['split']==split)} for split in SEEDS}}))


if __name__=='__main__':main()
