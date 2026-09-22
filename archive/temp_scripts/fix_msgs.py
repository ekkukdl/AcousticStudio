import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the warning message
text = re.sub(r'QMessageBox\.warning\(self,\s*\"Warning\",\s*\".*?1.*?\"\)', 'QMessageBox.warning(self, "Warning", "에러: 타겟(Control Point)이 1개 이상 존재해야 위상을 계산할 수 있습니다.")', text)
text = re.sub(r'QMessageBox\.warning\(self,\s*\"Warning\",\s*\".*?\"\)', 'QMessageBox.warning(self, "Warning", "에러: 타겟(Control Point)이 1개 이상 존재해야 위상을 계산할 수 있습니다.")', text) # aggressive match if 1 is missing

# Fix the info message
text = re.sub(r'QMessageBox\.information\(self,\s*\"Information\",\s*\".*?\"\)', 'QMessageBox.information(self, "Information", "위상 연산 및 시각화 완료!")', text)

# Fix the button texts in toggle_field_slice
text = re.sub(r'self\.show_field_btn\.setText\(\".*?\(ON/OFF\)\"\)', 'self.show_field_btn.setText("음압 단면 보기 (ON/OFF)")', text)
text = re.sub(r'self\.show_field_btn\.setText\(\"(?!음압).*?\"\)', 'self.show_field_btn.setText("음압 단면 숨기기")', text)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
