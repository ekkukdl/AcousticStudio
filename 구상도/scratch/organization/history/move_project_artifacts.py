from pathlib import Path
import os,stat,json,hashlib,shutil,time,subprocess

base=Path.cwd().resolve()
repo=(base/'AcousticStudio').resolve()
target=(repo/'구상도').resolve()
assert target.is_relative_to(repo) and target.is_dir()
def inventory(folder):
    result={}; links=[]
    def visit(current):
        for entry in os.scandir(current):
            p=Path(entry.path); rel=p.relative_to(folder).as_posix()
            info=entry.stat(follow_symlinks=False)
            if getattr(info,'st_file_attributes',0)&stat.FILE_ATTRIBUTE_REPARSE_POINT:
                links.append({'path':rel,'target':os.readlink(p) if p.is_symlink() else str(p.resolve())})
            elif entry.is_dir(follow_symlinks=False):visit(p)
            elif entry.is_file(follow_symlinks=False):
                h=hashlib.sha256()
                with p.open('rb') as f:
                    for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
                result[rel]={'bytes':info.st_size,'sha256':h.hexdigest()}
    visit(folder)
    return result,links
record={}
for name in ['outputs','scratch']:
    src=(base/name).resolve(); dst=(target/name).resolve()
    assert src.parent==base and dst.parent==target and not dst.exists()
    before,links=inventory(src)
    print(f'{name}: {len(before)} files, {sum(x["bytes"] for x in before.values())/1024/1024:.1f} MiB; {len(links)} reparse points',flush=True)
    # Same-volume directory rename preserves all files and junctions without following targets.
    try:
        src.rename(dst)
        copied=False
    except PermissionError:
        print(f'{name}: directory rename denied; copying and verifying before removing originals',flush=True)
        def skip_reparse(folder,names):
            return [n for n in names if getattr((Path(folder)/n).lstat(),'st_file_attributes',0)&stat.FILE_ATTRIBUTE_REPARSE_POINT]
        shutil.copytree(src,dst,ignore=skip_reparse)
        for link in links:
            junction=dst/link['path']; junction.parent.mkdir(parents=True,exist_ok=True)
            ps=lambda s:"'"+str(s).replace("'","''")+"'"
            subprocess.run(['powershell','-NoProfile','-Command',f'New-Item -ItemType Junction -Path {ps(junction)} -Target {ps(link["target"])} | Out-Null'],check=True)
        copied=True
    after,afterlinks=inventory(dst)
    assert before==after, f'File content changed while moving {name}'
    assert [x['path'] for x in links]==[x['path'] for x in afterlinks]
    if copied:
        assert src.resolve().parent==base and src.name in ['outputs','scratch']
        shutil.rmtree(src)
    record[name]={'file_count':len(before),'total_bytes':sum(x['bytes'] for x in before.values()),'files':before,'reparse_points':afterlinks,'sha256_comparison':'passed'}
    large=[(p,x['bytes']) for p,x in after.items() if x['bytes']>=90*1024*1024]
    print(f'{name}: move and SHA-256 comparison passed; files >=90MiB: {large}',flush=True)
(target/'artifact_move_verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print('Both original folders are now under AcousticStudio/구상도',flush=True)
