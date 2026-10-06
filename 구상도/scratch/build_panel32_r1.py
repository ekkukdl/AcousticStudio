"""Generate an independent KiCad 10 4x8 panel from the P0 routed channel cells.

Run with KiCad's bundled Python. All generated design files stay in panel_8faces_32ch_R1.
The two 16-channel electrical banks share GND only; bank power and timing are fed externally.
"""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import csv
import hashlib
import json
import math
import re
import shutil
import uuid
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/polygon_panels/panel_8faces_16ch'
DEST = ROOT / 'outputs/panel_8faces_32ch_R1'
NAME = 'panel_8faces_32ch_R1'
UUID_NS = uuid.UUID('f9aa2a7d-f9c3-4a0f-87d3-725ebca75b02')
PARAMS = {'revision':'R1', 'faces':8, 'columns':4, 'rows':8,
          'board_width_mm':84.0, 'board_length_mm':224.0, 'board_thickness_mm':1.6,
          'column_pitches_mm':[18.0,22.0,18.0], 'row_pitch_mm':20.0,
          'mounting_strip_mm':22.0, 'transducer_diameter_mm':16.0,
          'transducer_height_mm':12.5, 'emitting_plane_separation_mm':210.0}
if (DEST / 'parameters.json').exists():
    PARAMS.update(json.loads((DEST / 'parameters.json').read_text(encoding='utf-8')))
PARAMS.pop('column_pitch_mm',None)

def uid(key): return str(uuid.uuid5(UUID_NS, key))
def quote(s): return json.dumps(str(s), ensure_ascii=False)
class Quoted(str): pass
def parse(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text)
    stack=[]; result=None
    for tok in tokens:
        if tok=='(':
            node=[]
            if stack: stack[-1].append(node)
            else: result=node
            stack.append(node)
        elif tok==')': stack.pop()
        else: stack[-1].append(Quoted(json.loads(tok)) if tok.startswith('"') else tok)
    return result
def dump(node):
    if isinstance(node,list): return '('+' '.join(dump(x) for x in node)+')'
    return quote(node) if isinstance(node,Quoted) else str(node)
def children(node,key): return [x for x in node if isinstance(x,list) and x and x[0]==key]
def child(node,key): return next(iter(children(node,key)),None)

