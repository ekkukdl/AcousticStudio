from pathlib import Path
import zipfile,json

root=Path(__file__).resolve().parents[2]/'outputs/pcb/polygon_panels'
dest=root/'gerber_quotes';dest.mkdir(exist_ok=True)
needed={'.gtl','.gbl','.gts','.gbs','.gto','.gbo','.gm1','.drl'}
reports=[]
for n in (6,8):
    source=root/f'panel_{n}faces_16ch/gerbers_P0'
    files=sorted(p for p in source.iterdir() if p.is_file())
    assert needed.issubset({p.suffix for p in files})
    archive=dest/f'panel_{n}faces_16ch_Gerber_P0_quote.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for p in files:assert z.read(p.name)==p.read_bytes()
    reports.append({'faces':n,'zip':archive.name,'files':len(files),'bytes':archive.stat().st_size})
print(json.dumps(reports,indent=2))
