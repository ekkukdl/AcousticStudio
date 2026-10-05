from pathlib import Path
import json,hashlib,re

workspace=Path(__file__).resolve().parents[1]
dest=workspace/'AcousticStudio/구상도/creo_tunnel'
copies=[]
for n in (6,8):
    for f in (workspace/'outputs/creo_tunnel_models'/f'{n}faces'/'native').glob('*'):
        if f.suffix in {'.prt','.asm'}:copies.append((f,dest/'v1_single_panel'/f'{n}faces'/'native'/f.name))
for f in (workspace/'outputs/creo_tunnel_reused_v2/native').glob('*'):
    copies.append((f,dest/'v2_dual_panel/native'/f.name))
for original,copied in copies:
    assert copied.is_file()
    assert original.read_bytes()==copied.read_bytes(),copied

checked_links=0
for md in dest.rglob('*.md'):
    text=md.read_text(encoding='utf-8')
    assert '\ufffd' not in text,md
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if re.match(r'https?://',target):continue
        assert (md.parent/target.strip('<>')).exists(),(md,target)
        checked_links+=1

v2=dest/'v2_dual_panel'
build=json.loads((v2/'native_build_report.json').read_text())
reopen=json.loads((v2/'native_reopen_report.json').read_text())
assert build['result']['ok'] and reopen['result']['ok']
planned=set(build['result']['planned'])
assert set(p.name for p in (v2/'native').iterdir())==planned
assert planned==set(reopen['result']['uniqueModels'])
assert len(planned)==10
for result in build['result']['results']:
    for key in ('components','panelComponents','pairComponents'):
        for component in result.get(key) or []:
            assert component['model'].lower() in planned

files=[p for p in dest.rglob('*') if p.is_file() and p.name!='manifest.json']
manifest={p.relative_to(dest).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)}
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
assert max(p.stat().st_size for p in files)<100*1024*1024
print(json.dumps({'nativeFilesIdentical':len(copies),'v2UniqueNativeModels':len(planned),'localLinksChecked':checked_links,'manifestEntries':len(manifest),'maxFileBytes':max(p.stat().st_size for p in files)},indent=2))
