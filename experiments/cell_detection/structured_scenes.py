"""Controlled image simulations of trays and perforated holders.

Geometry and occupancy are assigned before rendering or detection. These are
optical approximations, not validated liquid optics or independent experiments.
Variants with the same family and seed share a split group.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def noise_field(rng, shape, sigma, amplitude):
    values=rng.normal(0,1,shape).astype(np.float32)
    values=cv2.GaussianBlur(values,(0,0),sigma)
    return amplitude*values/max(float(values.std()),1e-6)


def stamp_text(image,text,point):
    # OpenCV 5 text drawing accepts 8-bit destinations; composite the mask into
    # the floating-point scene without quantizing the scientific image itself.
    mask=np.zeros(image.shape,np.uint8)
    cv2.putText(mask,text,point,cv2.FONT_HERSHEY_SIMPLEX,.4,255,1,cv2.LINE_AA)
    alpha=mask.astype(np.float32)/255
    image[:]=image*(1-alpha)+.15*alpha


def layer(image, cx, cy, radius, kind, filled, frozen, rng):
    """Render holder rim and, independently, an interior droplet or liquid surface."""
    half=int(np.ceil(radius*1.65))
    x0,x1=max(0,int(cx)-half),min(image.shape[1],int(cx)+half+1)
    y0,y1=max(0,int(cy)-half),min(image.shape[0],int(cy)+half+1)
    yy,xx=np.mgrid[y0:y1,x0:x1].astype(np.float32)
    u,v=(xx-cx)/radius,(yy-cy)/radius
    d=np.hypot(u,v);angle=np.arctan2(v,u)
    view=image[y0:y1,x0:x1]
    light=np.cos(angle-2.1)
    rim=np.exp(-.5*((d-1.04)/.055)**2)
    if kind=='pcr':
        # A tube opening, bevel, tapered interior, and smaller rounded bottom.
        inside=.20+.07*d+.02*v
        inside+=.045*np.exp(-.5*((d-.77)/.055)**2)
        opening=np.clip((1.0-d)*25,0,1)
        view[:]=view*(1-opening)+inside*opening
        view+=rim*(.12+.14*light)
        view-=.085*np.exp(-.5*((np.hypot(u-.07,v-.12)-1.10)/.09)**2)
        fluid_r=.59; center_shift=.05
    elif kind in ('grid','disc'):
        # Machined circular cutout with a visible bevel and dark recess.
        inside=.045+.035*d+.012*np.cos(angle)
        opening=np.clip((1.0-d)*30,0,1)
        view[:]=view*(1-opening)+inside*opening
        view+=rim*(.03+.13*light)
        view+=.025*np.exp(-.5*((d-.87)/.035)**2)
        fluid_r=.52; center_shift=.07
    else:
        # Broad circular pocket containing a much smaller central droplet.
        inside=.43+.035*u-.025*v
        opening=np.clip((1.0-d)*25,0,1)
        view[:]=view*(1-opening)+inside*opening
        view-=.11*np.exp(-.5*((d-.92)/.035)**2)
        view+=rim*(.04+.10*light)
        fluid_r=.205; center_shift=.02
    drop_x=cx+center_shift*radius+rng.uniform(-.035,.035)*radius
    drop_y=cy+.045*radius+rng.uniform(-.035,.035)*radius
    qx,qy=(xx-drop_x)/(radius*fluid_r),(yy-drop_y)/(radius*fluid_r)
    q=np.hypot(qx,qy)
    if filled:
        edge=np.clip((1-q)*18,0,1)
        if frozen:
            interior=.58+.10*np.exp(-q*q)+rng.normal(0,.012,q.shape)
        elif kind=='pocket':
            # Off-axis illumination creates bright and dark sides of the drop.
            interior=.15+.61*np.clip(.5+.65*qx-.4*qy,0,1)
        else:
            interior=.12+.025*q
        view[:]=view*(1-edge)+interior*edge
        if not frozen:
            meniscus=np.exp(-.5*((q-.90)/.08)**2)
            crescent=np.clip(np.cos(np.arctan2(qy,qx)-1.2),0,1)**5
            view+=meniscus*(.025+.56*crescent)
            view+=.035*np.exp(-.5*((q-.44)/.07)**2)
    else:
        # Empty tubes still have a rounded base; cutouts have only their wall.
        # Never replace empty targets with obviously unrelated symbol shapes.
        if kind=='pcr':
            view-=.05*np.exp(-q*q/.8)
            view+=.035*np.exp(-.5*((q-.92)/.09)**2)
    return drop_x,drop_y,radius*fluid_r*.80


def scene_geometry(family):
    if family=='pcr':
        shape=(740,1040);radius=27
        places=[(112+c*73,113+r*72,r,c) for r in range(8) for c in range(12)]
    elif family=='grid':
        shape=(760,980);radius=27
        places=[(125+c*79,130+r*80,r,c) for r in range(7) for c in range(10)]
    elif family=='disc':
        shape=(900,900);radius=29
        places=[(120+c*67+(r%2)*33.5,100+r*59,r,c) for r in range(13) for c in range(11)
                if np.hypot(120+c*67+(r%2)*33.5-450,100+r*59-450)<335]
    elif family=='pocket':
        shape=(560,690);radius=46
        places=[(122+c*112,100+r*116,r,c) for r in range(4) for c in range(4)]
    else:raise ValueError('Unknown holder family.')
    return shape,radius,places


def render(family,seed,*,condition='clear'):
    rng=np.random.default_rng(seed)
    shape,radius,places=scene_geometry(family);h,w=shape
    yy,xx=np.mgrid[:h,:w]
    image=(.10+noise_field(rng,shape,6,.013)).astype(np.float32)
    if family=='disc':
        distance=np.hypot(xx-w/2,yy-h/2)
        mask=distance<397
        body=.44+.05*xx/w-.04*yy/h+noise_field(rng,shape,.8,.018)
        body+=.14*np.exp(-.5*((distance-390)/2.)**2)
    else:
        mask=(xx>45)&(xx<w-42)&(yy>42)&(yy<h-38)
        body=.48+.07*xx/w-.06*yy/h+noise_field(rng,shape,1.3,.012)
        # Tray border / metal holder edge, with directional illumination.
        edge=np.minimum.reduce([xx-45,w-42-xx,yy-42,h-38-yy])
        body+=.13*np.exp(-.5*((edge-7)/2.5)**2)
        body-=.08*np.exp(-.5*((edge-17)/3.)**2)
    image[mask]=body[mask]
    # Gentle large-scale surface texture remains separate from cell occupancy.
    image+=noise_field(rng,shape,20,.015)
    targets=[];negatives=[];objects=[]
    for slot,(cx,cy,row,col) in enumerate(places):
        filled=bool(rng.random()>.27)
        if family in ('pcr','grid'):
            if row==0:filled=True
            if row==2:filled=False  # A complete empty row defeats grid-fill shortcuts.
        if family=='pocket' and (row,col)==(1,3):filled=True
        frozen=filled and rng.random()<.22
        x,y,r=layer(image,cx,cy,radius,family,filled,frozen,rng)
        entry=dict(x=float(x),y=float(y),radius=float(r),slot=slot,row=row+1,column=col+1,
                   state='filled_frozen' if frozen else 'filled_liquid' if filled else 'empty')
        (targets if filled else negatives).append(entry)
        objects.append(dict(entry,holder_x=float(cx),holder_y=float(cy),holder_radius=radius))
    if family in ('pcr','grid'):
        # Labels, seams and edge markings make background proposals meaningful.
        for row in range(8 if family=='pcr' else 7):
            stamp_text(image,chr(65+row),(65,120+row*(72 if family=='pcr' else 80)))
        for col in range(12 if family=='pcr' else 10):
            stamp_text(image,str(col+1),(104+col*(73 if family=='pcr' else 79),73))
    transform=np.eye(3,dtype=np.float64)
    if condition!='clear':
        # A scratch / reflection crosses a filled object rather than only background.
        crossed=next((o for o in objects if o['row']==2 and o['column']==4),objects[len(objects)//2])
        line=(yy-crossed['holder_y'])-.52*(xx-crossed['holder_x'])
        image+=.31*np.exp(-.5*(line/1.2)**2)
        image*=.69+.44*(xx/w)+.12*np.sin(yy/h*np.pi)
        image+=.34*np.exp(-((xx-w*.83)**2/(w*.12)**2+(yy-h*.20)**2/(h*.28)**2))
        src=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
        dst=np.float32([[w*.055,h*.025],[w*.97,h*.07],[w*.91,h*.96],[w*.02,h*.91]])
        transform=cv2.getPerspectiveTransform(src,dst)
        # Constant background avoids inventing reflected, unlabeled tray wells
        # outside the photographed holder when perspective exposes the border.
        image=cv2.warpPerspective(image,transform,(w,h),borderMode=cv2.BORDER_CONSTANT,borderValue=.09)
        image=cv2.GaussianBlur(image,(0,0),1.4 if condition=='glare' else 2.5)
    image+=rng.normal(0,.006,image.shape).astype(np.float32)
    image=np.clip(image,0,1)
    if family in ('grid','disc') and condition!='gray_blur':
        rgb=np.stack([image*.62,image*.82,image],axis=2)
        raw=cv2.cvtColor(np.uint8(np.clip(rgb,0,1)*255),cv2.COLOR_RGB2BGR)
    else:raw=np.uint16(image*65535)
    # Map annotations with the exact same perspective transform. Use an inscribed
    # measurement circle (smallest local scale), and retain ellipse axes for review.
    def mapped(entry):
        x,y,r=entry['x'],entry['y'],entry['radius']
        points=np.float32([[[x,y],[x+1,y],[x,y+1]]])
        p=cv2.perspectiveTransform(points,transform)[0]
        jac=np.column_stack([p[1]-p[0],p[2]-p[0]])
        axes=np.linalg.svd(jac,compute_uv=False)*r
        return dict(entry,x=float(p[0,0]),y=float(p[0,1]),radius=float(axes.min()),ellipse_axes=axes.tolist())
    targets=[dict(mapped(t),id=i) for i,t in enumerate(targets)]
    negatives=[mapped(t) for t in negatives]
    return raw,targets,negatives,dict(family=family,seed=seed,condition=condition,rows=max(p[2] for p in places)+1,
                                    slots=len(places),transform=transform.tolist(),description='Procedural holder geometry and approximate appearance. Not measured liquid optics.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    scenes=[]
    for family,seed in [('pcr',1103),('grid',2207),('disc',3301),('pocket',4409)]:
        for condition,current_seed in [('clear',seed),('glare',seed),('gray_blur',seed+101)]:
            name=f'{family}-{condition}'
            raw,targets,negatives,metadata=render(family,current_seed,condition=condition)
            source=args.output/(name+'.png')
            if not cv2.imwrite(str(source),raw):raise IOError('Image write failed.')
            scenes.append(dict(id=name,recording=f'simulated-{family}-{current_seed}',source=str(source.resolve()),
                               sha256=hashlib.sha256(source.read_bytes()).hexdigest(),width=raw.shape[1],height=raw.shape[0],
                               split='structured_synthetic_diagnostic',targets=targets,negatives=negatives,complete_labels=True,
                               label_status=f'Simulated {family} holder: {len(targets)} filled positions, {len(negatives)} empty positions. Labels come from rendering, not detector output. Clear and glare views sharing a seed belong to the same scene group. Synthetic results do not establish accuracy on real trays.',
                               rendering=metadata))
            print(name,len(targets),'filled;',len(negatives),'empty',flush=True)
    (args.output/'labels.json').write_text(json.dumps(dict(scenes=scenes),indent=2)+'\n')


if __name__=='__main__':main()
