"""Record actual KiCad footprint positions and drills for mechanical generation."""
from pathlib import Path
import json,hashlib,pcbnew
root=Path(__file__).resolve().parents[1];d=root/'outputs/panel_8faces_32ch_R1';out=d/'mechanical/creo32_R1';out.mkdir(parents=True,exist_ok=True)
manifest={p['ref']:p for p in json.loads((d/'component_manifest.json').read_text())}
boardpath=d/'panel_8faces_32ch_R1.kicad_pcb';b=pcbnew.LoadBoard(str(boardpath));components=[];holes=[]
for f in b.GetFootprints():
 ref=f.GetReference();v=f.GetPosition()
 if ref in manifest:
  p=manifest[ref].copy();p.update(x=pcbnew.ToMM(v.x),y=pcbnew.ToMM(v.y),rotation= f.GetOrientationDegrees())
  assert abs(p['x']-manifest[ref]['x'])<1e-6 and abs(p['y']-manifest[ref]['y'])<1e-6,'Source changed: '+ref
  components.append(p)
 for pad in f.Pads():
  drill=pad.GetDrillSize()
  if drill.x:
   v=pad.GetPosition();holes.append({'ref':ref,'pad':pad.GetNumber(),'x':pcbnew.ToMM(v.x),'y':pcbnew.ToMM(v.y),'drill_x':pcbnew.ToMM(drill.x),'drill_y':pcbnew.ToMM(drill.y),'NPTH':pad.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH})
result={'source_pcb_sha256':hashlib.sha256(boardpath.read_bytes()).hexdigest(),'units':'mm','component_count':len(components),'components':sorted(components,key=lambda p:p['ref']),'component_holes':holes,'vias_omitted_from_mechanical_board':True}
assert len(components)==148 and len(holes)==98
(out/'pcb_geometry_input.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('Recorded 148 components and 98 component/mounting holes.')
