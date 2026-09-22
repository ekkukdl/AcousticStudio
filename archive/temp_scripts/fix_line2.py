with open(r'src/acousticstudio/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
lines[1735] = '            print("에러: 타겟(Control Point)이 1개 이상 존재해야 위상을 계산할 수 있습니다.")\n'
with open(r'src/acousticstudio/app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Fixed line 1736!")
