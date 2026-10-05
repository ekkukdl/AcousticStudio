"""Build mm STEP parts/assemblies from the existing KiCad PCB geometry.

Creo 9 imports these STEP assemblies before saving native PRT/ASM files.
The frame and transducer are concept envelopes, not production designs.
"""
import json
import math
from pathlib import Path
import cadquery as cq

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / 'pcb_geometry.json').read_text(encoding='utf-8'))
APOTHEM = 75.0
BODY_HEIGHT = 12.5
BODY_DIAMETER = 16.0
RING_THICKNESS = 8.0
SLOT_CLEARANCE = 0.3

def polygon(n, apothem):
    r = apothem / math.cos(math.pi/n)
    return [(r*math.cos((i+0.5)*2*math.pi/n), r*math.sin((i+0.5)*2*math.pi/n)) for i in range(n)]

def make_board(d):
    board = cq.Workplane('XY').box(d['width'], d['length'], d['thickness'], centered=(False,False,False))
    for h in d['holes']:
        if abs(h['dx']-h['dy']) > 1e-7:
            raise ValueError('Unexpected slotted drill; model explicitly before export')
        cut = cq.Workplane('XY').workplane(offset=-0.1).center(h['x'],h['y']).circle(h['dx']/2).extrude(d['thickness']+0.2)
        board = board.cut(cut)
    return board.val()

def make_ring(n, d):
    outer = cq.Workplane('XY').polyline(polygon(n,APOTHEM+BODY_HEIGHT+15)).close().extrude(RING_THICKNESS)
    inner = cq.Workplane('XY').workplane(offset=-0.1).polyline(polygon(n,APOTHEM+BODY_HEIGHT-2)).close().extrude(RING_THICKNESS+0.2)
    ring = outer.cut(inner)
    # The original SCAD rings overlapped the board ends. Clearance slots retain
    # the same board positions while preventing solid interference.
    for k in range(n):
        slot = cq.Workplane('XY').box(d['thickness']+2*SLOT_CLEARANCE, d['width']+2*SLOT_CLEARANCE, RING_THICKNESS+0.2, centered=(False,False,False)).translate((APOTHEM+BODY_HEIGHT-SLOT_CLEARANCE,-d['width']/2-SLOT_CLEARANCE,-0.1)).rotate((0,0,0),(0,0,1),360*k/n)
        ring = ring.cut(slot)
    return ring.val()

def checked_export(shape, path):
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError(f'Invalid or non-single solid: {path}')
    cq.exporters.export(shape,str(path))
    reread = cq.importers.importStep(str(path)).val()
    if not reread.isValid() or abs(reread.Volume()-shape.Volume()) > 1e-4:
        raise ValueError(f'STEP round-trip changed geometry: {path}')

def build(n):
    d = DATA[str(n)]
    folder = ROOT / f'{n}faces'
    folder.mkdir(exist_ok=True)
    board = make_board(d)
    emitter = cq.Workplane('XY').workplane(offset=-BODY_HEIGHT).circle(BODY_DIAMETER/2).extrude(BODY_HEIGHT).val()
    ring = make_ring(n,d)
    checked_export(board,folder/f'pcb_{n}f.step')
    checked_export(emitter,folder/f'transducer_{n}f.step')
    checked_export(ring,folder/f'ring_{n}f.step')
    panel = cq.Assembly(name=f'panel_{n}f')
    panel.add(board,name=f'pcb_{n}f',color=cq.Color(0.04,0.35,0.16))
    for p in d['emitters']:
        panel.add(emitter,name=f'tx_{n}f_{p["reference"].lower()}',loc=cq.Location(cq.Vector(p['x'],p['y'],0)),color=cq.Color(0.68,0.69,0.71))
    panel.export(str(folder/f'panel_{n}f.step'),exportType='STEP',unit='MM')
    asm = cq.Assembly(name=f'tunnel_{n}faces')
    base = cq.Location(cq.Vector(APOTHEM+BODY_HEIGHT,-d['width']/2,0),cq.Vector(1,1,1),120)
    placements = []
    all_solids = []
    for k in range(n):
        rotation = cq.Location(cq.Vector(0,0,0),cq.Vector(0,0,1),360*k/n)
        loc = rotation*base
        asm.add(panel,name=f'panel_{n}f_{k+1:02}',loc=loc)
        all_solids.append(board.located(loc))
        for p in d['emitters']:
            all_solids.append(emitter.located(loc*cq.Location(cq.Vector(p['x'],p['y'],0))))
        placements.append({'panel':k+1,'azimuth_deg':360*k/n})
    lower = ring
    upper = ring.translate((0,0,d['length']-RING_THICKNESS))
    asm.add(ring,name=f'ring_{n}f_lower',color=cq.Color(0.32,0.34,0.37))
    asm.add(ring,name=f'ring_{n}f_upper',loc=cq.Location(cq.Vector(0,0,d['length']-RING_THICKNESS)),color=cq.Color(0.32,0.34,0.37))
    all_solids += [lower,upper]
    compound = cq.Compound.makeCompound(all_solids)
    bb = compound.BoundingBox()
    # Check every panel and transducer against the rings; remaining adjacent
    # panel overlaps are excluded by an explicit nearest-neighbour check.
    clashes = []
    for i,a in enumerate(all_solids):
        for j in range(i+1,len(all_solids)):
            b = all_solids[j]
            ba,bc=a.BoundingBox(),b.BoundingBox()
            if any((getattr(ba,q+'max') < getattr(bc,q+'min')-1e-7 or getattr(bc,q+'max') < getattr(ba,q+'min')-1e-7) for q in 'xyz'):
                continue
            volume = a.intersect(b).Volume()
            if volume > 1e-5:
                clashes.append({'solid_a':i,'solid_b':j,'overlap_mm3':volume})
    if clashes:
        raise ValueError(clashes)
    asm.export(str(folder/f'tunnel_{n}faces.step'),exportType='STEP',unit='MM')
    reread=cq.importers.importStep(str(folder/f'tunnel_{n}faces.step'))
    solid_count=sum(len(s.Solids()) for s in reread.vals())
    expected=n*17+2
    if solid_count!=expected:
        raise ValueError(f'Assembly round-trip: {solid_count} vs {expected}')
    summary={'units':'mm','faces':n,'pcb_size_mm':[d['width'],d['length'],d['thickness']],'drill_holes_per_pcb':len(d['holes']),'transducers_per_pcb':len(d['emitters']),'total_transducers':n*len(d['emitters']),'radiating_face_distance_mm':2*APOTHEM,'board_radial_position_mm':APOTHEM+BODY_HEIGHT,'overall_size_mm':[bb.xlen,bb.ylen,bb.zlen],'solid_count':expected,'step_round_trip_solid_count':solid_count,'solid_interferences':clashes,'placements':placements,'frame_status':'concept: slots only; fasteners/brackets/cable clearance not finalized','transducer_status':'D16/H12.5 envelope without pins or mesh','native_creo_status':'pending import and save in Creo 9'}
    (folder/'geometry_checks.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':
    for n in (6,8):
        build(n)
