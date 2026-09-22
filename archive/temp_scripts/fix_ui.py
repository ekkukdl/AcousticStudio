# -*- coding: utf-8 -*-
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    '"1. Selected Object Transform (??? )"': '"1. Selected Object Transform (선택된 객체 이동/회전)"',
    '"? (mm):"': '"위치 (mm):"',
    '"? (deg):"': '"회전 (deg):"',
    '"? (X,Y,Z):"': '"위치 (X,Y,Z):"',
    '"? (Rx,Ry,Rz):"': '"회전 (Rx,Ry,Rz):"',
    '"? ???"': '"센서 형태:"',
    '"?:"': '"알고리즘:"',
    '"? ? ???"': '"음압 단면 숨기기"',
    '"? ? ????(ON/OFF)"': '"음압 단면 보기 (ON/OFF)"',
    '"NxM Matrix (?)"': '"NxM Matrix (평면형)"',
    '"???(? 4?"': '"터널형 (상하좌우 4면)"',
    '"? ?? (???2?"': '"대향형 (상하 2면)"',
    '"??(Hemisphere)"': '"반구형 (Hemisphere)"',
    '"? ?????(10mm)"': '"소형 초음파센서 (10mm)"',
    '"? ?????(16mm)"': '"소형 초음파센서 (16mm)"',
    '"????(Langevin)"': '"랑주뱅 진동자 (Langevin)"'
}

for old, new in replacements.items():
    text = text.replace(old, new)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
