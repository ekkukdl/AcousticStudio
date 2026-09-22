import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add QScrollArea to imports
text = text.replace('from PySide6.QtWidgets import ', 'from PySide6.QtWidgets import QScrollArea, ')

# 2. Add ScrollArea
replacement = r'''
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        # Optional: remove border to make it look cleaner
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        
        scroll_area.setWidget(control_panel)
        main_layout.addWidget(scroll_area, stretch=1)
'''

text = re.sub(r'\s*control_panel = QWidget\(\)\s*control_layout = QVBoxLayout\(control_panel\)\s*main_layout\.addWidget\(control_panel, stretch=1\)', replacement, text)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("ScrollArea added!")