def reference(ref,bank):
    n=int(re.search(r'\d+',ref).group())
    if ref.startswith('T'):
        return 'T'+str(((n-1)//2)*4+bank*2+(n-1)%2+1)
    if ref.startswith('U'):
        return 'U'+str(n+bank*2 if n<=2 else n+2+bank*8)
    if ref.startswith('R'):return 'R'+str(n+bank*25)
    if ref.startswith('C'):return 'C'+str(n+bank*20)
    if ref.startswith('Q'):return 'Q'+str(bank+1)
    if ref=='J1':return 'J'+str(bank+1)
    if ref=='J2':return 'J'+str(bank+3)
    return ref
def net_name(name,bank):
    name=name.lstrip('/')
    suffix='A' if bank==0 else 'B'
    if name=='GND':return 'GND'
    if name.startswith(('IN','OUT')) and name[2 if name.startswith('IN') else 3:].isdigit():
        prefix='IN' if name.startswith('IN') else 'OUT'
        n=int(name[len(prefix):]); mapped=(n//2)*4+bank*2+n%2
        return f'{prefix}{mapped:02d}'
    if name=='DATA_A':return f'DATA_{suffix}0'
    if name=='DATA_B':return f'DATA_{suffix}1'
    if name=='+5V':return f'+5V_{suffix}'
    return f'{name}_{suffix}'

manifest=json.loads((SOURCE/'component_manifest.json').read_text(encoding='utf-8'))
purchase_candidates={}
for filename in ('BOM_SMT.csv','BOM_THT.csv'):
    with (SOURCE.parent/'pcba_8faces_16boards'/filename).open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            for ref in row['Designator'].split(','):purchase_candidates[ref]=row
source_symbols=parse((SOURCE/f'{"panel_8faces_16ch"}.kicad_sch').read_text(encoding='utf-8'))
libs={str(x[1]).split(':')[-1]:deepcopy(x) for x in children(child(source_symbols,'lib_symbols'),'symbol')}
# Compact, standard passive drawings; pin numbers stay identical.
device=parse(Path('C:/Program Files/KiCad/10.0/share/kicad/symbols/Device.kicad_sym').read_text(encoding='utf-8'))
for kind,orig in [('R','R_Small_US'),('C','C_Small')]:
    sym=deepcopy(next(s for s in children(device,'symbol') if s[1]==orig))
    sym[1]=Quoted('Levitation:'+kind)
    for sub in children(sym,'symbol'): sub[1]=Quoted(str(sub[1]).replace(orig,kind))
    libs[kind]=sym

parts=[]
for bank in (0,1):
    for original in manifest:
        if original['ref'].startswith('H'): continue
        p=deepcopy(original)
        p['source_ref']=original['ref'];p['bank']=bank
        p['ref']=reference(original['ref'],bank)
        p['uuid']=uid('symbol:'+p['ref'])
        p['nets']={pin:net_name(n,bank) if n else None for pin,n in p['nets'].items()}
        if p['kind']=='595':p['value']='74HCT595D';p['mpn']='74HCT595D,118';p['manufacturer']='Nexperia';p['datasheet']='https://assets.nexperia.com/documents/data-sheet/74HC_HCT595.pdf'
        elif p['kind']=='DRV':p['value']='TC4427A';p['mpn']='TC4427ACOA713';p['manufacturer']='Microchip';p['datasheet']='https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/TC4426A-TC4427A-TC4428A-1.5A-Dual-High-Speed-Power-MOSFET-Drivers-20001423.pdf'
        elif p['kind']=='Q':p['mpn']='MMBT3904,215';p['manufacturer']='Nexperia';p['datasheet']='https://assets.nexperia.com/documents/data-sheet/MMBT3904.pdf'
        else:p['mpn']='';p['manufacturer']='';p['datasheet']=''
        candidate=purchase_candidates.get(original['ref'],{})
        if not p['mpn'] and candidate.get('MPN'):
            p['mpn']=candidate['MPN'];p['manufacturer']=candidate['Manufacturer']
        p['lcsc']=candidate.get('LCSC Part #','')
        p['x']=original['x']-2+40*bank+(PARAMS['board_width_mm']-84)/2
        p['y']=original['y']+(PARAMS['board_length_mm']-180)/2
        parts.append(p)
part_by_ref={p['ref']:p for p in parts}
root_uuid=uid('root')

def fx(size=1.0,justify=''):
    return f'(effects (font (size {size} {size})){" (justify "+justify+")" if justify else ""})'
schematic_items=[]
def snap(n):return round(n/1.27)*1.27
def label(net,x,y,angle=0):
    schematic_items.append(f'(label {quote(net)} (at {x:.4f} {y:.4f} {angle}) {fx(1.27,"left" if angle==0 else "right")} (uuid {uid("label:"+net+":"+str(x)+":"+str(y))}))')
def wire(x1,y1,x2,y2):
    if abs(x1-x2)+abs(y1-y2)<1e-6:return
    schematic_items.append(f'(wire (pts (xy {x1:.4f} {y1:.4f}) (xy {x2:.4f} {y2:.4f})) (stroke (width 0) (type default)) (uuid {uid("wire:"+str((x1,y1,x2,y2)))}))')
def text(s,x,y,size=1.4):
    schematic_items.append(f'(text {quote(s)} (at {x} {y} 0) {fx(size,"left")} (uuid {uid("text:"+s+str(x)+str(y))}))')
def rectangle(x1,y1,x2,y2,key):
    schematic_items.append(f'(rectangle (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.254) (type default)) (fill (type none)) (uuid {uid(key)}))')
def pin_offsets(kind):
    out={}
    for sub in children(libs[kind],'symbol'):
        for pin in children(sub,'pin'):
            at=child(pin,'at');n=child(pin,'number')[1]
            out[str(n)]=(float(at[1]),-float(at[2]))
    return out
def add_symbol(p,x,y,auto_labels=True):
    x=snap(x);y=snap(y)
    kind=p['kind'];ref=p['ref'];libid='Levitation:'+kind
    footprint={'595':'SOIC16','DRV':'SOIC8','T':'V40AN16T_P10','R':'R0805','C':'C0805','CP':'CP_Radial_D6.3_P2.5','Q':'SOT23','JLOG':'Header2x05','JPWR':'Header1x03','MH':'Mount_M3'}.get(kind)
    if footprint is None:raise ValueError(kind)
    props=[]
    h={'595':12.5,'DRV':6.0,'JLOG':16.0,'JPWR':7.0,'CP':4.5}.get(kind,3.5)
    for k,v,px,py,hide in [('Reference',ref,x,y-h,False),('Value',p['value'],x,y+h,False),('Footprint','Levitation:'+footprint,x,y,True),('Datasheet',p.get('datasheet',''),x,y,True),('MPN',p.get('mpn',''),x,y,True),('Manufacturer',p.get('manufacturer',''),x,y,True)]:
        if k in ('MPN','Manufacturer') and not v:continue
        just=''
        if kind in ('R','C') and k in ('Reference','Value'):
            px=x+3.5;py=y-1.27 if k=='Reference' else y+1.27;just=' (justify left)'
        props.append(f'(property {quote(k)} {quote(v)} (at {px} {py} 0) (effects (font (size 1.0 1.0)){just}{" (hide yes)" if hide else ""}))')
    pins=pin_offsets(kind)
    schematic_items.append(f'(symbol (lib_id {quote(libid)}) (at {x} {y} 0) (unit 1) (in_bom {"no" if kind=="MH" else "yes"}) (on_board yes) (dnp no) (uuid {p["uuid"]}) '+''.join(props)+''.join(f'(pin {quote(n)} (uuid {uid("pin:"+ref+":"+n)}))' for n in pins)+f'(instances (project {quote(NAME)} (path {quote("/"+root_uuid)} (reference {quote(ref)}) (unit 1)))))')
    for pin,(dx,dy) in pins.items():
        net=p['nets'].get(pin)
        if not net:
            schematic_items.append(f'(no_connect (at {x+dx:.4f} {y+dy:.4f}) (uuid {uid("nc:"+ref+":"+pin)}))')
        elif auto_labels:
            label(net,x+dx,y+dy,180 if dx<0 else 0)
    return {n:(x+dx,y+dy) for n,(dx,dy) in pins.items()}

def passive_pair(p,x,y):
    x=snap(x);y=snap(y)
    pins=add_symbol(p,x,y,False)
    # Standard C/R symbols have vertical pins.
    for n,(px,py) in pins.items():
        if abs(px-x)>abs(py-y):
            endx=px+(-2.54 if px<x else 2.54)
            wire(px,py,endx,py);label(p['nets'][n],endx,py,180 if px<x else 0)
        else:
            endy=py+(-2.54 if py<y else 2.54)
            wire(px,py,px,endy);label(p['nets'][n],px,endy)

for bank in (0,1):
    x0=bank*290
    for half in (0,1):
        y0=30+half*122
        rectangle(x0+12,y0,x0+286,y0+115,f'block{bank}{half}')
        chans=[(n//2)*4+bank*2+n%2 for n in range(half*8,half*8+8)]
        text(f'BANK {"A" if bank==0 else "B"} / DATA_{"A" if bank==0 else "B"}{half} / local outputs '+','.join(str(n) for n in chans),x0+16,y0+7)
        add_symbol(part_by_ref[reference('U'+str(half+1),bank)],x0+34,y0+32)
        passive_pair(part_by_ref[reference('C'+str(9+half),bank)],x0+34,y0+72)
        for d in range(4):
            n=half*8+d*2
            x=x0+79+d*54;y=y0+32
            driver=part_by_ref[reference('U'+str(3+half*4+d),bank)]
            add_symbol(driver,x,y)
            for c in (0,1):
                trans=part_by_ref[reference('T'+str(n+c+1),bank)]
                add_symbol(trans,x+18,y+24+c*18)
                res=part_by_ref[reference('R'+str(n+c+1),bank)]
                passive_pair(res,x-10,y+24+c*18)
            passive_pair(part_by_ref[reference('C'+str(1+half*4+d),bank)],x-6,y+65)
            passive_pair(part_by_ref[reference('C'+str(11+half*4+d),bank)],x+20,y+65)

# Connector, ARM and clock conditioning bank; all items still carry explicit net names.
for bank in (0,1):
    x0=bank*290
    rectangle(x0+12,278,x0+286,397,f'controls{bank}')
    text(f'BANK {"A" if bank==0 else "B"}: 5V logic / separate driver supply / ARM defaults OFF',x0+16,286)
    add_symbol(part_by_ref[reference('J1',bank)],x0+37,312)
    add_symbol(part_by_ref[reference('J2',bank)],x0+37,367)
    add_symbol(part_by_ref[reference('Q1',bank)],x0+103,305)
    for r,x,y in [(17,82,337),(18,106,337),(19,130,337),(20,163,306),(21,163,337),(22,199,306),(23,235,306),(24,199,337),(25,235,337)]:
        passive_pair(part_by_ref[reference('R'+str(r),bank)],x0+x,y)
    passive_pair(part_by_ref[reference('C19',bank)],x0+112,374)
    passive_pair(part_by_ref[reference('C20',bank)],x0+163,374)
    for net,xx in [('GND',201),('+5V_'+('A' if bank==0 else 'B'),229),('DRV_VDD_'+('A' if bank==0 else 'B'),257)]:
        if net=='GND' and bank==1:continue
        p={'ref':f'#FLG{bank*3+xx}','kind':'PWR','value':'PWR_FLAG','uuid':uid('flag:'+net),'nets':{'1':net}}
        # Source library's power flag has no physical footprint.
        px=snap(x0+xx);py=snap(374)
        schematic_items.append(f'(symbol (lib_id "Levitation:FLAG") (at {px} {py} 0) (unit 1) (in_bom no) (on_board no) (uuid {p["uuid"]}) (property "Reference" {quote(p["ref"])} (at {px} {py} 0) (effects (font (size 1 1)) (hide yes))) (property "Value" "PWR_FLAG" (at {px} {py+3} 0) {fx(1)}) (instances (project {quote(NAME)} (path {quote("/"+root_uuid)} (reference {quote(p["ref"])}) (unit 1)))))')
        ox,oy=pin_offsets('FLAG')['1'];label(net,px+ox,py+oy)

for i in range(1,5):
    add_symbol({'ref':'H'+str(i),'kind':'MH','value':'M3_NPTH','uuid':uid('symbol:H'+str(i)),'nets':{}},40+i*25,407)

DEST.mkdir(parents=True,exist_ok=True)
for folder in ('Levitation.pretty','models'):
    shutil.copytree(SOURCE/folder,DEST/folder,dirs_exist_ok=True)
for file in ('fp-lib-table','sym-lib-table'):
    shutil.copy2(SOURCE/file,DEST/file)
header=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {root_uuid}) (paper "User" 620 460) (title_block (title "32CH ultrasonic panel - 4x8 - single PCB per face") (date "2026-10-06") (rev "R1") (comment 1 "Prototype: 8 panels / 256 channels. External timing and power required."))'
(DEST/f'{NAME}.kicad_sch').write_text(header+'\n(lib_symbols\n'+'\n'.join(dump(s) for s in libs.values())+')\n'+'\n'.join(schematic_items)+'\n)\n',encoding='utf-8')
libsyms=deepcopy(list(libs.values()))
for sym in libsyms:sym[1]=Quoted(str(sym[1]).split(':')[-1])
(DEST/'Levitation.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor")\n'+'\n'.join(dump(s) for s in libsyms)+'\n)\n',encoding='utf-8')
proj=json.loads((SOURCE/'panel_8faces_16ch.kicad_pro').read_text(encoding='utf-8'))
proj['meta']['filename']=NAME+'.kicad_pro'
for cls in proj.get('net_settings',{}).get('classes',[]):
    cls['clearance']=max(cls.get('clearance',0.2),0.2)
proj.get('net_settings',{})['netclass_patterns']=[{'netclass':'Power','pattern':'/DRV_VDD_*'},{'netclass':'LogicPower','pattern':'/+5V_*'},{'netclass':'LogicPower','pattern':'/GND'}]
(DEST/f'{NAME}.kicad_pro').write_text(json.dumps(proj,ensure_ascii=False,indent=2),encoding='utf-8')

# PCB cell reuse preserves existing pin escape routing, then fills one common ground plane.
b=pcbnew.LoadBoard(str(SOURCE/'panel_8faces_16ch.kicad_pcb'))
templates={f.GetReference():f for f in b.GetFootprints()}
board=pcbnew.BOARD()
board.SetDesignSettings(b.GetDesignSettings())
board.SetCopperLayerCount(2)
board.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(1.6))
netobjs={}
for p in parts:
    for n in p['nets'].values():
        if n and n not in netobjs:
            nn='/'+n
            obj=pcbnew.NETINFO_ITEM(board,nn);board.Add(obj);netobjs[n]=obj

for p in parts:
    fp=pcbnew.Cast_to_FOOTPRINT(templates[p['source_ref']].Duplicate(False))
    fp.SetParent(board)
    fp.SetReference(p['ref']);fp.SetValue(p['value'])
    fp.SetUuid(pcbnew.KIID(uid('footprint:'+p['ref'])))
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(p['x']),pcbnew.FromMM(p['y'])))
    path=pcbnew.KIID_PATH();path.push_back(pcbnew.KIID(root_uuid));path.push_back(pcbnew.KIID(p['uuid']));fp.SetPath(path)
    fp.SetSheetname(NAME);fp.SetSheetfile(NAME+'.kicad_sch')
    for pad in fp.Pads():
        pad.SetUuid(pcbnew.KIID(uid('pad:'+p['ref']+':'+pad.GetNumber())))
        nn=p['nets'].get(pad.GetNumber())
        if nn:pad.SetNet(netobjs[nn])
        else:
            pinname=None
            for sub in children(libs[p['kind']],'symbol'):
                for pin in children(sub,'pin'):
                    if child(pin,'number')[1]==pad.GetNumber():pinname=child(pin,'name')[1]
            nn=f'unconnected-({p["ref"]}-{pinname}-Pad{pad.GetNumber()})'
            if nn not in netobjs:
                obj=pcbnew.NETINFO_ITEM(board,nn);board.Add(obj);netobjs[nn]=obj
            pad.SetNet(netobjs[nn])
    board.Add(fp)
    # Source references are offset deliberately; keep the new text at the same relative location.

for bank in (0,1):
    delta=pcbnew.VECTOR2I(pcbnew.FromMM(-2+40*bank+(PARAMS['board_width_mm']-84)/2),pcbnew.FromMM((PARAMS['board_length_mm']-180)/2))
    transducer_pads={(pad.GetPosition().x,pad.GetPosition().y) for ref,fp in templates.items() if ref.startswith('T') for pad in fp.Pads()}
    for original in b.GetTracks():
        nn=net_name(original.GetNetname(),bank)
        item=original.Duplicate()
        if isinstance(original,pcbnew.PCB_VIA):item=pcbnew.Cast_to_PCB_VIA(item)
        else:item=pcbnew.Cast_to_PCB_TRACK(item)
        item.SetParent(board);item.Move(delta);item.SetNet(netobjs[nn])
        item.SetUuid(pcbnew.KIID(uid('track:'+str(bank)+':'+original.m_Uuid.AsString())))
        board.Add(item)

w=PARAMS['board_width_mm'];h=PARAMS['board_length_mm'];strip=PARAMS['mounting_strip_mm']
for i,((x1,y1),(x2,y2)) in enumerate([((0,0),(w,0)),((w,0),(w,h)),((w,h),(0,h)),((0,h),(0,0))]):
    edge=pcbnew.PCB_SHAPE(board);edge.SetShape(pcbnew.SHAPE_T_SEGMENT);edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x1),pcbnew.FromMM(y1)));edge.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x2),pcbnew.FromMM(y2)));edge.SetWidth(pcbnew.FromMM(0.05));board.Add(edge)
