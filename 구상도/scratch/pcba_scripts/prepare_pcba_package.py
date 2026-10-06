import csv, json, re, hashlib
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / 'outputs/pcb/polygon_panels/pcba_8faces_16boards'
OUT.mkdir(parents=True, exist_ok=True)
parts = json.loads((ROOT/'scratch/pcba_inputs/pcba_parts_8f.json').read_text(encoding='utf-8'))
sortkey = lambda p: (re.match(r'[A-Z]+',p['ref'])[0],int(re.search(r'\d+',p['ref'])[0]))
parts.sort(key=sortkey)
# Purchase candidates, not a claim that procurement or production validation is complete.
specs = [
 ('100nF', '100nF 50V X7R 10% 0805', 'YAGEO','CC0805KRX7R9BB104','C49678','https://www.lcsc.com/product-detail/C49678.html','C9/C10 increased from 16V to 50V; same footprint'),
 ('1uF', '1uF 50V X7R 10% 0805', 'CCTC','TCC0805X7R105K500DT','C376926','https://www.lcsc.com/product-detail/C376926.html','Check capacitance under applied DC bias'),
 ('10uF','10uF >=16V 0805','Murata','GRM21BR61E106KA73L','','https://ww1.microchip.com/downloads/en/DeviceDoc/50002394A.pdf','25V candidate; confirm current manufacturer specification and supply'),
 ('220uF','220uF 25V radial D6.3mm P2.5mm','Rubycon','25YXJ220M6.3X11','C88729','https://www.lcsc.com/product-detail/C88729.html','THT; positive pin 1 to DRV_VDD'),
 ('10k','10k 1% 0805 0.125W','YAGEO','RC0805FR-0710KL','','https://www.yageogroup.com/component-documentation/download/specsheet/RC0805FR-0710KL','Supplier catalog matching required'),
 ('100k','100k 1% 0805 0.125W','YAGEO','RC0805FR-07100KL','','https://www.yageogroup.com/component-documentation/download/specsheet/RC0805FR-07100KL','Supplier catalog matching required'),
 ('33R','33 ohm 1% 0805 0.125W','YAGEO','RC0805FR-0733RL','','https://www.yageogroup.com/component-documentation/download/specsheet/RC0805FR-0733RL','Supplier catalog matching required'),
 ('SN74HCT595D','74HCT595 SO16 shift register','Nexperia','74HCT595D,118','C282339','https://assets.nexperia.com/documents/data-sheet/74HC_HCT595.pdf','Candidate substitution for source SN74HCT595D; SO16 3.9x9.9mm P1.27; verify supplier mapping'),
 ('TC4427ACOA','TC4427A dual non-inverting driver SOIC8','Microchip','TC4427ACOA713','C144234','https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/20001423J.pdf','713 tape/reel candidate; confirm non-inverting variant'),
 ('MMBT3904','MMBT3904 NPN SOT23','Nexperia','MMBT3904,215','','https://assets.nexperia.com/documents/data-sheet/MMBT3904.pdf','Pin1 base; pin2 emitter; pin3 collector; supplier matching required'),
 ('FPGA_SIGNAL_3V3','Male straight header 2x5 P2.54mm','Vendor selection','','','','THT; unshrouded; confirm mating connector and orientation'),
 ('POWER_INPUT','Male straight header 1x3 P2.54mm','Vendor selection','','','','THT; confirm current rating and mating connector'),
 ('V40AN16T','40kHz transmitter D16mm pin pitch 10mm','Supplier confirmation','','','','THT; source V40AN16T name not manufacturer-verified; customer-supplied option; phase polarity test required'),
]
groups=[]
for key,comment,manufacturer,mpn,code,url,note in specs:
    pp=[p for p in parts if p['value'].split()[0]==key]
    assert pp, key
    assert len({p['footprint'] for p in pp})==1
    groups.append(dict(comment=comment,refs=','.join(p['ref'] for p in pp),footprint=pp[0]['footprint'],manufacturer=manufacturer,mpn=mpn,code=code,qty=len(pp),smd=pp[0]['smd'],url=url,note=note))
