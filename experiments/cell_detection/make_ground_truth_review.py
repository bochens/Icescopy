"""Build a local reference-label viewer without changing images or annotations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


PAGE = r'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cell reference labels</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#151719;color:#eee;font:15px system-ui,sans-serif}
header{padding:20px 24px 12px;border-bottom:1px solid #444}h1{font-size:23px;margin:0 0 8px}
p{line-height:1.5;margin:8px 0}.muted{color:#b7bec5}.controls{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:14px 0}
select,button{font:inherit;color:inherit;background:#292e33;border:1px solid #626a72;border-radius:6px;padding:7px 10px}
select{max-width:100%}button{cursor:pointer}label{display:flex;align-items:center;gap:6px}input{accent-color:#59bbff}
.positive{color:#71ff7a}.negative{color:#ff8f8f}#status{font-weight:600}#viewport{padding:16px;overflow:auto;height:calc(100vh - 270px);min-height:420px}
#picture{position:relative;width:100%;margin:0}#photo{display:block;width:100%;height:auto}svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
circle{fill:none;stroke-width:2;vector-effect:non-scaling-stroke}text{paint-order:stroke;stroke:#111;stroke-width:2px;stroke-linejoin:round;font-weight:600}
#error{color:#ffa4a4}a{color:#8bceff}footer{padding:8px 24px 20px;font-size:13px}
</style><header><h1>Reference labels</h1>
<p>These are the annotations used to train or evaluate the detector, <strong>not detector predictions</strong>.
<span class="positive">Green: droplet or filled well.</span> <span class="negative">Red: reviewed non-cell location.</span>
Circles mark measurement areas, not exact outer boundaries.</p>
<div class="controls"><label>Recording <select id="group"></select></label><label>Frame <select id="frame"></select></label>
<button id="previous" aria-label="Previous frame">Previous</button><button id="next" aria-label="Next frame">Next</button>
<label><input id="positives" type="checkbox" checked>Positives</label><label><input id="negatives" type="checkbox" checked>Negatives</label>
<label><input id="ids" type="checkbox">Cell IDs</label><button id="fit">Fit</button><button id="zoom">Zoom in</button></div>
<p id="status"></p><p id="note" class="muted"></p><p id="error" role="alert"></p></header>
<div id="viewport"><figure id="picture"><img id="photo" alt="Original frame with optional reference circles"><svg id="overlay"></svg></figure></div>
<footer>Liquid and frozen samples are both positive. Unmarked wells in partial annotations remain unknown.
CIF circles were checked at sampled times and carried across the fixed-camera recording; individual frames may still need corrections.
Original image bytes and annotation files are unchanged. Nothing is uploaded.</footer>
<script>const DATA=__DATA__;const $=id=>document.getElementById(id);const NS='http://www.w3.org/2000/svg';
let scene,rows=[],width=null;const groups=[...new Set(DATA.map(s=>s.group))];
for(const name of groups){const o=document.createElement('option');o.textContent=name;o.value=name;$('group').append(o)}
function chooseGroup(){rows=DATA.filter(s=>s.group===$('group').value);$('frame').replaceChildren();
rows.forEach((s,i)=>{let o=document.createElement('option');o.value=i;o.textContent=s.frame===null?s.id:'Frame '+(s.frame+1);$('frame').append(o)});chooseFrame()}
function chooseFrame(){scene=rows[+$('frame').value];$('error').textContent='';$('photo').src=scene.source;
$('overlay').setAttribute('viewBox',`0 0 ${scene.width} ${scene.height}`);$('status').textContent=
`${scene.partition==='training'?'Training':'Held out for evaluation'} · ${scene.targets.length} positive circles · ${scene.negatives.length} negative circles · ${scene.complete?'Complete reference labels':'Partial reference labels'}`;
$('note').textContent=scene.status||scene.provenance;$('previous').disabled=+$('frame').value===0;$('next').disabled=+$('frame').value===rows.length-1;draw()}
function draw(){const svg=$('overlay');svg.replaceChildren();if(!scene)return;
for(const [kind,color,enabled] of [['targets','#59ff68',$('positives').checked],['negatives','#ff7070',$('negatives').checked]]){
if(!enabled)continue;for(const c of scene[kind]){const circle=document.createElementNS(NS,'circle');
for(const [a,v] of Object.entries({cx:c[1],cy:c[2],r:c[3],stroke:color}))circle.setAttribute(a,v);svg.append(circle);
if($('ids').checked){const text=document.createElementNS(NS,'text');text.setAttribute('x',c[1]+c[3]+3);text.setAttribute('y',c[2]);
text.setAttribute('fill',color);text.setAttribute('font-size',Math.max(13,scene.width/100));text.textContent=(kind==='targets'?'P':'N')+c[0];svg.append(text)}}}}
$('group').onchange=chooseGroup;$('frame').onchange=chooseFrame;for(const id of ['positives','negatives','ids'])$(id).onchange=draw;
for(const [id,step] of [['previous',-1],['next',1]])$(id).onclick=()=>{$('frame').value=String(+$('frame').value+step);chooseFrame()};
$('fit').onclick=()=>{width=null;$('picture').style.width='100%'};
$('zoom').onclick=()=>{width=(width||$('picture').getBoundingClientRect().width)*1.5;$('picture').style.width=width+'px'};
$('photo').onerror=()=>{$('error').textContent='Image could not be loaded. Serve this page from its local output folder.'};chooseGroup();</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    root = args.output.resolve().parent
    scenes = json.loads(args.manifest.read_text())['scenes']
    data = []
    for s in scenes:
        source = Path(s['source']).resolve().relative_to(root)
        data.append(dict(
            id=s['id'], group=s['group'], frame=s.get('frame_index0'),
            partition=s['partition'], source=source.as_posix(),
            width=s['width'], height=s['height'], complete=s['complete_labels'],
            status=s.get('label_status', ''), provenance=s['label_provenance'],
            targets=[[c.get('id', i), c['x'], c['y'], c['radius']]
                     for i, c in enumerate(s['targets'])],
            negatives=[[c.get('id', i), c['x'], c['y'], c['radius']]
                       for i, c in enumerate(s.get('negatives', []))]))
    # Exclusive creation protects every earlier preview. No image is modified.
    with args.output.open('x') as out:
        out.write(PAGE.replace('__DATA__', json.dumps(data, separators=(',', ':')).replace('<', '\\u003c')))
    print(args.output.resolve())


if __name__ == '__main__':
    main()
