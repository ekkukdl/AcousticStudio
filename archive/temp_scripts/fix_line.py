with open(r'src/acousticstudio/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
lines[1864] = '        print("위상 연산 및 시각화 완료!")\n'
with open(r'src/acousticstudio/app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Fixed exact broken line!")
