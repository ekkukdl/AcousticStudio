"""Prepare placement-only data so native conversion can run alongside STEP checks."""
from pathlib import Path
import json,math
r=Path(__file__).resolve().parents[1];d=r/'outputs/panel_8faces_32ch_R1/mechanical/creo32_R1';stage=r/'scratch/creo32_session'
data=json.loads((d/'pcb_geometry_input.json').read_text());holes=data['component_holes']
names={'T':'tx16_r1','R':'r0805_r1','C':'c0805_r1','595':'so16_r1','DRV':'so8_r1','Q':'sot23_r1','CP':'cp63_r1','JLOG':'hdr10_r1','JPWR':'hdr3_r1'}
parts=[{'name':n} for n in ['pcb32_r1']+list(names.values())]
pcs=[{'reference':'PCB','model':'pcb32_r1','matrix':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}]
for p in data['components']:
 x,y=p['x'],p['y'];a=math.radians(-p['rotation']);c,s=math.cos(a),math.sin(a)
 if p['kind'] in ('CP','JLOG','JPWR'):
  hh=[q for q in holes if q['ref']==p['ref']];x=sum(q['x'] for q in hh)/len(hh);y=sum(q['y'] for q in hh)/len(hh)
 pcs.append({'reference':p['ref'],'model':names[p['kind']],'matrix':[[c,s,0,0],[-s,c,0,0],[0,0,1,0],[x,y,0 if p['kind']=='T' else 1.6,1]]})
faces=[]
for f in range(8):
 a=math.pi*f/4;c,s=math.cos(a),math.sin(a)
 faces.append([[-s,c,0,0],[0,0,1,0],[c,s,0,0],[117.5*c+42*s,117.5*s-42*c,-112,1]])
plan={'parts':parts,'panel_components':pcs,'face_matrices':faces}
(d/'native_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
(stage/'build.creojs').write_text((stage/'builder_template.creojs').read_text().replace('MODEL_DATA',json.dumps(plan)),encoding='utf-8')
print('Prepared 10 parts, 149 panel components and 8 face placements.')
