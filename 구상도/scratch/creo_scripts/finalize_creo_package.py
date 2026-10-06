from pathlib import Path
import json, zipfile, hashlib
root=Path('outputs/cad_generation/creo_tunnel_models').resolve()
stage=Path.home()/'AppData/Local/Temp/creo_tunnel_20261005'
report=json.loads((stage/'native_status.json').read_text())
assert report['status']=='success' and report['results']['ok'] is True,report
assert len(report['results']['results'])==2
(root/'native_reopen_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for n in (6,8):
    p=root/f'{n}faces'/'geometry_checks.json'
    data=json.loads(p.read_text())
    data['native_creo_status']='Saved and reopened in fresh Creo Parametric 9.0.12.0 session; native dependencies loaded and PCB dimensions verified'
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
files=[]
for f in root.rglob('*'):
    if f.is_file() and f.suffix.lower() in {'.prt','.asm','.step','.png','.json','.md','.py'} and f.name!='package_manifest.json':files.append(f)
manifest={str(f.relative_to(root)):dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(files)}
(root/'package_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
files.append(root/'package_manifest.json')
archive=root/'creo9_tunnel_6faces_8faces.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for f in files:z.write(f,f.relative_to(root).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert '6faces/native/tunnel_6faces.asm' in z.namelist()
    assert '8faces/native/tunnel_8faces.asm' in z.namelist()
print(json.dumps({'archive':str(archive),'files':len(files),'bytes':archive.stat().st_size,'verification':report},ensure_ascii=False))
