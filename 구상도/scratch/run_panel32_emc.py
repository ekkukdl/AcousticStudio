from pathlib import Path
import os
import runpy
import sys

base=Path(__file__).resolve().parent
sys.path.insert(0,str(Path(os.environ['CODEX_HOME'])/'skills/kicad/scripts'))
sys.path.insert(0,str(base/'pcb32_support/emc/scripts'))
analysis=base.parent/'outputs/panel_8faces_32ch_R1/analysis'
sys.argv=['analyze_emc.py','--schematic',str(analysis/'schematic.json'),'--pcb',str(analysis/'pcb.json'),'--output',str(analysis/'emc.json')]
runpy.run_path(str(base/'pcb32_support/emc/scripts/analyze_emc.py'),run_name='__main__')
