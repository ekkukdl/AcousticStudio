from pathlib import Path
import hashlib,json,subprocess
repo=Path(__file__).resolve().parents[1]/'AcousticStudio'
root=repo/'구상도/creo_tunnel'
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
for name,data in manifest.items():
    path=(root/name).relative_to(repo).as_posix()
    blob=subprocess.run(['git','show',':'+path],cwd=repo,capture_output=True,check=True).stdout
    assert len(blob)==data['bytes'] and hashlib.sha256(blob).hexdigest()==data['sha256'],name
changed=subprocess.run(['git','diff','--cached','--name-only','-z'],cwd=repo,capture_output=True,check=True).stdout.decode('utf-8').split('\0')
assert all(not p or p=='docs/project_status.txt' or p.startswith('구상도/creo_tunnel/') for p in changed)
check=subprocess.run(['git','diff','--cached','--check'],cwd=repo,capture_output=True)
assert check.returncode==0,check.stdout.decode('utf-8',errors='replace')[:1500]
print(json.dumps({'gitIndexHashesVerified':len(manifest),'stagedScopeVerified':True,'diffCheck':'passed'}))
