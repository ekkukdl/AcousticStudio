# -*- coding: utf-8 -*-
import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

replacements = [
    (r'1\. Selected Object Transform.*?\)', '1. Selected Object Transform (선택된 객체 이동/회전)'),
    (r'\".*? \(mm\):\"', '"위치 (mm):"'),
    (r'\".*? \(deg\):\"', '"회전 (deg):"'),
    (r'\".*? \(X,Y,Z\):\"', '"생성 위치 (X,Y,Z):"'),
    (r'\".*? \(Rx,Ry,Rz\):\"', '"생성 각도 (Rx,Ry,Rz):"'),
    (r'\"NxM Matrix.*?\"', '"NxM Matrix (평면형)"'),
    (r'addItems\(\[\".*?\(10mm\)\".*?\]\)', 'addItems(["소형 초음파센서 (10mm)", "소형 초음파센서 (16mm)", "랑주뱅 진동자 (Langevin)"])'),
    (r'addRow\(\".*?\(mm\):\"', 'addRow("위치 (mm):"'),
    (r'addRow\(\".*?\(deg\):\"', 'addRow("회전 (deg):"'),
    (r'addRow\(\".*?\(X,Y,Z\):\"', 'addRow("생성 위치 (X,Y,Z):"'),
    (r'addRow\(\".*?\(Rx,Ry,Rz\):\"', 'addRow("생성 각도 (Rx,Ry,Rz):"'),
]

# Manual replacements for specific lines
text = re.sub(r'QGroupBox\(\"1\. Selected Object Transform.*?\"\)', 'QGroupBox("1. Selected Object Transform (선택된 객체 이동/회전)")', text)
text = re.sub(r'addRow\(\".*?:\", self\.transducer_type_cb\)', 'addRow("센서 형태:", self.transducer_type_cb)', text)
text = re.sub(r'addRow\(\".*?:\", self\.array_type_cb\)', 'addRow("배열 방식:", self.array_type_cb)', text)
text = re.sub(r'addRow\(\".*?:\", self\.trap_type_cb\)', 'addRow("알고리즘:", self.trap_type_cb)', text)
text = re.sub(r'setText\(\".*?3D.*?\"\)', 'setText("배열 3D 뷰어에 생성하기")', text)
text = re.sub(r'QCheckBox\(\"Point.*?\"\)', 'QCheckBox("Point 위치 변동 시 위상/음압 실시간 자동 계산")', text)
text = re.sub(r'setText\(\"Calculate Phase.*?\"\)', 'setText("Calculate Phase (위상 계산 및 시각화)")', text)
text = re.sub(r'setText\(\"XZ.*?\"\)', 'setText("XZ (측면)")', text)
text = re.sub(r'setText\(\"YZ.*?\"\)', 'setText("YZ (정면)")', text)
text = re.sub(r'setText\(\"XY.*?\"\)', 'setText("XY (바닥)")', text)
text = re.sub(r'self\.show_field_btn\.setText\(\".*?\(ON/OFF\)\"\)', 'self.show_field_btn.setText("음압 단면 보기 (ON/OFF)")', text)
text = re.sub(r'self\.show_field_btn\.setText\(\"(?!음압).*?\"\)', 'self.show_field_btn.setText("음압 단면 숨기기")', text)
text = re.sub(r'Warning\", \".*?1.*?\"', 'Warning", "에러: 타겟(Control Point)이 1개 이상 존재해야 위상을 계산할 수 있습니다."', text)
text = re.sub(r'Information\", \".*?!\"', 'Information", "위상 연산 및 시각화 완료!"', text)

# Array Types combo box
text = re.sub(r'addItems\(\[\s*\"NxM Matrix.*?\",\s*\".*?4.*?\",\s*\".*?2.*?\",\s*\".*?Hemisphere.*?\"\s*\]\)', 
              'addItems([\n            "NxM Matrix (평면형)", \n            "터널형 (상하좌우 4면)", \n            "대향형 (상하 2면)", \n            "반구형 (Hemisphere)"\n        ])', text, flags=re.DOTALL)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Regex replace Done!")