for i,(xx,yy) in enumerate([(6,11),(w-6,11),(6,h-11),(w-6,h-11)],1):
    fp=pcbnew.Cast_to_FOOTPRINT(templates['H1'].Duplicate(False));fp.SetParent(board);fp.SetReference('H'+str(i));fp.SetValue('M3_NPTH');fp.SetUuid(pcbnew.KIID(uid('hole:'+str(i))));path=pcbnew.KIID_PATH();path.push_back(pcbnew.KIID(root_uuid));path.push_back(pcbnew.KIID(uid('symbol:H'+str(i))));fp.SetPath(path);fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(xx),pcbnew.FromMM(yy)))
    for pad in fp.Pads():pad.SetNetCode(0);pad.SetUuid(pcbnew.KIID(uid('holepad:'+str(i))))
    board.Add(fp)

for layer in (pcbnew.F_Cu,pcbnew.B_Cu):
    zone=pcbnew.ZONE(board);zone.SetLayer(layer);zone.SetNet(netobjs['GND']);zone.SetLocalClearance(pcbnew.FromMM(0.25));zone.SetThermalReliefGap(pcbnew.FromMM(0.25));zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.3));zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    outline=zone.Outline();outline.NewOutline()
    for xx,yy in [(0.5,strip),(w-0.5,strip),(w-0.5,h-strip),(0.5,h-strip)]:outline.Append(pcbnew.FromMM(xx),pcbnew.FromMM(yy))
    board.Add(zone)
    for edge,y1,y2 in [('TOP',0,strip),('BOTTOM',h-strip,h)]:
        keep=pcbnew.ZONE(board);keep.SetLayer(layer);keep.SetIsRuleArea(True);keep.SetDoNotAllowTracks(True);keep.SetDoNotAllowVias(True);keep.SetDoNotAllowPads(False);keep.SetDoNotAllowZoneFills(True);keep.SetDoNotAllowFootprints(False)
        poly=keep.Outline();poly.NewOutline()
        for xx,yy in [(0,y1),(w,y1),(w,y2),(0,y2)]:poly.Append(pcbnew.FromMM(xx),pcbnew.FromMM(yy))
        board.Add(keep)
