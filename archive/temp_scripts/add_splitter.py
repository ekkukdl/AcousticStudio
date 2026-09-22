import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add imports
text = text.replace('from PySide6.QtWidgets import (QApplication', 'from PySide6.QtWidgets import (QApplication, QSplitter')

# 2. Remove old main_layout.addWidget calls
text = re.sub(r'\s*main_layout\.addWidget\(self\.view_panel, stretch=3\)', '', text)
text = re.sub(r'\s*main_layout\.addWidget\(scroll_area, stretch=1\)', '', text)

# 3. Add Splitter at the end of the constructor, or right after scroll_area
splitter_code = '''
        scroll_area.setWidget(control_panel)
        
        from PySide6.QtWidgets import QSplitter
        from PySide6.QtCore import Qt
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.view_panel)
        self.splitter.addWidget(scroll_area)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([1020, 380])
        
        main_layout.addWidget(self.splitter)
'''

text = text.replace('scroll_area.setWidget(control_panel)', splitter_code)

# Let's verify we didn't add it twice if we run this script again
# Also make sure we don't have dangling stretch additions

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Splitter added!")
