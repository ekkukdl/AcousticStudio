"""Export current native design; run using system Python after build + stitching."""
from pathlib import Path
import subprocess, concurrent.futures

root=Path(__file__).resolve().parents[1];d=root/'outputs/panel_8faces_32ch_R1';n=d.name
cli='C:/Program Files/KiCad/10.0/bin/kicad-cli.exe';pcb=str(d/(n+'.kicad_pcb'));sch=str(d/(n+'.kicad_sch'))
jobs=[
 ['sch','erc','--format','json','--exit-code-violations','-o',str(d/'ERC.json'),sch],
 ['sch','export','netlist','--format','kicadxml','-o',str(d/'schematic.net.xml'),sch],
 ['sch','export','svg','-o',str(d/'schematic_svg'),sch],
 ['pcb','export','gerbers','-l','F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts','-o',str(d/'gerbers_R1'),pcb],
 ['pcb','export','drill','--excellon-separate-th','--generate-map','--map-format','svg','-o',str(d/'gerbers_R1'),pcb],
 ['pcb','export','pos','--format','csv','--units','mm','--smd-only','--exclude-fp-th','-o',str(d/'PnP_SMT_KiCad.csv'),pcb],
 ['pcb','export','svg','--mode-single','--fit-page-to-board','--exclude-drawing-sheet','-l','F.Cu,F.Silkscreen,F.Fab,Edge.Cuts','-o',str(d/'previews/pcb_top.svg'),pcb],
 ['pcb','export','svg','--mode-single','--fit-page-to-board','--exclude-drawing-sheet','--mirror','-l','B.Cu,B.Silkscreen,B.Fab,Edge.Cuts','-o',str(d/'previews/pcb_bottom.svg'),pcb],
 ['pcb','export','step','--board-only','-f','-o',str(d/'mechanical/panel_board_only.step'),pcb],
]
def run(args):
    p=subprocess.run([cli]+args,capture_output=True)
    print(' '.join(args[:3]),'return',p.returncode)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8',errors='replace')+p.stdout.decode('utf-8',errors='replace'))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,jobs))
