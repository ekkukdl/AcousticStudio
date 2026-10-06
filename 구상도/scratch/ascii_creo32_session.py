from pathlib import Path
import json
r=Path(__file__).resolve().parents[1];stage=r/'scratch/creo32_session';d=r/'outputs/panel_8faces_32ch_R1/mechanical/creo32_R1'
alias='C:/Users/line0/AppData/Local/Temp/acoustic_creo32_models'
text=(stage/'build.creojs').read_text(encoding='utf-8').replace(json.dumps((d/'native').as_posix()),json.dumps(alias+'/native')).replace(json.dumps((d/'geometry').as_posix()),json.dumps(alias+'/geometry'))
(stage/'build.creojs').write_text(text,encoding='utf-8')
(stage/'config.pro').write_text('web_browser_homepage file:///C:/Users/line0/AppData/Local/Temp/acoustic_creo32_session/build.html\n',encoding='utf-8')
