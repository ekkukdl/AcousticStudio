from pathlib import Path
import json,shutil,re
ROOT=Path('outputs/creo_tunnel_reused_v2').resolve()
STAGE=Path.home()/'AppData/Local/Temp/creo_reused_v2_20261005_a3'
report=json.loads((STAGE/'build_report.json').read_text())
assert report['result']['ok'] is True,report
(ROOT/'native_build_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
dest=ROOT/'native';dest.mkdir(exist_ok=True)
for name in report['result']['planned']:
    files=[f for f in (STAGE/'native').iterdir() if f.name==name or re.fullmatch(re.escape(name)+r'\.\d+',f.name)]
    newest=max(files,key=lambda f:0 if f.name==name else int(f.name.rsplit('.',1)[1]))
    shutil.copy2(newest,dest/name)
helpers=(STAGE/'build.creojs').read_text().split('function makeTunnels()')[0]
helpers=helpers.replace(json.dumps((STAGE/'native').as_posix()),json.dumps(dest.as_posix()))
helpers=helpers.replace('model:f.ModelDescr.GetFileName()','model:f.ModelDescr.GetFileName().toLowerCase()')
verify='''
function verifyTunnels(){
 let phase='start';const log=[];
 try{
  const s=pfcGetCurrentSession();s.ChangeDirectory(DIR);
  const planned=PLANNED;
  function checkComponents(m,expected){
   const actual=components(m);
   if(actual.length!==expected.length)throw new Error('Component count: '+m.FileName);
   for(let i=0;i<actual.length;i++){
    const a=actual[i],e=expected[i];
    if(a.model!==e.model || a.packaged)throw new Error('Reference/fix mismatch: '+m.FileName+' '+a.model);
    for(let r=0;r<4;r++)for(let c=0;c<4;c++)if(Math.abs(a.matrix[r][c]-e.matrix[r][c])>1e-6)throw new Error('Placement mismatch: '+m.FileName);
   }
   return actual;
  }
  for(const n of [6,8]){
   phase='retrieve '+n;
   const top=getModel(s,n===6?'tunnel_6f_v2.asm':'tunnel_8f_dual.asm');
   const pcb=getModel(s,'pcb_'+n+'f.prt'),panel=getModel(s,'panel_'+n+'f.asm');
   const d=DATA[String(n)];
   const pcbDims=dimensions(pcb),overall=dimensions(top);
   for(let i=0;i<3;i++)if(Math.abs(pcbDims[i]-d.pcb_size_mm[i])>.001||Math.abs(overall[i]-d.overall_size_mm[i])>.01)throw new Error('Size mismatch');
   const panelExpected=[{model:'pcb_'+n+'f.prt',matrix:translate(0,0,0)}].concat(d.emitter_matrices.map(m=>({model:'tx16.prt',matrix:m})));
   const pc=checkComponents(panel,panelExpected);
   const topExpected=d.face_matrices.map(m=>({model:n===6?'panel_6f.asm':'facepair_8f.asm',matrix:m}));
   topExpected.push({model:'ring_'+n+'f.prt',matrix:translate(0,0,0)},{model:'ring_'+n+'f.prt',matrix:translate(0,0,172)});
   const tc=checkComponents(top,topExpected);
   let pair=null;
   if(n===8)pair=checkComponents(getModel(s,'facepair_8f.asm'),d.pair_matrices.map(m=>({model:'panel_8f.asm',matrix:m})));
   log.push({faces:n,assembly:top.FileName,pcbDimensionsMm:pcbDims,overallDimensionsMm:overall,components:tc,panelComponents:pc,pairComponents:pair,placementVerified:true,fixConstraintsVerified:true});
  }
  const loaded=s.ListModels();const names=[];
  for(let i=0;i<sizeOf(loaded);i++){
   const m=itemOf(loaded,i);names.push(m.FileName);
   if(!/mm|millimeter/i.test(m.GetPrincipalUnits().Name))throw new Error('Unit mismatch: '+m.FileName);
  }
  if(names.length!==planned.length||planned.some(n=>names.indexOf(n)<0))throw new Error('Unique model count mismatch: '+names);
  return {ok:true,uniqueModels:names,units:'mmNs',results:log};
 }catch(e){return {ok:false,phase:phase,error:String(e),results:log};}
}
'''.replace('PLANNED',json.dumps(report['result']['planned']))
(STAGE/'verify.creojs').write_text(helpers+verify,encoding='utf-8')
html=(STAGE/'build.html').read_text().replace('src="build.creojs"','src="verify.creojs"').replace('CreoJS.makeTunnels()','CreoJS.verifyTunnels()')
(STAGE/'verify.html').write_text(html,encoding='utf-8')
working=STAGE/'verify_session';working.mkdir(exist_ok=True)
(working/'config.pro').write_text('web_browser_homepage '+(STAGE/'verify.html').as_uri()+'\n',encoding='utf-8')
print('Copied 10 native files; prepared fresh-session validation')
