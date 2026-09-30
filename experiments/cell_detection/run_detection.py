"""Run one experimental image and write a new result folder; never edit a session."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

from detector import Circle, Encoder, detect, read_image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image',type=Path)
    parser.add_argument('examples',type=Path,help='JSON containing examples and optional existing circles')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--method',choices=['template','embedding','learned'],default='template')
    parser.add_argument('--threshold',type=float,default=.75)
    parser.add_argument('--model',type=Path)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Output folder already exists; choose a new name.')
    if not 0<=args.threshold<=1:
        parser.error('Threshold must be between zero and one.')
    payload=json.loads(args.examples.read_text())
    examples=[Circle(**row) for row in payload['examples']]
    existing=[Circle(**row) for row in payload.get('existing',[])]
    head=json.loads(args.model.read_text()) if args.model else None
    if args.method=='learned' and head is None:
        parser.error('--model is required for the learned method.')
    image=read_image(args.image)
    encoder=Encoder() if args.method!='template' else None
    start=time.perf_counter()
    results=detect(image,examples,existing,args.method,args.threshold,encoder,head)
    elapsed=time.perf_counter()-start
    args.output.mkdir(parents=True,exist_ok=False)
    result={'image_sha256':hashlib.sha256(args.image.read_bytes()).hexdigest(),
            'method':args.method,'threshold':args.threshold,'seconds':elapsed,
            'examples':payload['examples'],'existing':payload.get('existing',[]),
            'suggestions':results,'note':'Experimental suggestions only. Scores are not occupancy probabilities.'}
    (args.output/'suggestions.json').write_text(json.dumps(result,indent=2)+'\n')
    overlay=cv2.cvtColor(np.uint8(image*255),cv2.COLOR_RGB2BGR)
    for circle,color in [(c,(180,180,180)) for c in existing]+[(Circle(**r['circle']),(0,200,240)) for r in results]+[(c,(60,230,80)) for c in examples]:
        cv2.circle(overlay,(round(circle.x),round(circle.y)),round(circle.radius),color,2,cv2.LINE_AA)
    cv2.imwrite(str(args.output/'suggestions.png'),overlay)
    print(json.dumps({'suggestions':len(results),'seconds':round(elapsed,3),'output':str(args.output)}))


if __name__=='__main__':main()
