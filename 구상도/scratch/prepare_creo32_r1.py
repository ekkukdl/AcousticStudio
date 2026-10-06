"""Prepare Creo 9.0.10 Creo.JS builder; project-local files, no prior models changed."""
from pathlib import Path
import json,shutil
root=Path(__file__).resolve().parents[1];dest=root/'outputs/panel_8faces_32ch_R1/mechanical/creo32_R1'
stage=root/'scratch/creo32_session';stage.mkdir(exist_ok=True)
native=dest/'native';native.mkdir(parents=True,exist_ok=True)
creo=Path('C:/Program Files/PTC/Creo 9.0.10.0/Common Files')
for f in ('creojs.js','browser.creojs','weblink.legacy.creojs'):shutil.copy2(creo/'apps/creojs/creojsweb'/f,stage/f)
helpers='''
const DIR=NATIVE_DIR, GEO=GEOMETRY_DIR;
function sizeOf(s){return typeof s.Count==='number'?s.Count:s.length;}
function itemOf(s,i){return typeof s.Item==='function'?s.Item(i):s[i];}
function unitsMm(m){
 const systems=m.ListUnitSystems();let chosen=null;
 for(let i=0;i<sizeOf(systems);i++){const u=itemOf(systems,i);if(/mmns/i.test(u.Name)){chosen=u;break;}}
 if(!chosen)throw new Error('mmNs system missing '+m.FileName);
 if(m.GetPrincipalUnits().Name!==chosen.Name)m.SetPrincipalUnits(chosen,pfcUnitConversionOptions.Create(pfcUnitDimensionConversion.UNITCONVERT_SAME_SIZE));
}
function transform(values){const t=pfcTransform3D.Create(null),m=t.Matrix;for(let r=0;r<4;r++)for(let c=0;c<4;c++){if(typeof m.set==='function')m.set(r,c,values[r][c]);else m.Set(r,c,values[r][c]);}t.Matrix=m;return t;}
function addFixed(a,m,matrix){const f=a.AssembleComponent(m,transform(matrix)),c=pfcCreate('pfcComponentConstraints');c.Append(pfcComponentConstraint.Create(pfcComponentConstraintType.ASM_CONSTRAINT_FIX));f.SetConstraints(c,null);if(f.IsPackaged)throw new Error('Packaged '+m.FileName);return f;}
function components(m){const fs=m.ListFeaturesByType(false,pfcFeatureType.FEATTYPE_COMPONENT),out=[];if(fs)for(let i=0;i<sizeOf(fs);i++){const f=itemOf(fs,i),matrix=[];for(let r=0;r<4;r++){const row=[];for(let c=0;c<4;c++)row.push(f.Position.Matrix.Item(r,c));matrix.push(row);}out.push({model:f.ModelDescr.GetFileName().toLowerCase(),packaged:f.IsPackaged,matrix:matrix});}return out;}
function bounds(m){const o=m.GeomOutline,out=[];for(let i=0;i<2;i++){const row=[];for(let j=0;j<3;j++)row.push(itemOf(itemOf(o,i),j));out.push(row);}return out;}
'''.replace('NATIVE_DIR',json.dumps(native.as_posix())).replace('GEOMETRY_DIR',json.dumps((dest/'geometry').as_posix()))
code=helpers+'''
function makePanel32(){
 let phase='start';const created=[];
 try{
  const s=pfcGetCurrentSession();s.ChangeDirectory(TEMPLATE_DIR);
  const template=s.RetrieveModel(pfcModelDescriptor.CreateFromFileName('mmns_asm_design_abs.asm'));
  s.ChangeDirectory(DIR);const models={};const data=MODEL_DATA;
  for(const p of data.parts){phase='import '+p.name;const m=s.ImportNewModel(GEO+'/'+p.name+'.step',pfcNewModelImportType.IMPORT_NEW_STEP,pfcModelType.MDL_PART,p.name,null);unitsMm(m);m.Save();models[p.name]=m;created.push(m.FileName);}
  phase='panel assembly';const panel=template.CopyAndRetrieve('panel32_r1',null);unitsMm(panel);
  for(const p of data.panel_components)addFixed(panel,models[p.model],p.matrix);
  panel.Regenerate(null);panel.Save();created.push(panel.FileName);
  phase='tunnel assembly';const tunnel=template.CopyAndRetrieve('tunnel8_32_r1',null);unitsMm(tunnel);
  for(const m of data.face_matrices)addFixed(tunnel,panel,m);
  tunnel.Regenerate(null);tunnel.Save();created.push(tunnel.FileName);
  s.CreateModelWindow(tunnel);tunnel.Display();
  return {ok:true,phase:'complete',created:created,pcbBounds:bounds(models.pcb32_r1),panelBounds:bounds(panel),tunnelBounds:bounds(tunnel),panelComponents:components(panel),tunnelComponents:components(tunnel),units:tunnel.GetPrincipalUnits().Name};
 }catch(e){return {ok:false,phase:phase,error:String(e),created:created};}
}
'''.replace('TEMPLATE_DIR',json.dumps((creo/'templates').as_posix()))
# Geometry build fills MODEL_DATA after STEP validation.
(stage/'builder_template.creojs').write_text(code,encoding='utf-8')
html='''<!doctype html><html><head><meta charset="utf-8"><script src="creojs.js"></script><script type="text/creojs" src="browser.creojs"></script><script type="text/creojs" src="weblink.legacy.creojs"></script><script type="text/creojs" src="build.creojs"></script></head><body onload="CreoJS.$ADD_ON_LOAD(run)"><pre id="status">32CH PCB R1 native model generation</pre><script>function run(){CreoJS.makePanel32().then(function(r){document.getElementById('status').textContent=JSON.stringify(r,null,2);fetch('http://127.0.0.1:9142/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(r)});}).catch(function(e){fetch('http://127.0.0.1:9142/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ok:false,error:String(e)})});});}</script></body></html>'''
(stage/'build.html').write_text(html,encoding='utf-8')
(stage/'config.pro').write_text('web_browser_homepage '+(stage/'build.html').as_uri()+'\n',encoding='utf-8')
(stage/'receiver.py').write_text('''from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import json
dest=Path(__file__).resolve().parent/'build_report.json'
class Receiver(BaseHTTPRequestHandler):
 def do_OPTIONS(self):
  self.send_response(204);self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Methods','POST,OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.end_headers()
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'))
  if self.path!='/result' or n>2000000:self.send_error(400);return
  value=json.loads(self.rfile.read(n));dest.write_text(json.dumps(value,indent=2),encoding='utf-8')
  self.send_response(200);self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(b'OK')
 def log_message(self,*args):pass
HTTPServer(('127.0.0.1',9142),Receiver).serve_forever()
''',encoding='utf-8')
print(stage)