for layer in (pcbnew.F_SilkS,pcbnew.B_SilkS):
    for s,xx,yy in [('32CH R1 / 4x8',w/2,h-strip-1)]:
        t=pcbnew.PCB_TEXT(board);t.SetText(s);t.SetLayer(layer);t.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(xx),pcbnew.FromMM(yy)));t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0),pcbnew.FromMM(1.0)));t.SetTextThickness(pcbnew.FromMM(0.15));t.SetMirrored(layer==pcbnew.B_SilkS);board.Add(t)
board.BuildConnectivity()
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(str(DEST/f'{NAME}.kicad_pcb'),board)
# Preserve custom symbol fields in PCB and write the intended project settings after SaveBoard.
pcb_ast=parse((DEST/f'{NAME}.kicad_pcb').read_text(encoding='utf-8'))
for fp in children(pcb_ast,'footprint'):
    props={str(p[1]):p for p in children(fp,'property')}
    ref=str(props['Reference'][2])
    if ref not in part_by_ref:continue
    p=part_by_ref[ref]
    for field,val in [('Datasheet',p.get('datasheet','')),('MPN',p.get('mpn','')),('Manufacturer',p.get('manufacturer',''))]:
        if field not in props and not val:continue
        if field in props:props[field][2]=Quoted(val)
        else:
            prop=deepcopy(props['Datasheet']);prop[1]=Quoted(field);prop[2]=Quoted(val)
            uu=child(prop,'uuid')
            if uu:uu[1]=uid('field:'+ref+':'+field)
            fp.append(prop)
