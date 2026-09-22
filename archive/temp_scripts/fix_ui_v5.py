import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix "센서 형태:"
text = re.sub(r'array_layout\.addRow\(\".*?\",\s*self\.transducer_type_cb\)', 'array_layout.addRow(\"센서 형태:\", self.transducer_type_cb)', text)

# Fix "배열 3D 뷰어에 생성하기"
text = re.sub(r'QPushButton\(\".*?3D.*?\"\)', 'QPushButton("배열 3D 뷰어에 생성하기")', text)

# Fix "Calculate Phase (위상 계산 및 시각화)"
text = re.sub(r'QPushButton\(\"Calculate Phase.*?\"\)', 'QPushButton("Calculate Phase (위상 계산 및 시각화)")', text)

# Fix "YZ (정면)"
text = re.sub(r'QCheckBox\(\"YZ.*?\"\)', 'QCheckBox("YZ (정면)")', text)

# Fix "음압 단면 보기 (ON/OFF)" (Initial Button instantiation)
text = re.sub(r'QPushButton\(\".*?\(ON/OFF\)\"\)', 'QPushButton("음압 단면 보기 (ON/OFF)")', text)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Done fixing remaining buttons!")
