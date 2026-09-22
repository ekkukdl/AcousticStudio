import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix broken prints using simpler substring replace
text = text.replace('print("??????? 1?? ?? ?????????.")', 'print("에러: 타겟(Control Point)이 1개 이상 존재해야 위상을 계산할 수 있습니다.")')
text = text.replace('print("? ?????????!")', 'print("위상 연산 및 시각화 완료!")')

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Fixed prints!")
