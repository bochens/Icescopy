"""Make an offline, local-only comparison page from a completed benchmark."""
import argparse
import json
from pathlib import Path


PAGE=r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cell detection experiment</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f6;color:#173437;font:15px system-ui,sans-serif}header{padding:22px 28px;background:#fff;border-bottom:1px solid #d8e1e1}h1{font-size:23px;margin:0 0 7px}p{margin:7px 0;line-height:1.5}.muted{color:#53696b;font-size:13px}main{padding:18px 28px}.controls{display:flex;gap:18px;align-items:end;flex-wrap:wrap;margin-bottom:14px}label{display:flex;gap:6px;flex-direction:column;font-size:13px}select{font:inherit;background:white;border:1px solid #adc0c0;border-radius:6px;padding:8px;min-width:150px}.checks{flex-direction:row;align-items:center;padding-bottom:8px}.stats{display:flex;gap:22px;flex-wrap:wrap;background:white;border:1px solid #d8e1e1;border-radius:8px;padding:12px 16px;margin-bottom:14px}.stats b{font-size:19px;margin-right:5px}.stage{background:#172526;border-radius:9px;overflow:auto;max-height:78vh;text-align:center}canvas{max-width:100%;height:auto;vertical-align:middle}footer{padding:10px 0;font-size:12px;color:#53696b}.legend{display:flex;gap:20px;margin:10px 0;font-size:13px}.dot{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px}.note{max-width:1000px}button{padding:8px;border:1px solid #adc0c0;background:white;border-radius:6px;color:#173437;cursor:pointer}</style>
<header><h1>Detection from one or two examples</h1><p>Local experiment · single pictures · no changes to Icescopy or saved sessions</p><p class="muted note">Green circles are the supplied examples. Yellow circles are proposed additions. Compare different examples and methods. Scores rank similarity; they do not certify that a well contains a sample.</p></header>
<main><div class="controls"><label>Picture<select id="scene"></select></label><label>Method<select id="method"><option value="template">Image matching</option><option value="embedding">Pretrained neural network</option><option value="learned">Trained comparison model</option></select></label><label>Examples<select id="count"><option>1</option><option>2</option></select></label><label>Example choice<select id="trial"></select></label><label class="checks"><input id="truth" type="checkbox">Show reference circles and missed cells</label><button id="zoom">Show original size</button></div>
<div class="stats" id="stats"></div><div class="legend"><span><i class="dot" style="background:#39e87d"></i>Marked examples</span><span><i class="dot" style="background:#ffce48"></i>Proposed additions</span><span><i class="dot" style="background:#ef718b"></i>Missed reference cells</span></div><div class="stage"><canvas id="canvas"></canvas></div><p id="status" class="muted note"></p><footer>Reference locations came from manual inspection or existing session circles. Unknown occupancy and incomplete labels are stated for each picture. This is an experimental comparison, not a validated detector.</footer></main>
<script>const DATA=__DATA__;const $=id=>document.getElementById(id);let scene,result,picture=new Image(),original=false;
DATA.scenes.forEach((s,i)=>{let o=document.createElement('option');o.value=i;o.textContent=s.id+' · '+s.split.replaceAll('_',' ');$('scene').append(o)});
function options(){scene=DATA.scenes[+$('scene').value];let rows=scene.results.filter(r=>r.method===$('method').value&&r.seeds.length===+$('count').value);$('trial').replaceChildren();rows.forEach((r,i)=>{let o=document.createElement('option');o.value=i;o.textContent='Cells '+r.seeds.join(' + ');$('trial').append(o)});choose();}
function choose(){let rows=scene.results.filter(r=>r.method===$('method').value&&r.seeds.length===+$('count').value);result=rows[+$('trial').value];picture.onload=draw;picture.src=scene.id+'.jpg';draw();}
function circle(ctx,c,color,width){let k=scene.preview_scale;ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.arc(c.x*k,c.y*k,c.radius*k,0,Math.PI*2);ctx.stroke();}
function draw(){if(!scene||!result||!picture.complete||!picture.naturalWidth)return;let canvas=$('canvas');canvas.width=picture.naturalWidth;canvas.height=picture.naturalHeight;canvas.style.maxWidth=original?'none':'100%';let ctx=canvas.getContext('2d');ctx.drawImage(picture,0,0);if($('truth').checked){scene.truth.forEach((c,i)=>{if(!result.seeds.includes(i))circle(ctx,c,result.missed_ids.includes(i)?'#ef718b':'#8caaaa',1.5)})}result.accepted.forEach(i=>circle(ctx,scene.proposals[i],'#ffce48',2));result.seeds.forEach(i=>circle(ctx,scene.truth[i],'#39e87d',3));let errors=result.false_detections===null?result.unmatched_suggestions+' unclassified additions':result.false_detections+' extra detections';$('stats').innerHTML='<span><b>'+result.found+'/'+result.remaining+'</b> reference cells found</span><span><b>'+result.missed+'</b> missed</span><span><b>'+errors+'</b></span><span><b>'+result.duplicate_existing+'</b> duplicates of examples</span><span>Threshold '+result.threshold.toFixed(2)+'</span>';$('status').textContent=scene.label_status+' Image preparation and model features: '+scene.seconds.toFixed(2)+' seconds on this Mac; changing examples reuses those features.';}
['scene','method','count'].forEach(id=>$(id).onchange=options);$('trial').onchange=choose;$('truth').onchange=draw;$('zoom').onclick=()=>{original=!original;$('zoom').textContent=original?'Fit picture':'Show original size';draw()};options();</script></html>'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    args=parser.parse_args()
    data=json.loads(args.report.read_text())
    target=args.report.parent/'review.html'
    with target.open('x') as out:
        out.write(PAGE.replace('__DATA__',json.dumps(data).replace('<','\\u003c')))
    print(target.resolve())


if __name__=='__main__':main()
