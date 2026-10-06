"""Add conservative GND stitching to a freshly generated R1 board, then run DRC.
Use KiCad bundled Python. Rebuild first for deterministic regeneration.
"""
from pathlib import Path
import json, math, uuid
import pcbnew

dest=Path(__file__).resolve().parents[1]/'outputs/panel_8faces_32ch_R1'
path=dest/'panel_8faces_32ch_R1.kicad_pcb'
b=pcbnew.LoadBoard(str(path)); mm=pcbnew.ToMM
gnd=b.FindNet('/GND'); tracks=list(b.GetTracks()); pads=[p for f in b.GetFootprints() for p in f.Pads()]
zones=[z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode()==gnd.GetNetCode()]
def point(v):return mm(v.x),mm(v.y)
def segdist(x,y,a,c):
    ax,ay=point(a);cx,cy=point(c);dx=cx-ax;dy=cy-ay
    t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
    return math.hypot(x-ax-t*dx,y-ay-t*dy)
def safe(x,y):
    v=pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
    if not all(z.HitTestFilledArea(z.GetLayer(),v) for z in zones):return False
    for p in pads:
        box=p.GetBoundingBox(); x0,y0=point(box.GetPosition());x1,y1=point(box.GetEnd())
        if math.hypot(max(x0-x,0,x-x1),max(y0-y,0,y-y1))<0.65:return False
    for t in tracks:
        if t.GetNetCode()==gnd.GetNetCode():continue
        width=t.GetWidth(pcbnew.F_Cu) if isinstance(t,pcbnew.PCB_VIA) else t.GetWidth()
        if segdist(x,y,t.GetStart(),t.GetEnd())<mm(width)/2+0.60:return False
    return True
added=[]
def add(x,y):
    if any(math.hypot(x-a,y-c)<1.0 for a,c in added):return
    if not safe(x,y):return
    v=pcbnew.PCB_VIA(b);v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
    v.SetWidth(pcbnew.FromMM(0.6));v.SetDrill(pcbnew.FromMM(0.3));v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNet(gnd)
    v.SetUuid(pcbnew.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL,f'panel32-r1-stitch-{x}-{y}'))))
    b.Add(v);tracks.append(v);added.append((x,y))
for t in list(tracks):
    if isinstance(t,pcbnew.PCB_VIA) and t.GetNetCode()!=gnd.GetNetCode():
        x,y=point(t.GetPosition())
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1.5,0),(-1.5,0)]:
            if safe(x+dx,y+dy):add(x+dx,y+dy);break
for x in (1.2,42,82.8):
    for y in range(27,200,10):add(x,y)
b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(path),b)
(dest/'analysis/stitching.json').write_text(json.dumps({'added_ground_vias':len(added),'positions_mm':added,'diameter_mm':0.6,'drill_mm':0.3},indent=2),encoding='utf-8')
print('Added GND vias:',len(added))
