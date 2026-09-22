import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# Remove the previously incorrectly inserted blockSignals
text = re.sub(r'([ \t]*)self\.sel_x\.blockSignals\(False\)\n.*?self\._is_updating_ui = False', r'\1self._is_updating_ui = False', text, flags=re.DOTALL)
text = re.sub(r'([ \t]*)self\.sel_x\.blockSignals\(True\)\n.*?self\.sel_rz\.setValue\(0\)', r'\1self.sel_x.setValue(cx); self.sel_y.setValue(cy); self.sel_z.setValue(cz)\n\1self.sel_rx.setValue(0); self.sel_ry.setValue(0); self.sel_rz.setValue(0)', text, flags=re.DOTALL)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Reverted bad blocks")
