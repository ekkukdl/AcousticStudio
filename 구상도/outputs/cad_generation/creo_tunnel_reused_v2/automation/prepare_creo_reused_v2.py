from pathlib import Path
import json,shutil
ROOT=Path('outputs/cad_generation/creo_tunnel_reused_v2').resolve()
OLD=ROOT.parent/'creo_tunnel_models'
STAGE=Path.home()/'AppData/Local/Temp/creo_reused_v2_20261005_a3'
NATIVE=STAGE/'native';NATIVE.mkdir(parents=True,exist_ok=True)
CREO=Path('C:/Program Files/PTC/Creo 9.0.12.0/Common Files')
for f in ('creojs.js','browser.creojs','weblink.legacy.creojs'):shutil.copy2(CREO/'apps/creojs/creojsweb'/f,STAGE/f)
for folder,name in [('6faces','pcb_6f.prt'),('8faces','pcb_8f.prt'),('8faces','tx_8f_t1.prt'),('6faces','ring_6f_lower.prt')]:shutil.copy2(OLD/folder/'native'/name,NATIVE/name)
shutil.copy2(ROOT/'geometry/ring_8f.step',NATIVE/'ring_8f.step')
data={str(n):json.loads((ROOT/'geometry'/f'checks_{n}f.json').read_text()) for n in (6,8)}
code='''
const DATA=MODEL_DATA;
const DIR=NATIVE_DIR;
function sizeOf(s){return typeof s.Count==='number'?s.Count:s.length;}
function itemOf(s,i){return typeof s.Item==='function'?s.Item(i):s[i];}
function getModel(s,name){return s.RetrieveModel(pfcModelDescriptor.CreateFromFileName(name));}
function unitsMm(m){
 const systems=m.ListUnitSystems();let chosen=null;
 for(let i=0;i<sizeOf(systems);i++){const u=itemOf(systems,i);if(/mmns/i.test(u.Name)){chosen=u;break;}}
 if(!chosen)throw new Error('mmNs system missing: '+m.FileName);
 if(m.GetPrincipalUnits().Name!==chosen.Name)m.SetPrincipalUnits(chosen,pfcUnitConversionOptions.Create(pfcUnitDimensionConversion.UNITCONVERT_SAME_SIZE));
}
function transform(values){
 const tr=pfcTransform3D.Create(null); const m=tr.Matrix;
 for(let i=0;i<4;i++)for(let j=0;j<4;j++){if(typeof m.set==='function')m.set(i,j,values[i][j]);else m.Set(i,j,values[i][j]);}
 tr.Matrix=m; return tr;
}
function translate(x,y,z){return [[1,0,0,0],[0,1,0,0],[0,0,1,0],[x,y,z,1]];}
function addFixed(assembly,model,values){
 const feature=assembly.AssembleComponent(model,transform(values));
 const constraints=pfcCreate('pfcComponentConstraints');
 constraints.Append(pfcComponentConstraint.Create(pfcComponentConstraintType.ASM_CONSTRAINT_FIX));
 feature.SetConstraints(constraints,null);
 if(feature.IsPackaged)throw new Error('Unconstrained component: '+model.FileName);
 return feature;
}
function components(m){
 const features=m.ListFeaturesByType(false,pfcFeatureType.FEATTYPE_COMPONENT);
 const result=[];
 if(features)for(let i=0;i<sizeOf(features);i++){
  const f=itemOf(features,i);const matrix=f.Position.Matrix;const values=[];
  for(let r=0;r<4;r++){const row=[];for(let c=0;c<4;c++)row.push(matrix.Item(r,c));values.push(row);}
  result.push({model:f.ModelDescr.GetFileName(),packaged:f.IsPackaged,matrix:values});
 }
 return result;
}
function dimensions(m){const o=m.GeomOutline;const result=[];for(let i=0;i<3;i++)result.push(Math.abs(itemOf(itemOf(o,1),i)-itemOf(itemOf(o,0),i)));return result;}
function makeTunnels(){
 let phase='start';const log=[];
 try{
  const s=pfcGetCurrentSession();
  s.ChangeDirectory(TEMPLATE_DIR);
  const template=getModel(s,'mmns_asm_design_abs.asm');
  s.ChangeDirectory(DIR);
  const pcb6=getModel(s,'pcb_6f.prt'),pcb8=getModel(s,'pcb_8f.prt');
  phase='shared parts';
  const tx=getModel(s,'tx_8f_t1.prt').CopyAndRetrieve('tx16',null);unitsMm(tx);tx.Save();
  const ring6=getModel(s,'ring_6f_lower.prt').CopyAndRetrieve('ring_6f',null);unitsMm(ring6);ring6.Save();
  const ring8=s.ImportNewModel(DIR+'/ring_8f.step',pfcNewModelImportType.IMPORT_NEW_STEP,pfcModelType.MDL_PART,'ring_8f',null);unitsMm(ring8);ring8.Save();
  const planned=['pcb_6f.prt','pcb_8f.prt','tx16.prt','ring_6f.prt','ring_8f.prt'];
  for(const n of [6,8]){
   phase='panel '+n;
   const d=DATA[String(n)],pcb=n===6?pcb6:pcb8,ring=n===6?ring6:ring8;
   const panel=template.CopyAndRetrieve('panel_'+n+'f',null);unitsMm(panel);
   addFixed(panel,pcb,translate(0,0,0));
   for(const matrix of d.emitter_matrices)addFixed(panel,tx,matrix);
   panel.Regenerate(null);panel.Save();planned.push(panel.FileName);
   let unit=panel;
   if(n===8){
    phase='facepair';unit=template.CopyAndRetrieve('facepair_8f',null);unitsMm(unit);
    for(const matrix of d.pair_matrices)addFixed(unit,panel,matrix);
    unit.Regenerate(null);unit.Save();planned.push(unit.FileName);
   }
   phase='tunnel '+n;
   const top=template.CopyAndRetrieve(n===6?'tunnel_6f_v2':'tunnel_8f_dual',null);unitsMm(top);
   for(const matrix of d.face_matrices)addFixed(top,unit,matrix);
   addFixed(top,ring,translate(0,0,0));addFixed(top,ring,translate(0,0,172));
   top.Regenerate(null);top.Save();planned.push(top.FileName);
   const actual=dimensions(top);
   for(let i=0;i<3;i++)if(Math.abs(actual[i]-d.overall_size_mm[i])>.01)throw new Error('Native assembly size mismatch '+actual);
   log.push({faces:n,assembly:top.FileName,units:top.GetPrincipalUnits().Name,dimensionsMm:actual,components:components(top),panelComponents:components(panel),pairComponents:n===8?components(unit):null});
  }
  return {ok:true,planned:planned,results:log};
 }catch(e){return {ok:false,phase:phase,error:String(e),results:log};}
}
'''.replace('MODEL_DATA',json.dumps(data)).replace('NATIVE_DIR',json.dumps(NATIVE.as_posix())).replace('TEMPLATE_DIR',json.dumps((CREO/'templates').as_posix()))
(STAGE/'build.creojs').write_text(code,encoding='utf-8')
html='''<!doctype html><html><head><meta charset="utf-8"><script src="creojs.js"></script>
<script type="text/creojs" src="browser.creojs"></script><script type="text/creojs" src="weblink.legacy.creojs"></script><script type="text/creojs" src="build.creojs"></script></head>
<body onload="CreoJS.$ADD_ON_LOAD(run)"><pre id="status">Building shared native assemblies...</pre><script>
function run(){CreoJS.makeTunnels().then(function(result){const report={status:'completed',result:result};document.getElementById('status').textContent=JSON.stringify(report,null,2);fetch('http://127.0.0.1:9132/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(report)});}).catch(function(e){fetch('http://127.0.0.1:9132/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'error',error:String(e)})});});}
</script></body></html>'''
(STAGE/'build.html').write_text(html,encoding='utf-8')
(STAGE/'config.pro').write_text('web_browser_homepage '+(STAGE/'build.html').as_uri()+'\nregen_failure_handling resolve_mode\n',encoding='utf-8')
receiver=Path('scratch/creo_scripts/creo_conversion_receiver.py').read_text().replace('creo_tunnel_20261005/native_status.json','creo_reused_v2_20261005_a3/build_report.json').replace('9129','9132')
(STAGE/'receiver.py').write_text(receiver,encoding='utf-8')
print(STAGE)


