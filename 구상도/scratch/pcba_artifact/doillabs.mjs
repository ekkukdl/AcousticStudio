import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile,FileBlob} from '@oai/artifact-tool';
const root=process.cwd();
const out=path.join(root,'outputs/pcb/polygon_panels/pcba_8faces_16boards/DOILLABS');
await fs.mkdir(out,{recursive:true});
const parts=JSON.parse(await fs.readFile(path.join(root,'scratch/pcba_inputs/pcba_parts_8f.json'),'utf8'));
const tables=JSON.parse(await fs.readFile(new URL('./tables.json',import.meta.url),'utf8'));
const lookup=new Map();
for(const r of tables.BOM_ALL.slice(1)) for(const ref of r[1].split(','))lookup.set(ref,r);
const ordered=[...parts].sort((a,b)=>a.ref.match(/[A-Z]+/)[0].localeCompare(b.ref.match(/[A-Z]+/)[0])||Number(a.ref.match(/\d+/)[0])-Number(b.ref.match(/\d+/)[0]));
const pkg=p=>({C0805:'0805',R0805:'0805',SOIC8:'SOIC-8',SOIC16:'SOIC-16',SOT23:'SOT-23','CP_Radial_D6.3_P2.5':'Radial D6.3 P2.5 (THT)',Header2x05:'2x5 P2.54 (THT)',Header1x03:'1x3 P2.54 (THT)',V40AN16T_P10:'D16 P10 (THT)'}[p.footprint]||p.footprint);
const value=p=>p.ref.startsWith('C')?lookup.get(p.ref)[0].split(' ').slice(0,2).join(' '):p.ref.startsWith('R')?p.value:p.ref.startsWith('U')? (p.ref==='U1'||p.ref==='U2'?'74HCT595D':'TC4427A'):p.value;
const bom=ordered.map(p=>{const r=lookup.get(p.ref);return [p.ref,value(p),pkg(p),1,(p.smd?'SMT: ':'THT hand solder: ')+r[0]+(!p.smd&&p.ref.startsWith('T')?' / manufacturer and phase polarity confirmation required':''),r[3]==='Vendor selection'||r[3]==='Supplier confirmation'?'':r[3],r[4]]});
const pnp=ordered.map(p=>{
 let x=p.x_mm,y=180-p.y_mm;
 if(!p.smd){x=p.pads.reduce((s,q)=>s+q.x_mm,0)/p.pads.length;y=180-p.pads.reduce((s,q)=>s+q.y_mm,0)/p.pads.length;}
 return [p.ref,value(p),pkg(p),Math.round(x*1e6)/1e6,Math.round(y*1e6)/1e6,(p.rotation_deg%360+360)%360,p.side];
});
if(bom.length!==74||pnp.length!==74)throw Error('Incorrect component count');
for(let i=0;i<74;i++){
 if(bom[i][0]!==pnp[i][0]||bom[i][1]!==pnp[i][1]||bom[i][2]!==pnp[i][2])throw Error('BOM / PnP mismatch');
 if(!(pnp[i][3]>=0&&pnp[i][3]<=48&&pnp[i][4]>=0&&pnp[i][4]<=180))throw Error('Coordinate outside outline');
}
const headers={BOM:['Reference','Value','Package','Quantity','Description','Manufacturer','MPN'],PnP:['Reference','Value','Package','X(mm)','Y(mm)','Rotation','Side']};
for(const [kind,rows] of [['BOM',bom],['PnP',pnp]]){
 if(process.argv.includes('--upload-only')){
  const wb=Workbook.create();const sh=wb.worksheets.add(kind);
  const data=[headers[kind],...rows];const range=sh.getRange('A1:G75');range.values=data;
  range.format.columnWidth=22;range.format.rowHeight=28;range.format.wrapText=true;
  sh.getRange('C2:C75').setNumberFormat('@');
  sh.getRange('A1:G1').format.fill='#DBEAFE';
  if(kind==='BOM'){sh.getRange('E1:E75').format.columnWidth=65;sh.getRange('G1:G75').format.columnWidth=30;sh.getRange('A2:G75').format.rowHeight=42;sh.getRange('D2:D75').setNumberFormat('0');}
  else{sh.getRange('D2:E75').setNumberFormat('0.000');sh.getRange('F2:F75').setNumberFormat('0');}
  wb.recalculate();if(JSON.stringify(range.values)!==JSON.stringify(data))throw Error('Upload table roundtrip mismatch');
  const base=path.join(out,`DOILLABS_${kind}_8faces_16ch_UPLOAD`);
  const quote=v=>{const s=v==null?'':String(v);return /[",\r\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;};
  await fs.writeFile(base+'.csv',range.values.map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n','utf8');
  await (await SpreadsheetFile.exportXlsx(wb)).save(base+'.xlsx');
  const preview=await wb.render({sheetName:kind,range:'A1:G9',scale:1,format:'png'});
  await fs.writeFile(path.join(root,`scratch/pcba_artifact/doillabs_${kind}_UPLOAD.png`),new Uint8Array(await preview.arrayBuffer()));
  console.log(`Created ${kind} UPLOAD XLSX/CSV: first-row headers, 74 components, single worksheet`);
  continue;
 }
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,`outputs/DOILLABS_${kind}_Template.xlsx`)));
 const sh=wb.worksheets.getItem(kind);
 const guide=wb.worksheets.getItem('입력 안내');
 // Preserve template names, merged headings and seven-column header at row 4.
 sh.getRange('A5:G78').values=rows;
 sh.getRange('C5:C78').setNumberFormat('@');
 sh.getRange('A5:G78').format.fill='#FFFFFF';
 sh.getRange('A5:G78').format.font.color='#111827';
 sh.getRange('A5:G78').format.wrapText=true;
 sh.getRange('A5:G78').format.rowHeight=45;
 const widths=kind==='BOM'?[12,22,29,12,65,18,33]:[12,22,29,16,16,14,14];
 widths.forEach((w,i)=>sh.getRange(`${String.fromCharCode(65+i)}4:${String.fromCharCode(65+i)}78`).format.columnWidth=w);
 if(kind==='BOM')sh.getRange('D5:D78').setNumberFormat('0');
 else {sh.getRange('D5:E78').setNumberFormat('0.000');sh.getRange('F5:F78').setNumberFormat('0');}
 const notes=kind==='BOM'?[
 '이 파일은 한 보드 기준 74개 부품입니다. 16장 제작 수량은 주문 화면에서 설정합니다.',
 'SMT 55개 + THT 19개. Description의 THT hand solder 항목은 별도 수삽 납땜 견적을 요청하세요.',
 'U1/U2 구매 후보: Nexperia 74HCT595D,118 (SOIC-16). 원본 표시 SN74HCT595D를 대체하는 후보입니다.',
 '트랜스듀서와 헤더의 정확한 제조사/MPN은 업체 확인이 필요하여 공란으로 남겼습니다.',
 '견적용 초안. 기존 0.002 mm 간격 경고와 부품 매칭을 확인한 후 제조 승인하세요.'
 ]:[
 '전체 74개 위치: SMT 55개 Bottom, THT 트랜스듀서 16개 Top, 헤더/전해콘덴서 3개 Bottom.',
 '48x180 mm 외곽선의 좌하단 원점. X = 기존 X, Y = 기존 Gerber Y + 180 mm.',
 'Bottom X는 반전하지 않음. 회전은 KiCad 값의 0~359도 표현이며 업체 핀1 미리보기 확인 필요.',
 'THT 좌표는 패드 중심 평균을 사용. C19 몸체 중심, J1/J2 핀열 중심이며 자동 SMT 투입용이 아님.',
 'THT 19개는 수삽 위치 참고이며 별도 납땜 공정 요청 필요. 원본 THT_position_guide의 핀1 정보 참조.'
 ];
 const start=kind==='BOM'?23:16;
 for(let i=0;i<notes.length;i++){
  const r=guide.getRange(`A${start+i}:D${start+i}`);r.merge();guide.getRange(`A${start+i}`).values=[[notes[i]]];r.format.wrapText=true;r.format.rowHeight=40;
 }
 guide.getRange('B14:B18').format.wrapText=true;
 if(kind==='BOM')guide.getRange('A14:D18').format.rowHeight=100;
 wb.recalculate();
 const actual=sh.getRange('A5:G78').values;
 if(JSON.stringify(actual)!==JSON.stringify(rows))throw Error('Workbook data changed');
 console.log((await wb.inspect({kind:'region',sheetId:kind,range:'A4:G8',maxChars:1000})).ndjson);
 const exported=await SpreadsheetFile.exportXlsx(wb);
 await exported.save(path.join(out,`DOILLABS_${kind}_8faces_16ch.xlsx`));
 for(const [sheetName,range,suffix] of [[kind,'A1:G12',kind],['입력 안내',`A1:D${start+notes.length-1}`,kind+'_guide']]){
  const preview=await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(root,`scratch/pcba_artifact/doillabs_${suffix}.png`),new Uint8Array(await preview.arrayBuffer()));
 }
}
await fs.writeFile(path.join(out,'사용안내.txt'),`사이트에서 기존 BOM/PnP 업로드를 제거하고 *_UPLOAD.csv 두 파일을 BOM 및 PnP 항목에 다시 업로드하세요.\n동일 이름의 *_UPLOAD.xlsx는 단일 시트 대체 파일입니다. CSV와 XLSX를 중복 업로드하지 마세요.\nUPLOAD 파일은 첫 행에 헤더, 둘째 행부터 실제 부품 데이터를 배치하며 제목/안내/예시 행을 제거했습니다.\n한 보드 기준 부품 74개, SMT 55개/THT 19개이며 제작 수량은 16장입니다.\nPnP는 보드 좌하단 원점 규칙입니다 (X 그대로, Y=기존 Gerber Y+180 mm).\nC19/J1/J2 좌표는 실물 중심에 맞추어 패드 중심 평균을 사용했습니다.\nTHT 부품은 자동 SMT 대상이 아니므로 트랜스듀서 포함 별도 수삽 납땜 공정을 업체에 요청하세요.\n부품 후보 확인, 0.002 mm 간격 경고 검토 및 미리보기에서 핀1 방향 확인 후 주문하세요.\n`,'utf8');
console.log('Saved two DOILLABS template workbooks; matched 74 references; all coordinates inside board');
