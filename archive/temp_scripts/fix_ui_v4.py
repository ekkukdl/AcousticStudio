import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r't_layout\.addRow\(\".*?\(mm\):\",\s*pos_lyt\)', 't_layout.addRow(\"위치 (mm):\", pos_lyt)', text)
text = re.sub(r't_layout\.addRow\(\".*?\(deg\):\",\s*rot_lyt\)', 't_layout.addRow(\"회전 (deg):\", rot_lyt)', text)
text = re.sub(r'array_layout\.addRow\(\".*?\(X,Y,Z\):\",\s*gen_pos_lyt\)', 'array_layout.addRow(\"생성 위치 (X,Y,Z):\", gen_pos_lyt)', text)
text = re.sub(r'array_layout\.addRow\(\".*?\(Rx,Ry,Rz\):\",\s*gen_rot_lyt\)', 'array_layout.addRow(\"생성 각도 (Rx,Ry,Rz):\", gen_rot_lyt)', text)
text = re.sub(r'self\.transducer_type_cb\.addItems\(\[\".*?\"\]\)', 'self.transducer_type_cb.addItems([\"소형 초음파센서 (10mm)\", \"소형 초음파센서 (16mm)\", \"랑주뱅 진동자 (Langevin)\"])', text)
text = re.sub(r'QGroupBox\(\"1\. Selected.*\"\)', 'QGroupBox("1. Selected Object Transform (선택된 객체 이동/회전)")', text)
text = re.sub(r'QGroupBox\(\"3\. Control Points.*\"\)', 'QGroupBox("3. Control Points (타겟 설정)")', text)
text = re.sub(r'QGroupBox\(\"4\. Phase.*?\"\)', 'QGroupBox("4. Phase Simulation (위상 연산)")', text)
text = re.sub(r'QGroupBox\(\"5\. Acoustic.*?\"\)', 'QGroupBox("5. Acoustic Field Visualization (음압 단면 시각화)")', text)
text = re.sub(r'QGroupBox\(\"2\. Transducer.*?\"\)', 'QGroupBox("2. Transducer Array Setup (초음파 배열 설정)")', text)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
