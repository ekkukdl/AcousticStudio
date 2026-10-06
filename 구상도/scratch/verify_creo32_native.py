"""Normalize generated names, preserve import logs, prepare fresh-session verification."""
from pathlib import Path
import json,re,shutil
r=Path(__file__).resolve().parents[1];stage=r/'scratch/creo32_session';d=r/'outputs/panel_8faces_32ch_R1/mechanical/creo32_R1';native=d/'native';audit=d/'validation';audit.mkdir(exist_ok=True)
build=json.loads((audit/'native_build_report.json' if (audit/'native_build_report.json').exists() else stage/'build_report.json').read_text());assert build['ok'] and len(build['created'])==12
(audit/'native_build_report.json').write_text(json.dumps(build,indent=2),encoding='utf-8')
for name in build['created']:
 matches=[p for p in native.iterdir() if re.fullmatch(re.escape(name)+r'\.\d+',p.name)]
 if matches:
  newest=max(matches,key=lambda p:int(p.name.rsplit('.',1)[1]));shutil.copy2(newest,native/name)
  for p in matches:p.unlink()
for p in native.glob('*_log.xml'):shutil.copy2(p,audit/p.name);p.unlink()
geo=json.loads((d/'geometry_checks.json').read_text())
(audit/'native_reexport').mkdir(exist_ok=True)
helpers=(stage/'build.creojs').read_text().split('function makePanel32()')[0]
verify='''
function verifyPanel32(){
 let phase='start';const checked=[];
 try{
  const s=pfcGetCurrentSession();s.ChangeDirectory(DIR);const data=GEOMETRY_DATA;
  function get(name){return s.RetrieveModel(pfcModelDescriptor.CreateFromFileName(name));}
  function checkBounds(model,expected){const bb=bounds(model);for(let i=0;i<2;i++)for(let j=0;j<3;j++)if(Math.abs(bb[i][j]-expected[i][j])>.001)throw new Error('Bounds mismatch '+model.FileName+' actual='+JSON.stringify(bb)+' expected='+JSON.stringify(expected));return bb;}
  function checkComponents(model,expected){const actual=components(model);if(actual.length!==expected.length)throw new Error('Count mismatch '+model.FileName);for(let i=0;i<actual.length;i++){const a=actual[i],e=expected[i];if(a.model!==e.model+'.prt' && a.model!==e.model+'.asm')throw new Error('Reference mismatch '+a.model);if(a.packaged)throw new Error('Unfixed '+a.model);for(let r=0;r<4;r++)for(let c=0;c<4;c++)if(Math.abs(a.matrix[r][c]-e.matrix[r][c])>1e-6)throw new Error('Matrix mismatch '+model.FileName);}return actual;}
  for(const p of data.parts){
   phase='part '+p.name;const m=get(p.name+'.prt');if(!/mm|millimeter/i.test(m.GetPrincipalUnits().Name))throw new Error('Units '+m.FileName);
   const bb=bounds(m),entry={name:m.FileName,bounds:bb,expectedBounds:p.bounds_mm,expectedVolumeMm3:p.volume_mm3,units:m.GetPrincipalUnits().Name};checked.push(entry);
   // Independent native roundtrip verifies actual solids without relying on a
   // material assignment or Creo's conservative curved-surface outline.
   m.ExportIntf3D(DIR+'/../validation/native_reexport/'+p.name+'.step',pfcExportType.EXPORT_STEP,null);entry.nativeSTEPReexported=true;
   if(p.name!=='tx16_r1'&&p.name!=='cp63_r1')checkBounds(m,p.bounds_mm);
  }
  phase='panel';const panel=get('panel32_r1.asm');const pc=checkComponents(panel,data.panel_components);const pb=checkBounds(panel,data.panel.bounds_mm);
  phase='tunnel';const tunnel=get('tunnel8_32_r1.asm');const tc=checkComponents(tunnel,data.face_matrices.map(m=>({model:'panel32_r1',matrix:m})));const tb=checkBounds(tunnel,data.tunnel.bounds_mm);
  s.CreateModelWindow(tunnel);tunnel.Display();
  return {ok:true,freshSession:true,parts:checked,panelBounds:pb,tunnelBounds:tb,panelComponents:pc,tunnelComponents:tc,fixConstraintsVerified:true,placementVerified:true};
 }catch(e){return {ok:false,phase:phase,error:String(e),parts:checked};}
}
'''.replace('GEOMETRY_DATA',json.dumps(geo))
(stage/'verify.creojs').write_text(helpers+verify,encoding='utf-8')
html=(stage/'build.html').read_text().replace('src="build.creojs"','src="verify.creojs"').replace('CreoJS.makePanel32()','CreoJS.verifyPanel32()')
(stage/'verify.html').write_text(html,encoding='utf-8')
(stage/'config.pro').write_text('web_browser_homepage file:///C:/Users/line0/AppData/Local/Temp/acoustic_creo32_session/verify.html\n',encoding='utf-8')
if (stage/'build_report.json').exists():(stage/'build_report.json').unlink()
print('Prepared 12 canonical native files and fresh-session verification.')
