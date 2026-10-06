from pathlib import Path
import csv,json,zipfile,shutil
root=Path.cwd(); out=root/'outputs/pcb/polygon_panels/pcba_8faces_16boards'
tables={p.stem:list(csv.DictReader(p.open(encoding='utf-8',newline=''))) for p in out.glob('*.csv')}
refs=lambda rows:{r for row in rows for r in row['Designator'].split(',')}
assert refs(tables['BOM_SMT'])==refs(tables['PnP_SMT'])
assert refs(tables['BOM_THT'])==refs(tables['THT_position_guide'])
assert not refs(tables['BOM_SMT'])&refs(tables['BOM_THT'])
assert refs(tables['BOM_ALL'])==refs(tables['BOM_SMT'])|refs(tables['BOM_THT'])
assert sum(int(x['Quantity']) for x in tables['BOM_SMT'])==55
assert sum(int(x['Quantity']) for x in tables['BOM_THT'])==19
assert len(refs(tables['BOM_ALL']))==74
assert sum(int(x['Total_quantity']) for x in tables['Parts_16_boards'])==1184
assert all(x['Layer']=='Bottom' for x in tables['PnP_SMT'])
assert len(tables['PnP_SMT'])==55
shutil.copy2(root/'outputs/pcb/polygon_panels/gerber_quotes/panel_8faces_16ch_Gerber_P0_quote.zip',out)
bundle=out.parent/'PCBA_8faces_16boards_quote_package.zip'
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(out.iterdir()):
  if p.is_file():z.write(p,p.name)
with zipfile.ZipFile(bundle) as z:
 assert z.testzip() is None
 assert len(z.namelist())==9
 for p in out.iterdir():
  if p.is_file():assert z.read(p.name)==p.read_bytes()
print(json.dumps({'validation':'passed','CSV_files':6,'SMT_refs':55,'THT_refs':19,'total_parts_per_board':74,'16_board_total':1184,'package':str(bundle),'bytes':bundle.stat().st_size},ensure_ascii=False))
