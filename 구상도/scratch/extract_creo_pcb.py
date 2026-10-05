import json
from pathlib import Path
import pcbnew

out = Path('outputs/creo_tunnel_models')
out.mkdir(parents=True, exist_ok=True)
data = {}
for n in (6, 8):
    name = f'panel_{n}faces_16ch'
    path = Path('outputs/polygon_panels') / name / f'{name}.kicad_pcb'
    b = pcbnew.LoadBoard(str(path))
    edges = [g for g in b.GetDrawings() if g.GetLayer() == pcbnew.Edge_Cuts]
    coords = [(pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)) for g in edges for p in (g.GetStart(), g.GetEnd())]
    holes = []
    emitters = []
    for fp in b.GetFootprints():
        if fp.GetReference().startswith('T'):
            emitters.append({'reference': fp.GetReference(), 'x': pcbnew.ToMM(fp.GetPosition().x), 'y': pcbnew.ToMM(fp.GetPosition().y)})
        for pad in fp.Pads():
            drill = pad.GetDrillSize()
            if drill.x:
                holes.append({'reference': fp.GetReference(), 'pad': pad.GetNumber(), 'x': pcbnew.ToMM(pad.GetPosition().x), 'y': pcbnew.ToMM(pad.GetPosition().y), 'dx': pcbnew.ToMM(drill.x), 'dy': pcbnew.ToMM(drill.y)})
    data[str(n)] = {'source': str(path), 'width': max(x for x,y in coords)-min(x for x,y in coords), 'length': max(y for x,y in coords)-min(y for x,y in coords), 'thickness': pcbnew.ToMM(b.GetDesignSettings().GetBoardThickness()), 'holes': holes, 'emitters': sorted(emitters,key=lambda p:int(p['reference'][1:]))}
(out/'pcb_geometry.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
print(json.dumps({n:{k:v for k,v in p.items() if k not in ('holes','emitters')}|{'holes':len(p['holes']),'emitters':len(p['emitters'])} for n,p in data.items()},indent=2))
