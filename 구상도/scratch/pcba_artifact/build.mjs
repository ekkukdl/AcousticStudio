import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook} from '@oai/artifact-tool';
const tables=JSON.parse(await fs.readFile(new URL('./tables.json',import.meta.url),'utf8'));
const output=path.resolve('outputs/polygon_panels/pcba_8faces_16boards');
const wb=Workbook.create();
function col(n){let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s}
function quote(v){const s=v==null?'':String(v);return /[",\r\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s}
for(const [name,rows] of Object.entries(tables)){
 const sh=wb.worksheets.add(name);
 const range=sh.getRange(`A1:${col(rows[0].length)}${rows.length}`);
 range.values=rows;
 range.format.wrapText=true;
 range.format.columnWidth=28;
 range.format.rowHeight=45;
 sh.getRange(`A1:${col(rows[0].length)}1`).format.fill='#DBEAFE';
 const data=range.values;
 if(JSON.stringify(data)!==JSON.stringify(rows))throw new Error(`roundtrip mismatch ${name}`);
 await fs.writeFile(path.join(output,name+'.csv'),data.map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n','utf8');
}
console.log((await wb.inspect({kind:'region',sheetId:'BOM_SMT',range:'A1:G10',maxChars:1500})).ndjson);
try{
 const render=await wb.render({sheetName:'BOM_SMT',range:'A1:G10',scale:1,format:'png'});
 await fs.writeFile(path.resolve('scratch/pcba_artifact/BOM_preview.png'),new Uint8Array(await render.arrayBuffer()));
 console.log('Rendered BOM_preview.png');
}catch(err){console.log('Preview render failed: '+err.message);throw err}
console.log('Created six verified CSV tables');