# UUIDs of copied graphics/fields/models must be distinct even when their shapes are reused.
def unique_child_uuids(node,prefix):
    for idx,entry in enumerate(node):
        if isinstance(entry,list):
            if entry and entry[0]=='uuid':entry[1]=uid(prefix+':'+str(idx))
            else:unique_child_uuids(entry,prefix+':'+str(idx))
for fp in children(pcb_ast,'footprint'):
    ref=str(next(p[2] for p in children(fp,'property') if p[1]=='Reference'))
    for entry in fp[2:]:
        if isinstance(entry,list) and entry and entry[0] not in ('uuid','path','pad'):
            unique_child_uuids(entry,'graphic:'+ref+':'+str(fp.index(entry)))
(DEST/f'{NAME}.kicad_pcb').write_text(dump(pcb_ast)+'\n',encoding='utf-8')
(DEST/f'{NAME}.kicad_pro').write_text(json.dumps(proj,ensure_ascii=False,indent=2),encoding='utf-8')

# Parametric geometry and physical-output map: row-major T1..T32, bank mux order remains explicit.
elements=[];local=[]
ap=PARAMS['emitting_plane_separation_mm']/2
for face in range(PARAMS['faces']):
    angle=2*math.pi*face/PARAMS['faces'];nr=(math.cos(angle),math.sin(angle));tangent=(-math.sin(angle),math.cos(angle))
    for r in range(8):
        for c in range(4):
            idx=r*4+c;tx=part_by_ref['T'+str(idx+1)]
            transverse=tx['x']-w/2;z=tx['y']-h/2
            bank=c//2;bankidx=r*2+c%2;reg=bank*2+bankidx//8
            e={'channel':face*32+idx,'face':face,'local_channel':idx,'reference':'T'+str(idx+1), 'row':r,'column':c,'bank':'AB'[bank], 'data_line_on_face':reg,'shift_register_output':bankidx%8,'fpga_physical_channel':face*32+reg*8+bankidx%8,'position_mm':[ap*nr[0]+transverse*tangent[0],ap*nr[1]+transverse*tangent[1],z],'normal':[-nr[0],-nr[1],0]}
            elements.append(e)
            if face==0:local.append(e)
