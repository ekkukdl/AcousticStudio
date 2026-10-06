from pathlib import Path
import json,pcbnew,xml.etree.ElementTree as ET
root=Path.cwd();source=root/'outputs/pcb/polygon_panels/panel_8faces_16ch'
b=pcbnew.LoadBoard(str(source/'panel_8faces_16ch.kicad_pcb'))
netlist=ET.parse(source/'schematic.net.xml').getroot()
sch={c.attrib['ref']:{'value':c.findtext('value'),'footprint':c.findtext('footprint')} for c in netlist.findall('./components/comp')}
rows=[]
for fp in b.GetFootprints():
    ref=fp.GetReference()
    if ref.startswith('H'):continue
    pads=[{'number':p.GetNumber(),'x_mm':pcbnew.ToMM(p.GetPosition().x),'y_mm':pcbnew.ToMM(p.GetPosition().y),'net':p.GetNetname(),'size_mm':[pcbnew.ToMM(p.GetSize().x),pcbnew.ToMM(p.GetSize().y)],'drill_mm':[pcbnew.ToMM(p.GetDrillSize().x),pcbnew.ToMM(p.GetDrillSize().y)]} for p in fp.Pads()]
    assert ref in sch and fp.GetValue()==sch[ref]['value'],ref
    rows.append({'ref':ref,'value':fp.GetValue(),'footprint':str(fp.GetFPID().GetLibItemName()),'side':'Top' if fp.GetLayer()==pcbnew.F_Cu else 'Bottom','x_mm':pcbnew.ToMM(fp.GetPosition().x),'y_mm':pcbnew.ToMM(fp.GetPosition().y),'rotation_deg':fp.GetOrientationDegrees(),'smd':bool(fp.GetAttributes()&pcbnew.FP_SMD),'pads':pads})
assert len(rows)==74
assert sum(r['smd'] for r in rows)==55
dest=root/'scratch/pcba_inputs/pcba_parts_8f.json'
dest.write_text(json.dumps(rows,indent=2),encoding='utf-8')
from collections import Counter
print(json.dumps({'total':len(rows),'smd':sum(r['smd'] for r in rows),'groups':dict(Counter((r['value']+' / '+r['footprint']+' / '+r['side']) for r in rows))},indent=2))
