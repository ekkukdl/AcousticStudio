import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# Make sure QLabel is imported
if 'QLabel' not in text:
    text = text.replace('from PySide6.QtWidgets import ', 'from PySide6.QtWidgets import QLabel, ')

# Update Transform Group
text = re.sub(r'pos_lyt\.addWidget\(self\.sel_x\);\s*pos_lyt\.addWidget\(self\.sel_y\);\s*pos_lyt\.addWidget\(self\.sel_z\)',
              'pos_lyt.addWidget(QLabel("X:")); pos_lyt.addWidget(self.sel_x); pos_lyt.addWidget(QLabel("Y:")); pos_lyt.addWidget(self.sel_y); pos_lyt.addWidget(QLabel("Z:")); pos_lyt.addWidget(self.sel_z)', text)
text = re.sub(r'rot_lyt\.addWidget\(self\.sel_rx\);\s*rot_lyt\.addWidget\(self\.sel_ry\);\s*rot_lyt\.addWidget\(self\.sel_rz\)',
              'rot_lyt.addWidget(QLabel("Rx:")); rot_lyt.addWidget(self.sel_rx); rot_lyt.addWidget(QLabel("Ry:")); rot_lyt.addWidget(self.sel_ry); rot_lyt.addWidget(QLabel("Rz:")); rot_lyt.addWidget(self.sel_rz)', text)

# Update Transducer Array Setup group
text = re.sub(r'gen_pos_lyt\.addWidget\(self\.gen_pos_x\);\s*gen_pos_lyt\.addWidget\(self\.gen_pos_y\);\s*gen_pos_lyt\.addWidget\(self\.gen_pos_z\)',
              'gen_pos_lyt.addWidget(QLabel("X:")); gen_pos_lyt.addWidget(self.gen_pos_x); gen_pos_lyt.addWidget(QLabel("Y:")); gen_pos_lyt.addWidget(self.gen_pos_y); gen_pos_lyt.addWidget(QLabel("Z:")); gen_pos_lyt.addWidget(self.gen_pos_z)', text)
text = re.sub(r'gen_rot_lyt\.addWidget\(self\.gen_rot_x\);\s*gen_rot_lyt\.addWidget\(self\.gen_rot_y\);\s*gen_rot_lyt\.addWidget\(self\.gen_rot_z\)',
              'gen_rot_lyt.addWidget(QLabel("Rx:")); gen_rot_lyt.addWidget(self.gen_rot_x); gen_rot_lyt.addWidget(QLabel("Ry:")); gen_rot_lyt.addWidget(self.gen_rot_y); gen_rot_lyt.addWidget(QLabel("Rz:")); gen_rot_lyt.addWidget(self.gen_rot_z)', text)

# Remove (X,Y,Z) from row labels since they are now in front of the boxes
text = re.sub(r't_layout\.addRow\(\"위치 \(X,Y,Z\):\"', 't_layout.addRow("위치 (mm):"', text)
text = re.sub(r't_layout\.addRow\(\"회전 \(Rx,Ry,Rz\):\"', 't_layout.addRow("회전 (deg):"', text)
text = re.sub(r'array_layout\.addRow\(\"생성 위치 \(X,Y,Z\):\"', 'array_layout.addRow("생성 위치 (mm):"', text)
text = re.sub(r'array_layout\.addRow\(\"생성 각도 \(Rx,Ry,Rz\):\"', 'array_layout.addRow("생성 각도 (deg):"', text)

# Fix selection logic TypeError (modifiers integer vs Qt flags)
text = re.sub(r'is_ctrl = bool\(modifiers & Qt\.KeyboardModifier\.ControlModifier\)',
              'is_ctrl = bool(int(modifiers) & int(Qt.KeyboardModifier.ControlModifier)) if hasattr(modifiers, "__int__") else bool(modifiers & Qt.KeyboardModifier.ControlModifier.value) if type(modifiers) == int else bool(modifiers & Qt.KeyboardModifier.ControlModifier)', text)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("UI layout and selection fixed")
