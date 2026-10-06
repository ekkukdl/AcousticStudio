"""Independent native board/netlist/manufacturing checks. KiCad bundled Python."""
from pathlib import Path
import json, csv, hashlib, math, xml.etree.ElementTree as ET
from collections import Counter
import pcbnew
root=Path(__file__).resolve().parents[1];d=root/'outputs/panel_8faces_32ch_R1';n=d.name
b=pcbnew.LoadBoard(str(d/(n+'.kicad_pcb')));parts=json.loads((d/'component_manifest.json').read_text());by={p['ref']:p for p in parts}
x=ET.parse(d/'schematic.net.xml');nets={}
for net in x.findall('.//nets/net'):
    for node in net.findall('node'):nets[node.get('ref'),node.get('pin')]=net.get('name')
checked=0;functional=0;mechanical=0;uuids=[]
for f in b.GetFootprints():
    ref=f.GetReference();uuids.append(f.m_Uuid.AsString())
    for pad in f.Pads():
        uuids.append(pad.m_Uuid.AsString())
        if ref.startswith('H'):
            assert pad.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH and not pad.GetNetCode();mechanical+=1;continue
        checked+=1
        assert pad.GetNetname()==nets[ref,pad.GetNumber()],(ref,pad.GetNumber(),pad.GetNetname(),nets.get((ref,pad.GetNumber())))
        if by[ref]['nets'][pad.GetNumber()]:functional+=1
        bb=pad.GetBoundingBox();assert pcbnew.ToMM(bb.GetTop())>=22 and pcbnew.ToMM(bb.GetBottom())<=202,ref
    if ref.startswith('T'):
        row,col=divmod(int(ref[1:])-1,4)
        assert abs(pcbnew.ToMM(f.GetPosition().x)-[13,31,53,71][col])<1e-5
        assert abs(pcbnew.ToMM(f.GetPosition().y)-(42+20*row))<1e-5
for t in b.GetTracks():
    uuids.append(t.m_Uuid.AsString())
    for v in (t.GetStart(),t.GetEnd()):assert 22.3<=pcbnew.ToMM(v.y)<=201.7
assert len(uuids)==len(set(uuids))
assert checked==468 and functional==432 and mechanical==4
assert len(x.findall('.//components/comp'))==152
assert len(by)==148
for i in range(32):
    tx=by['T'+str(i+1)];assert set(tx['nets'].values())=={'GND',f'OUT{i:02d}'}
    drivers=[p for p in parts if p['kind']=='DRV' and f'OUT{i:02d}' in p['nets'].values()];assert len(drivers)==1
    dr=drivers[0];assert dr['nets']['3']=='GND' and dr['nets']['6']==('DRV_VDD_A' if i%4<2 else 'DRV_VDD_B')
    outpin=next(pin for pin,net in dr['nets'].items() if net==f'OUT{i:02d}')
    assert dr['nets'][{'7':'2','5':'4'}[outpin]]==f'IN{i:02d}'
    assert sum(f'IN{i:02d}' in [p['nets'].get(a) for a in ('15','1','2','3','4','5','6','7')] for p in parts if p['kind']=='595')==1
mapping=json.loads((d/'physical_to_software_channel_map.json').read_text())['channel_map'];assert sorted(mapping)==list(range(256))
elements=json.loads((d/'array_positions_256.json').read_text())['elements'];assert len(elements)==256
with (d/'PnP_SMT_KiCad.csv').open(encoding='utf-8-sig',newline='') as fp:pnp=list(csv.DictReader(fp))
assert len(pnp)==110 and all(p['Side']=='bottom' for p in pnp)
assert {p['Ref'] for p in pnp}=={p['ref'] for p in parts if p['kind'] not in ('T','CP','JLOG','JPWR')}
for row in pnp:
    p=by[row['Ref']];assert abs(float(row['PosX'])-p['x'])<1e-5 and abs(float(row['PosY'])+p['y'])<1e-5
drc=json.loads((d/'DRC.json').read_text());assert not drc['violations'] and not drc['unconnected_items'] and not drc['schematic_parity']
erc=json.loads((d/'ERC.json').read_text());assert not any(s.get('violations') for s in erc['sheets'])
source=root/'outputs/polygon_panels/panel_8faces_16ch/panel_8faces_16ch.kicad_pcb'
digest=hashlib.sha256(source.read_bytes()).hexdigest();assert digest=='f3f6dd83527634e501152ea15e70d8534f6eeb01c2caa54a2b335c86cc029cfd'
result={'status':'PASS','electrical_pads_compared':checked,'connected_pads':functional,'explicit_nc_pads':checked-functional,'mechanical_NPTH':mechanical,'SMT_components':len(pnp),'THT_components':38,'tracks':sum(not isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()),'vias':sum(isinstance(t,pcbnew.PCB_VIA) for t in b.GetTracks()),'channel_map_bijective':True,'mount_strips_no_electrical_pads_or_tracks':True,'original_pcb_sha256_unchanged':digest,'ERC_violations':0,'DRC_violations':0,'schematic_parity':0}
(d/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
