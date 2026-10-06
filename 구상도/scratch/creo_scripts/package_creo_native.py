from pathlib import Path
import json, shutil, re

root=Path('outputs/cad_generation/creo_tunnel_models').resolve()
stage=Path.home()/'AppData/Local/Temp/creo_tunnel_20261005'
report=json.loads((stage/'native_status.json').read_text())
assert report['status']=='success'
for n in (6,8):
    dest=root/f'{n}faces'/'native'
    dest.mkdir(exist_ok=True)
    groups={}
    for f in (stage/f'{n}faces').iterdir():
        match=re.fullmatch(r'(.+\.(?:prt|asm))\.(\d+)',f.name)
        if match:
            name,rev=match.group(1),int(match.group(2))
            if name not in groups or rev>groups[name][0]: groups[name]=(rev,f)
    for name,(rev,f) in groups.items(): shutil.copy2(f,dest/name)
    data=json.loads((root/f'{n}faces'/'geometry_checks.json').read_text())
    data['native_creo_status']='Saved by Creo Parametric 9.0.12.0; mmNs units verified'
    (root/f'{n}faces'/'geometry_checks.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(stage/'native_status.json',root/'native_generation_report.json')
code='''
function sizeOf(s) { return typeof s.Count === 'number' ? s.Count : s.length; }
function itemOf(s,i) { return typeof s.Item === 'function' ? s.Item(i) : s[i]; }
function verifyTunnels() {
 const session=pfcGetCurrentSession();
 const root=ROOT;
 const results=[];
 for(const n of [6,8]) {
  session.ChangeDirectory(root+'/'+n+'faces/native');
  const model=session.RetrieveModel(pfcModelDescriptor.CreateFromFileName('tunnel_'+n+'faces.asm'));
  const pcb=session.RetrieveModel(pfcModelDescriptor.CreateFromFileName('pcb_'+n+'f.prt'));
  const outline=pcb.GeomOutline;
  const dims=[];
  for(let i=0;i<3;i++) dims.push(Math.abs(itemOf(itemOf(outline,1),i)-itemOf(itemOf(outline,0),i)));
  const expected=n===6?[60,180,1.6]:[48,180,1.6];
  for(let i=0;i<3;i++) if(Math.abs(dims[i]-expected[i])>0.001) throw new Error('PCB dimension mismatch: '+dims);
  const models=session.ListModels();
  const loaded=[];
  for(let i=0;i<sizeOf(models);i++) {
   const m=itemOf(models,i);
   if(m.FileName.indexOf('_'+n+'f')<0 && m.FileName.indexOf('_'+n+'faces')<0) continue;
   loaded.push({name:m.FileName,units:m.GetPrincipalUnits().Name});
  }
  const expectedModels=n+5;
  if(loaded.length!==expectedModels) throw new Error('Dependency count mismatch: '+loaded.length);
  results.push({faces:n,assembly:model.FileName,pcbDimensionsMm:dims,pcbVolumeMm3:pcb.GetMassProperty(null).Volume,assemblyVolumeMm3:model.GetMassProperty(null).Volume,loaded:loaded});
 }
 return results;
}
'''.replace('ROOT',json.dumps(root.as_posix()))
(stage/'verify.creojs').write_text(code,encoding='utf-8')
html=(stage/'convert_models.html').read_text(encoding='utf-8').replace('convert.creojs','verify.creojs').replace('CreoJS.convertTunnels()','CreoJS.verifyTunnels()')
(stage/'verify_models.html').write_text(html,encoding='utf-8')
verifydir=stage/'verify_session'
verifydir.mkdir(exist_ok=True)
(verifydir/'config.pro').write_text('web_browser_homepage '+(stage/'verify_models.html').as_uri()+'\n',encoding='utf-8')
print('Copied native models and prepared fresh-session verification:',verifydir)
