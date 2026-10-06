from pathlib import Path
r=Path(__file__).resolve().parents[1]
code=(r/'scratch/verify_creo32_native.py').read_text(encoding='utf-8')
code=code.replace("scratch/creo32_session","scratch/creo32_frame_session").replace('mechanical/creo32_R1','mechanical/creo32_frame_R2').replace("==12","==13").replace('panel32_r1','panel32_r2').replace('tunnel8_32_r1','tunnel8_32_r2').replace("data.face_matrices.map(m=>({model:'panel32_r2',matrix:m}))","data.top_components")
code=code.replace('acoustic_creo32_session/verify.html','acoustic_creo32_frame_session/verify.html').replace("verify.html\\n'","verify.html\\nstep_export_format ap214_is\\n'")
code=code.replace('12 canonical','13 canonical')
exec(compile(code,str(__file__),'exec'))
