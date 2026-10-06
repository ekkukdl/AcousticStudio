from pathlib import Path
import json
import shutil

source=Path('outputs/cad_generation/creo_tunnel_models').resolve()
stage=Path.home()/'AppData/Local/Temp/creo_tunnel_20261005'
stage.mkdir(exist_ok=True)
creo=Path('C:/Program Files/PTC/Creo 9.0.12.0/Common Files')
web=creo/'apps/creojs/creojsweb'
for file in ('creojs.js','browser.creojs','weblink.legacy.creojs'):
    shutil.copy2(web/file,stage/file)
for n in (6,8):
    dest=stage/f'{n}faces'
    dest.mkdir(exist_ok=True)
    for file in (source/f'{n}faces').glob('*.step'):
        shutil.copy2(file,dest/file.name)
code='''
function sizeOf(s) { return typeof s.Count === 'number' ? s.Count : s.length; }
function itemOf(s,i) { return typeof s.Item === 'function' ? s.Item(i) : s[i]; }
function convertTunnels() {
  const session = pfcGetCurrentSession();
  const output=[];
  const root=STAGE;
  session.SetConfigOption('template_solidpart', TEMPLATES+'/mmns_part_solid_abs.prt');
  session.SetConfigOption('template_designasm', TEMPLATES+'/mmns_asm_design_abs.asm');
  for (const n of [6,8]) {
    const directory=root+'/'+n+'faces';
    session.ChangeDirectory(directory);
    const before=session.ListModels();
    const names=new Set();
    for(let i=0;i<sizeOf(before);i++) names.add(itemOf(before,i).FileName);
    const model=session.ImportNewModel(directory+'/tunnel_'+n+'faces.step',pfcNewModelImportType.IMPORT_NEW_STEP,pfcModelType.MDL_ASSEMBLY,'tunnel_'+n+'faces',null);
    const loaded=session.ListModels();
    const created=[];
    for(let i=0;i<sizeOf(loaded);i++) {
      const part=itemOf(loaded,i);
      if(names.has(part.FileName)) continue;
      const units=part.GetPrincipalUnits();
      const systems=part.ListUnitSystems();
      let chosen=null;
      for(let j=0;j<sizeOf(systems);j++) {
        const system=itemOf(systems,j);
        if(/mmns/i.test(system.Name)) { chosen=system; break; }
      }
      if(chosen && units.Name!==chosen.Name) part.SetPrincipalUnits(chosen,pfcUnitConversionOptions.Create(pfcUnitDimensionConversion.UNITCONVERT_SAME_SIZE));
      const finalUnits=part.GetPrincipalUnits();
      if(!/mm|millimeter/i.test(finalUnits.Name)) throw new Error('Not mm: '+part.FileName+' '+finalUnits.Name);
      part.Save();
      created.push({name:part.FileName,units:finalUnits.Name});
    }
    model.Save();
    output.push({faces:n,assembly:model.FileName,created:created,directory:directory});
  }
  return output;
}
'''.replace('STAGE',json.dumps(stage.as_posix())).replace('TEMPLATES',json.dumps((creo/'templates').as_posix()))
(stage/'convert.creojs').write_text(code,encoding='utf-8')
html='''<!doctype html><html><head><meta charset="utf-8"><title>Creo tunnel conversion</title>
<script src="creojs.js"></script><script type="text/creojs" src="browser.creojs"></script>
<script type="text/creojs" src="convert.creojs"></script></head>
<body onload="CreoJS.$ADD_ON_LOAD(ready)"><h2>6 / 8 face tunnel: STEP to Creo 9 PRT/ASM</h2>
<p>Run this page inside Creo's embedded browser. Imports only the supplied models and saves their new parts and assemblies.</p>
<button id="run" onclick="runConversion()" disabled>Generate PRT / ASM</button><pre id="status">Waiting for Creo.JS...</pre>
<script>
var running=false;
function report(value) {
 document.getElementById('status').textContent=JSON.stringify(value,null,2);
 fetch('http://127.0.0.1:9129/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)}).catch(function(){});
}
function runConversion() {
 if(running) return; running=true;
 document.getElementById('run').disabled=true;
 document.getElementById('status').textContent='Importing and saving models...';
 CreoJS.convertTunnels().then(function(result){report({status:'success',results:result});}).catch(function(error){report({status:'error',error:String(error),details:error});running=false;document.getElementById('run').disabled=false;});
}
function ready() {document.getElementById('run').disabled=false;document.getElementById('status').textContent='Creo.JS ready';runConversion();}
</script></body></html>'''
(stage/'convert_models.html').write_text(html,encoding='utf-8')
(stage/'config.pro').write_text('web_browser_homepage '+(stage/'convert_models.html').as_uri()+'\n',encoding='utf-8')
print(stage)
