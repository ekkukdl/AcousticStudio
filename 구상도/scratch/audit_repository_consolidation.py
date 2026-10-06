"""Compare the old upstream with the consolidated working tree; read-only."""
import ast,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2]
old=root.parent/'AcousticStudio'
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args])
old_sha=git(old,'rev-parse','origin/main').decode().strip()
new_sha=git(root,'rev-parse','ver2/main').decode().strip()
paths=git(old,'ls-tree','-r','--name-only','origin/main','--','src','tests','main.py','requirements.txt','docs').decode().splitlines()
same=[];changed=[];missing=[]
for name in paths:
    source=git(old,'show','origin/main:'+name).replace(b'\r\n',b'\n')
    target=root/name
    if not target.is_file():missing.append(name);continue
    actual=target.read_bytes().replace(b'\r\n',b'\n')
    (same if actual==source else changed).append(name)
old_app=ast.parse(git(old,'show','origin/main:src/acousticstudio/app.py').decode('utf-8'))
new_app=ast.parse((root/'src/acousticstudio/app.py').read_text(encoding='utf-8'))
def methods(tree):
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AcousticStudioMain')
    return {n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
old_methods=methods(old_app);new_methods=methods(new_app)
method_missing=sorted(old_methods.keys()-new_methods.keys())
method_changes=sorted(n for n in old_methods.keys()&new_methods.keys() if old_methods[n]!=new_methods[n])
record=git(old,'show','origin/main:docs/project_status.txt').decode('utf-8').replace('\r\n','\n').rstrip()
local_record=(root/'docs/project_status.txt').read_text(encoding='utf-8').replace('\r\n','\n')
remaining=iter(line.rstrip() for line in local_record.splitlines() if line.strip())
included=all(any(candidate==line.rstrip() for candidate in remaining)
             for line in record.splitlines() if line.strip())
assert not missing and not method_missing
assert method_changes==['__init__'],method_changes
assert included
assert changed==['docs/project_status.txt','src/acousticstudio/app.py'] or set(changed)=={'docs/project_status.txt','src/acousticstudio/app.py'}
result={'old_upstream':old_sha,'ver2_upstream':new_sha,'compared_paths':len(paths),'identical_files':same,'changed_files':changed,'missing_files':missing,'missing_methods':method_missing,'changed_methods':method_changes,'additional_methods':sorted(new_methods.keys()-old_methods.keys()),'old_progress_record_preserved_in_order':included,'old_latest_commit_in_ver2_history':subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',old_sha,'HEAD']).returncode==0,'scope':'old GitHub src/tests/main.py/requirements.txt/docs compared against current ver2 working tree; ignored runtime, backups and generated hardware artifacts excluded'}
(root/'docs/repository_consolidation_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
