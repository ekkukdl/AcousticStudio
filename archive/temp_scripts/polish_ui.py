import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. ScrollArea styling and margins
scroll_style = '''
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(128, 128, 128, 150);
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        
        control_panel = QWidget()
        control_panel.setMinimumWidth(380)
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(5, 10, 15, 10)
'''

text = re.sub(r'\s*scroll_area = QScrollArea\(\)\s*scroll_area\.setWidgetResizable\(True\)\s*# Optional: remove border to make it look cleaner\s*scroll_area\.setFrameShape\(QScrollArea\.Shape\.NoFrame\)\s*control_panel = QWidget\(\)\s*control_layout = QVBoxLayout\(control_panel\)', scroll_style, text)


# 2. Fix 1. Selected Object Transform layout
t_layout_replacement = '''
        from PySide6.QtWidgets import QGridLayout
        t_layout = QGridLayout()
        t_layout.addWidget(QLabel("위치 (mm):"), 0, 0)
        t_layout.addWidget(QLabel("X:"), 0, 1)
        t_layout.addWidget(self.sel_x, 0, 2)
        t_layout.addWidget(QLabel("Y:"), 0, 3)
        t_layout.addWidget(self.sel_y, 0, 4)
        t_layout.addWidget(QLabel("Z:"), 0, 5)
        t_layout.addWidget(self.sel_z, 0, 6)

        t_layout.addWidget(QLabel("회전 (deg):"), 1, 0)
        t_layout.addWidget(QLabel("Rx:"), 1, 1)
        t_layout.addWidget(self.sel_rx, 1, 2)
        t_layout.addWidget(QLabel("Ry:"), 1, 3)
        t_layout.addWidget(self.sel_ry, 1, 4)
        t_layout.addWidget(QLabel("Rz:"), 1, 5)
        t_layout.addWidget(self.sel_rz, 1, 6)

        transform_group.setLayout(t_layout)
        control_layout.addWidget(transform_group)
'''
text = re.sub(r't_layout = QFormLayout\(\).*?control_layout\.addWidget\(transform_group\)', t_layout_replacement, text, flags=re.DOTALL)


# 3. Fix 2. Transducer Array Setup layout
array_layout_replacement = '''
        gen_grid = QGridLayout()
        gen_grid.addWidget(QLabel("생성 위치 (mm):"), 0, 0)
        gen_grid.addWidget(QLabel("X:"), 0, 1)
        gen_grid.addWidget(self.gen_pos_x, 0, 2)
        gen_grid.addWidget(QLabel("Y:"), 0, 3)
        gen_grid.addWidget(self.gen_pos_y, 0, 4)
        gen_grid.addWidget(QLabel("Z:"), 0, 5)
        gen_grid.addWidget(self.gen_pos_z, 0, 6)

        gen_grid.addWidget(QLabel("생성 각도 (deg):"), 1, 0)
        gen_grid.addWidget(QLabel("Rx:"), 1, 1)
        gen_grid.addWidget(self.gen_rot_x, 1, 2)
        gen_grid.addWidget(QLabel("Ry:"), 1, 3)
        gen_grid.addWidget(self.gen_rot_y, 1, 4)
        gen_grid.addWidget(QLabel("Rz:"), 1, 5)
        gen_grid.addWidget(self.gen_rot_z, 1, 6)

        array_layout.addRow(gen_grid)
'''
text = re.sub(r'gen_pos_lyt = QHBoxLayout\(\).*?array_layout\.addRow\([^,]+,\s*gen_rot_lyt\)', array_layout_replacement, text, flags=re.DOTALL)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("UI polished!")