geometry={'units':'mm','coordinate_system':'Z=0 at board mid-height; XY origin at tunnel centre; face0 normal toward -X','status':'prototype_geometry_not_acoustically_validated', 'parameters':PARAMS,'elements':elements}
(DEST/'array_positions_256.json').write_text(json.dumps(geometry,ensure_ascii=False,indent=2),encoding='utf-8')
physical_map=[None]*256
for e in elements:physical_map[e['fpga_physical_channel']]=e['channel']
(DEST/'physical_to_software_channel_map.json').write_text(json.dumps({'definition':'map[physical_frame_channel] = software_channel; valid only after FPGA DATA/header assignment matches documented face/reg order','channel_map':physical_map},indent=2),encoding='utf-8')
with (DEST/'channel_map.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=[k for k in local[0] if k not in ('position_mm','normal')]);writer.writeheader();writer.writerows({k:v for k,v in e.items() if k not in ('position_mm','normal')} for e in elements)
(DEST/'component_manifest.json').write_text(json.dumps(parts,ensure_ascii=False,indent=2),encoding='utf-8')
(DEST/'parameters.json').write_text(json.dumps(PARAMS,ensure_ascii=False,indent=2),encoding='utf-8')
gap=2*(ap+PARAMS['transducer_height_mm'])*math.sin(math.pi/8)-w*math.cos(math.pi/8)
(DEST/'geometry_summary.json').write_text(json.dumps({'pcb_edge_gap_mm':gap,'gap_basis':'nearest adjacent PCB front-plane edge points; not optical field of view','emitting_plane_separation_mm':2*ap,'pcb_front_apothem_mm':ap+12.5,'transducer_envelope_mm':[74,156],'mount_strips_each_mm':strip,'mount_holes_mm':[[6,11],[w-6,11],[6,h-11],[w-6,h-11]],'notes':['object size and camera position unknown; full-object visibility has not been demonstrated','mechanical frame and rotating camera structure are outside this PCB revision']},indent=2),encoding='utf-8')
print(json.dumps({'output':str(DEST),'parts':len(parts),'board_mm':[w,h],'gap_mm':gap,'source_sha256':hashlib.sha256((SOURCE/'panel_8faces_16ch.kicad_pcb').read_bytes()).hexdigest()},ensure_ascii=True))
