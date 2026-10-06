from pathlib import Path
r=Path(__file__).resolve().parents[1]
script=(r/'scratch/render_creo32_vtk.py').read_text(encoding='utf-8')
script=script.replace('mechanical/creo32_R1','mechanical/creo32_frame_R2').replace("'pcb32_r1':(.07,.4,.25)","'pcb32_r2':(.04,.35,.16),'ring8_32_r2':(.3,.32,.36)").replace("'tx16_r1':(.68,.72,.76)","'tx16_r1':(.7,.71,.74)")
script=script.replace('def items(renderer,face=None,upright=False):','def items(renderer,face=None,upright=False,selected=None):').replace("for p in data['panel_components']:","for p in (selected if selected is not None else data['panel_components']):")
script=script.replace("camera=renderer.GetActiveCamera();camera.SetFocalPoint(0,0,0)","items(renderer,selected=data['top_components'][-2:])\ncamera=renderer.GetActiveCamera();camera.SetFocalPoint(0,0,0)")
script=script.replace('Exact PCB outline / hole positions; approximate component bodies. External frame omitted.','Green PCB / grey upper and lower rings | 265 x 265 x 224 mm')
exec(compile(script,str(__file__),'exec'))
