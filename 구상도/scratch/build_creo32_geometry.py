"""Build solids and STEP assemblies from actual R1 footprint positions.
Use scratch/creo32_env/Scripts/python.exe. No PCB design edits.
"""
from pathlib import Path
import json,math,hashlib,itertools
import cadquery as cq
from cadquery import exporters

root=Path(__file__).resolve().parents[1];source=root/'outputs/panel_8faces_32ch_R1';dest=source/'mechanical/creo32_R1';geom=dest/'geometry';geom.mkdir(parents=True,exist_ok=True)
data=json.loads((dest/'pcb_geometry_input.json').read_text());params=json.loads((source/'parameters.json').read_text())
w=params['board_width_mm'];h=params['board_length_mm'];th=params['board_thickness_mm']
def box(x,y,z):return cq.Workplane('XY').box(x,y,z,centered=(True,True,False)).val()
board=cq.Workplane('XY').box(w,h,th,centered=(False,False,False))
holes=data['component_holes'];bydiam={}
for hole in holes:
 assert abs(hole['drill_x']-hole['drill_y'])<1e-6,'Unexpected slot'
 bydiam.setdefault(hole['drill_x'],[]).append((hole['x'],hole['y']))
for diameter,points in bydiam.items():
 tools=cq.Workplane('XY').workplane(offset=-.1).pushPoints(points).circle(diameter/2).extrude(th+.2,combine=False)
 board=board.cut(cq.Compound.makeCompound(tools.vals()))
board=board.val();assert len(board.Solids())==1 and board.isValid()
expected_volume=w*h*th-sum(math.pi*(p['drill_x']/2)**2*th for p in holes)
assert abs(board.Volume()-expected_volume)<.001
shapes={
 'pcb32_r1':board,
 'tx16_r1':cq.Workplane('XY').workplane(offset=-12.5).circle(8).extrude(12.5).val(),
 'r0805_r1':box(2,1.25,.6),'c0805_r1':box(2,1.25,1.25),
 'so16_r1':box(3.9,9.9,1.75),'so8_r1':box(3.9,4.9,1.75),
 'sot23_r1':box(1.4,2.9,1.1),
 'cp63_r1':cq.Workplane('XY').circle(3.15).extrude(11).val(),
 'hdr10_r1':box(5.08,12.7,8.5),'hdr3_r1':box(2.54,7.62,8.5)}
kindmodels={'T':'tx16_r1','R':'r0805_r1','C':'c0805_r1','595':'so16_r1','DRV':'so8_r1','Q':'sot23_r1','CP':'cp63_r1','JLOG':'hdr10_r1','JPWR':'hdr3_r1'}
colors={'pcb32_r1':(.06,.38,.24),'tx16_r1':(.7,.73,.76),'r0805_r1':(.15,.16,.18),'c0805_r1':(.66,.48,.26),'so16_r1':(.1,.11,.13),'so8_r1':(.1,.11,.13),'sot23_r1':(.1,.11,.13),'cp63_r1':(.15,.24,.36),'hdr10_r1':(.18,.18,.2),'hdr3_r1':(.18,.18,.2)}
def matrix(loc):
 m=loc.wrapped.Transformation()
 return [[m.Value(j+1,i+1) if j<3 else (1 if i==3 else 0) for j in range(4)] for i in range(4)]
def info(shape):
 b=shape.BoundingBox();return {'size_mm':[b.xlen,b.ylen,b.zlen],'bounds_mm':[[b.xmin,b.ymin,b.zmin],[b.xmax,b.ymax,b.zmax]],'volume_mm3':shape.Volume(),'solids':len(shape.Solids())}
parts=[]
for name,shape in shapes.items():
 assert shape.isValid() and len(shape.Solids())==1
 path=geom/(name+'.step');exporters.export(shape,str(path))
 imported=cq.importers.importStep(str(path)).val();assert imported.isValid() and abs(imported.Volume()-shape.Volume())<1e-4
 parts.append({'name':name,'kind':'exact PCB substrate' if name=='pcb32_r1' else 'approximate component body envelope',**info(shape)})
panel=cq.Assembly(name='panel32_r1');panel.add(board,name='pcb32_r1',color=cq.Color(*colors['pcb32_r1']))
components=[{'reference':'PCB','model':'pcb32_r1','matrix':matrix(cq.Location()),'loc':cq.Location()}];solids=[board]
for p in data['components']:
 model=kindmodels[p['kind']];x,y=p['x'],p['y']
 if p['kind'] in ('CP','JLOG','JPWR'):
  hh=[v for v in holes if v['ref']==p['ref']];x=sum(v['x'] for v in hh)/len(hh);y=sum(v['y'] for v in hh)/len(hh)
 loc=cq.Location(cq.Vector(x,y,0 if p['kind']=='T' else th),cq.Vector(0,0,1),-p['rotation'])
 panel.add(shapes[model],name=p['ref'],loc=loc,color=cq.Color(*colors[model]));solids.append(shapes[model].located(loc))
 components.append({'reference':p['ref'],'model':model,'matrix':matrix(loc),'loc':loc})