assert sum(g['qty'] for g in groups)==74
header=['Comment','Designator','Footprint','Manufacturer','MPN','LCSC Part #','Quantity']
row=lambda g:[g['comment'],g['refs'],g['footprint'],g['manufacturer'],g['mpn'],g['code'],g['qty']]
tables={
 'BOM_SMT':[header]+[row(g) for g in groups if g['smd']],
 'BOM_THT':[header]+[row(g) for g in groups if not g['smd']],
 'BOM_ALL':[header]+[row(g) for g in groups],
 'Parts_16_boards':[['Comment','Designator','Footprint','Manufacturer','MPN','LCSC Part #','Quantity_per_board','Board_count','Total_quantity','Assembly','Source','Notes']]+[[*row(g)[:6],g['qty'],16,g['qty']*16,'SMT' if g['smd'] else 'THT',g['url'],g['note']] for g in groups],
}
native=list(csv.DictReader((ROOT/'scratch/pcba_inputs/pcba_native_smt.csv').open(encoding='utf-8',newline='')))
assert len(native)==55
lookup={p['ref']:p for p in parts}
pnp=[]
for n in native:
    p=lookup[n['Ref']]
    assert p['smd'] and n['Side']=='bottom'
    assert abs(float(n['PosX'])-p['x_mm'])<1e-5 and abs(float(n['PosY'])+p['y_mm'])<1e-5
    assert abs(float(n['Rot'])-p['rotation_deg'])<1e-5
    pnp.append([p['ref'],float(n['PosX']),float(n['PosY']),float(n['Rot']),'Bottom'])
tables['PnP_SMT']=[['Designator','Mid X','Mid Y','Rotation','Layer']]+pnp
tht=[]
for p in parts:
    if p['smd']: continue
    pads=p['pads']; pin1=next(x for x in pads if x['number']=='1')
    cx=sum(x['x_mm'] for x in pads)/len(pads); cy=-sum(x['y_mm'] for x in pads)/len(pads)
    note='Transmitter pin1 driven; pin2 GND; verify acoustic phase' if p['ref'].startswith('T') else ('Electrolytic pin1 positive DRV_VDD; pin2 GND' if p['ref']=='C19' else 'Header pin numbers must follow source PCB/netlist')
    tht.append([p['ref'],p['value'],p['side'],p['x_mm'],-p['y_mm'],round(cx,5),round(cy,5),p['rotation_deg'],pin1['x_mm'],-pin1['y_mm'],pin1['net'],note])
tables['THT_position_guide']=[['Designator','Value','Layer','Footprint_origin_X_mm','Footprint_origin_Y_mm','Pad_centroid_X_mm','Pad_centroid_Y_mm','KiCad_rotation_deg','Pin1_X_mm','Pin1_Y_mm','Pin1_net','Instruction']]+tht
assert set(x[0] for x in pnp)=={p['ref'] for p in parts if p['smd']}
assert len(tht)==19
(ROOT/'scratch/pcba_artifact/tables.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding='utf-8')
sources=['outputs/pcb/polygon_panels/panel_8faces_16ch/panel_8faces_16ch.kicad_pcb','outputs/pcb/polygon_panels/panel_8faces_16ch/schematic.net.xml','outputs/pcb/polygon_panels/gerber_quotes/panel_8faces_16ch_Gerber_P0_quote.zip']
manifest={'status':'quotation draft, not production release','boards':16,'board_size_mm':[48,180,1.6],'channels_per_board':16,'total_channels':256,'parts_per_board':74,'smt_per_board':55,'tht_per_board':19,'all_parts_16_boards':1184,'coordinates':'mm; same absolute XY system as original Gerbers; Y negative; Bottom not X-mirrored','source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},'unresolved':['Vendor reported 0.002mm clearance issue not resolved','Supplier confirmation for blank catalog IDs, connectors and V40AN16T','Candidate MPN substitutions and component rotations require factory preview','THT service including transducers must be separately confirmed']}
(OUT/'validation_and_sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'output':str(OUT),'groups':len(groups),'SMT':55,'THT':19,'total_at_16_boards':1184},ensure_ascii=False))
