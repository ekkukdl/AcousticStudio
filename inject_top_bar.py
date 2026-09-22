import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Change QHBoxLayout to QVBoxLayout for main_layout
text = text.replace('main_layout = QHBoxLayout(main_widget)', 'main_layout = QVBoxLayout(main_widget)')

# 2. Insert the top bar immediately after
top_bar_code = '''main_layout = QVBoxLayout(main_widget)
        
        # --- Top Bar (USB Connection) ---
        from PySide6.QtWidgets import QGroupBox, QFormLayout, QLineEdit, QHBoxLayout, QPushButton
        top_hw_group = QGroupBox("Hardware Connection (USB Serial)")
        top_hw_layout = QHBoxLayout()
        
        from PySide6.QtWidgets import QLabel
        top_hw_layout.addWidget(QLabel("Port:"))
        self.serial_port_edit = QLineEdit("COM3")
        self.serial_port_edit.setMaximumWidth(100)
        top_hw_layout.addWidget(self.serial_port_edit)
        
        top_hw_layout.addWidget(QLabel("Baud Rate:"))
        self.serial_baud_edit = QLineEdit("115200")
        self.serial_baud_edit.setMaximumWidth(100)
        top_hw_layout.addWidget(self.serial_baud_edit)
        
        self.btn_connect_hw = QPushButton("Connect (연결)")
        top_hw_layout.addWidget(self.btn_connect_hw)
        
        self.btn_send_phase = QPushButton("Send Phase Data")
        self.btn_send_phase.setEnabled(False)
        top_hw_layout.addWidget(self.btn_send_phase)
        
        top_hw_layout.addStretch() # Push everything to the left
        
        top_hw_group.setLayout(top_hw_layout)
        main_layout.addWidget(top_hw_group)
        # --------------------------------
'''
text = text.replace('main_layout = QVBoxLayout(main_widget)', top_bar_code)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Top bar injected!")
