import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

variables = '''
        self.sel_x = QDoubleSpinBox(); self.sel_x.setRange(-2000, 2000)
        self.sel_y = QDoubleSpinBox(); self.sel_y.setRange(-2000, 2000)
        self.sel_z = QDoubleSpinBox(); self.sel_z.setRange(-2000, 2000)
        self.sel_rx = QDoubleSpinBox(); self.sel_rx.setRange(-360, 360)
        self.sel_ry = QDoubleSpinBox(); self.sel_ry.setRange(-360, 360)
        self.sel_rz = QDoubleSpinBox(); self.sel_rz.setRange(-360, 360)
        
        from PySide6.QtWidgets import QGridLayout
'''

text = text.replace('from PySide6.QtWidgets import QGridLayout', variables)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Restored deleted spinboxes")
