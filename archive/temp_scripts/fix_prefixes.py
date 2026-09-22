import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# Remove setPrefix calls
text = re.sub(r';\s*self\.sel_x\.setPrefix\(\"X:\"\)', '', text)
text = re.sub(r';\s*self\.sel_y\.setPrefix\(\"Y:\"\)', '', text)
text = re.sub(r';\s*self\.sel_z\.setPrefix\(\"Z:\"\)', '', text)
text = re.sub(r';\s*self\.sel_rx\.setPrefix\(\"Rx:\"\)', '', text)
text = re.sub(r';\s*self\.sel_ry\.setPrefix\(\"Ry:\"\)', '', text)
text = re.sub(r';\s*self\.sel_rz\.setPrefix\(\"Rz:\"\)', '', text)

# Update row labels
text = re.sub(r't_layout\.addRow\(\"위치 \(mm\):\",\s*pos_lyt\)', 't_layout.addRow("위치 (X,Y,Z):", pos_lyt)', text)
text = re.sub(r't_layout\.addRow\(\"회전 \(deg\):\",\s*rot_lyt\)', 't_layout.addRow("회전 (Rx,Ry,Rz):", rot_lyt)', text)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
