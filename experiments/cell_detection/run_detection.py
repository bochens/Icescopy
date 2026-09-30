"""Run one experimental image and write a new result folder; never edit a session."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

from detector import Circle, Encoder, preprocess_image
from single_frame import detect_current_frame


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image',type=Path)
    parser.add_argument('examples',type=Path,help='JSON containing examples or saved example_ids, plus optional existing circles/current_positions')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--method',choices=['template','embedding','learned','fast'],default='template')
    parser.add_argument('--threshold',type=float,help='Default .75 for original methods; recorded calibration threshold for fast')
    parser.add_argument('--model',type=Path)
    parser.add_argument('--state-in',type=Path,help='Previously saved state.json; IDs and all known cells are retained')
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Output folder already exists; choose a new name.')
    if args.threshold is not None and not 0<=args.threshold<=1:
        parser.error('Threshold must be between zero and one.')
    try:
        payload=json.loads(args.examples.read_text())
        examples=[Circle(**row) for row in payload.get('examples',[])]
        existing=[Circle(**row) for row in payload.get('existing',[])]
        state=json.loads(args.state_in.read_text()) if args.state_in else None
        alternate=None
        if args.method=='fast':
            from fast_model import detect as alternate, load_model
            if args.model is None:raise ValueError('--model is required for the fast method.')
            head=load_model(args.model)
        else:
            head=json.loads(args.model.read_text()) if args.model else None
            if args.method=='learned' and head is None:
                raise ValueError('--model is required for the learned method.')
        if args.threshold is None:args.threshold=head['threshold'] if args.method=='fast' else .75
        raw=cv2.imread(str(args.image),cv2.IMREAD_UNCHANGED)
        if raw is None:raise ValueError(f'Cannot read image: {args.image}')
        image=preprocess_image(raw,color_order='BGR')
        encoder=Encoder() if args.method in ('embedding','learned') else None
        start=time.perf_counter()
        selected=detect_current_frame(raw,examples,state=state,existing=existing,
                                     example_ids=payload.get('example_ids',[]),
                                     current_positions=payload.get('current_positions'),
                                     remove_ids=payload.get('remove_ids',[]),color_order='BGR',
                                     method=args.method,threshold=args.threshold,encoder=encoder,head=head,detector=alternate)
        elapsed=time.perf_counter()-start
    except (ValueError,TypeError,KeyError,OSError) as error:
        parser.error(str(error))
    results=selected['suggestions']
    args.output.mkdir(parents=True,exist_ok=False)
    result={'image_sha256':hashlib.sha256(args.image.read_bytes()).hexdigest(),
            'method':args.method,'threshold':args.threshold,'seconds':elapsed,
            'examples':payload.get('examples',[]),'existing':payload.get('existing',[]),
            'example_ids':selected['example_ids'],'state_in':str(args.state_in) if args.state_in else None,
            'suggestions':results,'note':'Experimental suggestions only. Scores are not occupancy probabilities.'}
    (args.output/'suggestions.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.output/'state.json').write_text(json.dumps(selected['state'],indent=2)+'\n')
    overlay=cv2.cvtColor(np.uint8(image*255),cv2.COLOR_RGB2BGR)
    new_ids={r['id'] for r in results}
    for row in selected['state']['cells']:
        circle=Circle(**row['circle'])
        color=(60,230,80) if row['id'] in selected['example_ids'] else (0,200,240) if row['id'] in new_ids else (180,180,180)
        cv2.circle(overlay,(round(circle.x),round(circle.y)),round(circle.radius),color,2,cv2.LINE_AA)
    cv2.imwrite(str(args.output/'suggestions.png'),overlay)
    print(json.dumps({'suggestions':len(results),'seconds':round(elapsed,3),'output':str(args.output)}))


if __name__=='__main__':main()