assert len(components)==149
def collisions(solids):
 clashes=[];bbs=[s.BoundingBox() for s in solids]
 for i,a in enumerate(solids):
  ba=bbs[i]
  for j in range(i+1,len(solids)):
   bb=bbs[j]
   if any(getattr(ba,q+'max')<=getattr(bb,q+'min')+1e-7 or getattr(bb,q+'max')<=getattr(ba,q+'min')+1e-7 for q in 'xyz'):continue
   v=a.intersect(solids[j]).Volume()
   if v>1e-5:clashes.append({'a':i,'b':j,'volume_mm3':v})
 return clashes
panel_clashes=collisions(solids)
panel.export(str(geom/'panel32_r1.step'),exportType='STEP',unit='MM')
panel_import=cq.importers.importStep(str(geom/'panel32_r1.step')).val();assert len(panel_import.Solids())==149
tunnel=cq.Assembly(name='tunnel8_32_r1');mats=[];allsolids=[]
# Local PCB x => transverse +t; y => world Z; z => outward radial +n.
# Front face sits at Zlocal=0; emitting plane Zlocal=-12.5.
apothem=params['emitting_plane_separation_mm']/2+12.5
for face in range(8):
 a=math.pi*face/4;nx,ny=math.cos(a),math.sin(a);tx,ty=-ny,nx
 # The 120 degree rotation cycles XYZ to YZX; global Z rotation picks face.
 loc=cq.Location(cq.Vector(0,0,0),cq.Vector(0,0,1),face*45)*cq.Location(cq.Vector(apothem,-w/2,-h/2),cq.Vector(1,1,1),120)
 mats.append(matrix(loc));tunnel.add(panel,name=f'face{face}',loc=loc)
 allsolids.extend(s.located(loc*s.location()) for s in solids)
 # Verify every TX centre/normal against the acoustic coordinate file.
 for p in [p for p in data['components'] if p['kind']=='T']:
  center=(loc*cq.Location(cq.Vector(p['x'],p['y'],-12.5))).toTuple()[0]
  expected=[nx*(apothem-12.5)+tx*(p['x']-w/2),ny*(apothem-12.5)+ty*(p['x']-w/2),p['y']-h/2]
  assert all(abs(x-y)<1e-6 for x,y in zip(center,expected))
print('Checking panel solids and disjoint face sectors...',flush=True)
# Every solid is contained in its face's angular sector. This conservative
# bounding-volume proof avoids repeating hundreds of expensive rotated-board
# Boolean operations while providing a strict geometric separation criterion.
pb=cq.Compound.makeCompound(solids).BoundingBox()
sector_half_angle=math.degrees(math.atan2(max(abs(pb.xmin-w/2),abs(pb.xmax-w/2)),apothem+pb.zmin))
assert sector_half_angle<22.5,'Adjacent conservative face envelopes overlap'
tunnel_clashes=[dict(c,face=f) for f in range(8) for c in panel_clashes]
tunnel.export(str(geom/'tunnel8_32_r1.step'),exportType='STEP',unit='MM')
back=cq.importers.importStep(str(geom/'tunnel8_32_r1.step')).val();assert len(back.Solids())==149*8
result={'ok':True,'source_pcb_sha256':data['source_pcb_sha256'],'units':'mm','parameters':params,'parts':parts,'panel_components':[{k:v for k,v in p.items() if k!='loc'} for p in components],'face_matrices':mats,'panel':info(cq.Compound.makeCompound(solids)),'tunnel':info(cq.Compound.makeCompound(allsolids)),'pcb_holes':len(holes),'mounting_holes':sum(p['NPTH'] for p in holes),'panel_collisions':panel_clashes,'tunnel_collisions':tunnel_clashes,'inter_face_check':'strict disjoint bounding angular sectors','sector_half_angle_deg':sector_half_angle,'component_envelopes_approximate':True,'outer_frame_and_camera_included':False,'STEP_reimport_checked':True,'cadquery_version':cq.__version__}
(dest/'geometry_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
stage=root/'scratch/creo32_session';template=(stage/'builder_template.creojs').read_text()
(stage/'build.creojs').write_text(template.replace('MODEL_DATA',json.dumps(result)),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('pcb_holes','mounting_holes','panel_collisions','tunnel_collisions','cadquery_version')}),flush=True)
