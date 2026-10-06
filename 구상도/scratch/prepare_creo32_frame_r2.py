from pathlib import Path
import json,shutil
r=Path(__file__).resolve().parents[1];d=r/'outputs/panel_8faces_32ch_R1/mechanical/creo32_frame_R2';stage=r/'scratch/creo32_frame_session';stage.mkdir(exist_ok=True);(d/'native').mkdir(exist_ok=True);(d/'validation/native_reexport').mkdir(parents=True,exist_ok=True)
old=r/'scratch/creo32_session'
for f in ('creojs.js','browser.creojs','weblink.legacy.creojs'):shutil.copy2(old/f,stage/f)
code=(old/'builder_template.creojs').read_text(encoding='utf-8').replace('creo32_R1','creo32_frame_R2').replace('pcb32_r1','pcb32_r2').replace('panel32_r1','panel32_r2').replace('tunnel8_32_r1','tunnel8_32_r2')
actual=d.as_posix();alias='C:/Users/line0/AppData/Local/Temp/acoustic_creo32_frame_models'
code=code.replace(actual,alias).replace('for(const m of data.face_matrices)addFixed(tunnel,panel,m);','for(const p of data.top_components)addFixed(tunnel,p.model===\'panel32_r2\'?panel:models[p.model],p.matrix);')
(stage/'builder_template.creojs').write_text(code,encoding='utf-8')
data=json.loads((d/'geometry_checks.json').read_text(encoding='utf-8'))
(stage/'build.creojs').write_text(code.replace('MODEL_DATA',json.dumps(data)),encoding='utf-8')
html=(old/'build.html').read_text(encoding='utf-8').replace('9142','9143').replace('32CH PCB R1','32CH PCB and frame R2')
(stage/'build.html').write_text(html,encoding='utf-8')
(stage/'receiver.py').write_text((old/'receiver.py').read_text(encoding='utf-8').replace('9142','9143'),encoding='utf-8')
(stage/'config.pro').write_text('web_browser_homepage file:///C:/Users/line0/AppData/Local/Temp/acoustic_creo32_frame_session/build.html\nstep_export_format ap214_is\n',encoding='utf-8')
print('Prepared R2 native builder.')
