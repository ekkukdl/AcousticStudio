"""Shared-part tunnel: original 6 faces and dual-PCB regular octagon."""
from pathlib import Path
import importlib.util, json, math
import cadquery as cq

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'creo_tunnel_models'
spec=importlib.util.spec_from_file_location('original',OLD/'build_models.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
DATA=json.loads((OLD/'pcb_geometry.json').read_text())

def matrix(loc):
    # PTC uses row vectors: transpose the CadQuery column-vector transform.
    m=loc.wrapped.Transformation()
    return [[m.Value(j+1,i+1) if j<3 else (1 if i==3 else 0) for j in range(4)] for i in range(4)]

def ring8(d,apothem=150,gap=20):
    rb=apothem+12.5
    ring=cq.Workplane('XY').polyline(old.polygon(8,rb+15)).close().extrude(8)
    ring=ring.cut(cq.Workplane('XY').workplane(offset=-.1).polyline(old.polygon(8,rb-2)).close().extrude(8.2))
    for k in range(8):
        for y in (-58,10):
            slot=cq.Workplane('XY').box(2.2,48.6,8.2,centered=(False,False,False)).translate((rb-.3,y-.3,-.1)).rotate((0,0,0),(0,0,1),45*k)
            ring=ring.cut(slot)
    return ring.val()

def build(n):
    d=DATA[str(n)]; double=n==8; apothem=150 if double else 75
    board=old.make_board(d)
    tx=cq.Workplane('XY').workplane(offset=-12.5).circle(8).extrude(12.5).val()
    ring=ring8(d) if double else old.make_ring(6,d)
    (ROOT/'geometry').mkdir(exist_ok=True)
    old.checked_export(ring,ROOT/'geometry'/f'ring_{n}f.step')
    panel=cq.Assembly(name=f'panel_{n}f')
    panel.add(board,name=f'pcb_{n}f',color=cq.Color(.04,.35,.16))
    emitter_matrices=[]
    for p in d['emitters']:
        loc=cq.Location(cq.Vector(p['x'],p['y'],0));emitter_matrices.append(matrix(loc))
        panel.add(tx,name='tx_'+p['reference'],loc=loc,color=cq.Color(.7,.71,.74))
    unit=panel
    pair_matrices=[matrix(cq.Location(cq.Vector(0,0,0))),matrix(cq.Location(cq.Vector(68,0,0)))]
    if double:
        unit=cq.Assembly(name='facepair_8f')
        for j,x in enumerate((0,68)):unit.add(panel,name=f'panel_instance_{j}',loc=cq.Location(cq.Vector(x,0,0)))
    asm=cq.Assembly(name=f'tunnel_{n}f_v2')
    mats=[]; solids=[]
    width=116 if double else d['width']
    for k in range(n):
        loc=cq.Location(cq.Vector(0,0,0),cq.Vector(0,0,1),360*k/n)*cq.Location(cq.Vector(apothem+12.5,-width/2,0),cq.Vector(1,1,1),120)
        mats.append(matrix(loc));asm.add(unit,name=f'face_{k+1}',loc=loc)
        for x in ((0,68) if double else (0,)):
            lp=loc*cq.Location(cq.Vector(x,0,0));solids.append(board.located(lp))
            for p in d['emitters']:solids.append(tx.located(lp*cq.Location(cq.Vector(p['x'],p['y'],0))))
    for j,z in enumerate((0,172)):
        asm.add(ring,name=f'ring_{j}',loc=cq.Location(cq.Vector(0,0,z)),color=cq.Color(.3,.32,.36));solids.append(ring.translate((0,0,z)))
    clashes=[]
    for i,a in enumerate(solids):
        ba=a.BoundingBox()
        for j in range(i+1,len(solids)):
            b=solids[j];bb=b.BoundingBox()
            if any(getattr(ba,q+'max')<getattr(bb,q+'min')-1e-7 or getattr(bb,q+'max')<getattr(ba,q+'min')-1e-7 for q in 'xyz'):continue
            v=a.intersect(b).Volume()
            if v>1e-5:clashes.append([i,j,v])
    assert not clashes,clashes
    path=ROOT/'geometry'/f'tunnel_{n}f_v2.step'
    asm.export(str(path),exportType='STEP',unit='MM')
    back=cq.importers.importStep(str(path));count=sum(len(s.Solids()) for s in back.vals())
    assert count==len(solids)
    bb=cq.Compound.makeCompound(solids).BoundingBox()
    # Clear optical axis y=0 in every face, at middle height; ring remains at ends.
    camera_clear=double and all(abs(p['x']-58)>=16 for x in (0,68) for p in [{'x':x+q['x']} for q in d['emitters']])
    result=dict(faces=n,pcb_size_mm=[d['width'],180,1.6],pcb_count=n*(2 if double else 1),transducer_count=n*(32 if double else 16),gap_mm=20 if double else None,face_angular_pitch_deg=360/n,emitting_plane_spacing_mm=2*apothem,pcb_plane_apothem_mm=apothem+12.5,face_width_at_pcb_plane_mm=2*(apothem+12.5)*math.tan(math.pi/n),overall_size_mm=[bb.xlen,bb.ylen,bb.zlen],solid_count=count,interferences=clashes,emitter_matrices=emitter_matrices,face_matrices=mats,pair_matrices=pair_matrices,camera_centerline_clear=camera_clear if double else None)
    (ROOT/'geometry'/f'checks_{n}f.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if 'matrices' not in k}),flush=True)

if __name__=='__main__':
    for n in (6,8):build(n)
