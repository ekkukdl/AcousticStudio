from pathlib import Path
import json,hashlib,zipfile,shutil
ROOT=Path('outputs/cad_generation/creo_tunnel_reused_v2').resolve()
STAGE=Path.home()/'AppData/Local/Temp/creo_reused_v2_20261005_a3'
report=json.loads((STAGE/'build_report.json').read_text())
assert report['result']['ok'] is True,report
assert len(report['result']['uniqueModels'])==10,report
assert report['result']['units']=='mmNs'
assert len(report['result']['results'])==2
assert all(r['placementVerified'] and r['fixConstraintsVerified'] for r in report['result']['results'])
(ROOT/'native_reopen_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
automation=ROOT/'automation';automation.mkdir(exist_ok=True)
for name in ('prepare_creo_reused_v2.py','verify_creo_reused_v2.py'):
    shutil.copy2(Path('scratch/creo_scripts')/name,automation/name)
files=[p for p in ROOT.rglob('*') if p.is_file() and p.suffix.lower() in {'.asm','.prt','.step','.png','.json','.md','.py'} and '__pycache__' not in p.parts and p.name!='manifest.json']
manifest={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)}
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');files.append(ROOT/'manifest.json')
archive=ROOT/'creo9_shared_6f_dualpcb_8f_v2.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len([n for n in z.namelist() if n.startswith('native/')])==10
print(json.dumps({'ok':True,'nativeFiles':10,'archiveBytes':archive.stat().st_size,'files':len(files),'assemblies':[r['assembly'] for r in report['result']['results']]},indent=2))
