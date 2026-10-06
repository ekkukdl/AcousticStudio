"""New colored shared-part Creo geometry with upper/lower mounting rings."""
from pathlib import Path
import json,math,hashlib,shutil
import cadquery as cq
r=Path(__file__).resolve().parents[1]
old=r/'outputs/panel_8faces_32ch_R1/mechanical/creo32_R1'
d=old.parent/'creo32_frame_R2';g=d/'geometry';g.mkdir(parents=True,exist_ok=True)
data=json.loads((old/'geometry_checks.json').read_text(encoding='utf-8'))
source=json.loads((old/'pcb_geometry_input.json').read_text(encoding='utf-8'))
protected={str(p.relative_to(old)):hashlib.sha256(p.read_bytes()).hexdigest() for p in old.rglob('*') if p.is_file()}
colors={'pcb32_r2':(.04,.35,.16),'tx16_r1':(.7,.71,.74),'ring8_32_r2':(.3,.32,.36),'r0805_r1':(.15,.16,.18),'c0805_r1':(.66,.48,.26),'so16_r1':(.1,.11,.13),'so8_r1':(.1,.11,.13),'sot23_r1':(.1,.11,.13),'cp63_r1':(.15,.24,.36),'hdr10_r1':(.18,.18,.2),'hdr3_r1':(.18,.18,.2)}
def info(s):
 b=s.BoundingBox();return dict(size_mm=[b.xlen,b.ylen,b.zlen],bounds_mm=[[b.xmin,b.ymin,b.zmin],[b.xmax,b.ymax,b.zmax]],volume_mm3=s.Volume(),solids=len(s.Solids()))
def matrix(loc):
 m=loc.wrapped.Transformation();return [[m.Value(j+1,i+1) if j<3 else (1 if i==3 else 0) for j in range(4)] for i in range(4)]
def location(m):
 from OCP.gp import gp_Trsf
 t=gp_Trsf();t.SetValues(*[m[j][i] for i in range(3) for j in range(4)]);return cq.Location(t)
def polygon(ap):
 return [(ap/math.cos(math.pi/8)*math.cos((i+.5)*math.pi/4),ap/math.cos(math.pi/8)*math.sin((i+.5)*math.pi/4)) for i in range(8)]
shapes={}
for p in data['parts']:
 name=p['name'];shapes[name.replace('pcb32_r1','pcb32_r2')]=cq.importers.importStep(str(old/'geometry'/(name+'.step'))).val()
rb=data['parameters']['emitting_plane_separation_mm']/2+12.5
outer=rb+15;inner=rb-2
ring=cq.Workplane('XY').polyline(polygon(outer)).close().extrude(8)
ring=ring.cut(cq.Workplane('XY').workplane(offset=-.1).polyline(polygon(inner)).close().extrude(8.2))
for k in range(8):
 slot=cq.Workplane('XY').box(2.2,84.6,8.2,centered=(False,False,False)).translate((rb-.3,-42.3,-.1)).rotate((0,0,0),(0,0,1),45*k)
 ring=ring.cut(slot)
 for t in (-36,36):
  bore=cq.Solid.makeCylinder(1.6,17.2,cq.Vector(inner-.1,t,4),cq.Vector(1,0,0)).rotate((0,0,0),(0,0,1),45*k)
  ring=ring.cut(bore)
shapes['ring8_32_r2']=ring.val()
parts=[]
for name,s in shapes.items():
 assert s.isValid() and len(s.Solids())==1,name
 # AP214 colored single-body assembly preserves surface color on native import.
 a=cq.Assembly(name=name);a.add(s,name=name+'_body',color=cq.Color(*colors[name]));a.export(str(g/(name+'.step')),exportType='STEP',unit='MM')
 back=cq.importers.importStep(str(g/(name+'.step'))).val();assert len(back.Solids())==1 and abs(back.Volume()-s.Volume())<.001
 parts.append(dict(name=name,**info(s)))
panel=cq.Assembly(name='panel32_r2');components=[];panel_solids=[]
for p in data['panel_components']:
 p=dict(p);p['model']=p['model'].replace('pcb32_r1','pcb32_r2');loc=location(p['matrix'])
 panel.add(shapes[p['model']],name=p['reference'],loc=loc,color=cq.Color(*colors[p['model']]))
 components.append(p);panel_solids.append(shapes[p['model']].located(loc))
panel.export(str(g/'panel32_r2.step'),exportType='STEP',unit='MM')
tunnel=cq.Assembly(name='tunnel8_32_r2');allsolids=[];top=[]
for i,m in enumerate(data['face_matrices']):
 loc=location(m);tunnel.add(panel,name=f'face{i}',loc=loc);top.append(dict(model='panel32_r2',matrix=m))
 allsolids.extend(s.located(loc*s.location()) for s in panel_solids)
rings=[]
for z in (-105,97):
 loc=cq.Location(cq.Vector(0,0,z));tunnel.add(shapes['ring8_32_r2'],name='ring_'+str(z),loc=loc,color=cq.Color(*colors['ring8_32_r2']))
 rings.append(shapes['ring8_32_r2'].located(loc));allsolids.append(rings[-1]);top.append(dict(model='ring8_32_r2',matrix=matrix(loc)))
clashes=[]
for j,ring in enumerate(rings):
 br=ring.BoundingBox()
 for i,s in enumerate(allsolids[:-2]):
  bs=s.BoundingBox()
  if bs.zmin>=br.zmax-1e-6 or bs.zmax<=br.zmin+1e-6:continue
  v=ring.intersect(s).Volume()
  if v>1e-5:clashes.append(dict(ring=j,solid=i,volume_mm3=v))
assert not clashes,clashes
mounts=[p for p in source['component_holes'] if p['NPTH']]
assert sorted((round(p['x'],5),round(p['y'],5)) for p in mounts)==[(6,11),(6,213),(78,11),(78,213)]
tunnel.export(str(g/'tunnel8_32_r2.step'),exportType='STEP',unit='MM')
back=cq.importers.importStep(str(g/'tunnel8_32_r2.step')).val();assert len(back.Solids())==1194 and back.isValid()
result={**data,'parts':parts,'panel_components':components,'top_components':top,'panel':info(cq.Compound.makeCompound(panel_solids)),'tunnel':info(cq.Compound.makeCompound(allsolids)),'outer_frame_and_camera_included':False,'outer_frame_included':True,'camera_included':False,'frame_collisions':clashes,'colors_rgb':colors,'frame':dict(outer_apothem_mm=outer,inner_apothem_mm=inner,ring_height_mm=8,ring_z_starts_mm=[-105,97],slot_mm=[84.6,2.2],radial_m3_bore_diameter_mm=3.2,bores_per_ring=16,ring_count=2,mount_z_mm=[-101,101],tangential_mount_mm=[-36,36],opening_height_between_rings_mm=194,slot_each_side_clearance_mm=.3,mount_axis_alignment_verified=True),'R1_protected_sha256':protected}
(d/'geometry_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(d/'pcb_geometry_input.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
print(json.dumps({'ok':True,'parts':len(parts),'size_mm':result['tunnel']['size_mm'],'frame_collisions':clashes}),flush=True)
