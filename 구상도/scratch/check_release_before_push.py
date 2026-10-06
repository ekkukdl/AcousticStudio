"""Read-only check of staged release bytes and existing verification artifacts."""
from pathlib import Path
import subprocess,json,hashlib
r=Path(__file__).resolve().parents[2]
def git(*args,**kwargs):return subprocess.run(['git',*args],cwd=r,capture_output=True,check=True,**kwargs).stdout
entries=git('ls-files','--stage','-z').split(b'\0');staged={}
for entry in entries:
 if not entry:continue
 meta,name=entry.split(b'\t',1);mode,oid,stage=meta.split();staged[name.decode('utf-8')]=oid.decode()
base='구상도/outputs/panel_8faces_32ch_R1/'
names=[name for name in staged if name.startswith(base)]
oids=git('hash-object','--no-filters','--stdin-paths',input=('\n'.join(names)+'\n').encode('utf-8')).decode().splitlines()
assert len(oids)==len(names)
assert all(staged[name]==oid for name,oid in zip(names,oids)),'Git release bytes changed by filters'
d=r/base
for name,sha in json.loads((d/'SHA256.json').read_text(encoding='utf-8')).items():
 assert hashlib.sha256((d/name).read_bytes()).hexdigest()==sha,name
 assert base+name.replace('\\','/') in staged,name
for rev in ('creo32_R1','creo32_frame_R2'):
 for name in ('native_build_report.json','native_reopen_report.json','native_STEP_roundtrip.json'):
  assert json.loads((d/'mechanical'/rev/'validation'/name).read_text(encoding='utf-8'))['ok'],(rev,name)
change=git('diff','--cached','--name-only','-z').split(b'\0')
changed=[x.decode('utf-8') for x in change if x]
assert not any(x.endswith('.kicad_prl') or '/trail.txt.' in x or x.endswith('/creojs.js') for x in changed)
assert all((r/x).stat().st_size<100*1024**2 for x in changed)
check=subprocess.run(['git','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol','diff','--cached','--check','--','.',':(exclude)구상도/outputs/panel_8faces_32ch_R1',':(exclude)구상도/outputs/pcb_review_2026-10-06'],cwd=r,capture_output=True)
if check.returncode:
 print(check.stdout.decode('utf-8',errors='replace')[:2000]);raise SystemExit('Whitespace check failed')
print(json.dumps({'ok':True,'release_files_with_exact_staged_bytes':len(names),'staged_files':len(changed),'largest_staged_file_bytes':max((r/x).stat().st_size for x in changed),'CAD_existing_verification_reports':'PASS','release_SHA256':'PASS','authored_source_whitespace':'PASS; machine-generated output excluded'}))
