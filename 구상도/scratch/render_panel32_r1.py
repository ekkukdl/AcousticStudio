from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'pcb32_tools'))
import resvg_py
from PIL import Image

dest=Path(__file__).resolve().parents[1]/'outputs/panel_8faces_32ch_R1'
for src in (dest/'schematic_svg').glob('*.svg'):
    out=dest/'schematic_preview.png'
    out.write_bytes(resvg_py.svg_to_bytes(svg_string=src.read_text(encoding='utf-8'),width=4200,dpi=96,background='#ffffff'))
    im=Image.open(out)
    im.crop((int(im.width*0.015),int(im.height*0.07),int(im.width*0.50),int(im.height*0.35))).save(dest/'schematic_block_zoom.png')
    scale=im.width/620
    im.crop(tuple(int(v*scale) for v in (8,274,288,400))).save(dest/'schematic_control_zoom.png')
for src in (dest/'previews').glob('*.svg'):
    (dest/(src.stem+'.png')).write_bytes(resvg_py.svg_to_bytes(svg_string=src.read_text(encoding='utf-8'),height=2200,dpi=96,background='#ffffff'))
print('Rendered available KiCad SVG exports.')
