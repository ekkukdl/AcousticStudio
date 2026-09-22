import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

hw_ui = '''        # --- 6. Hardware Connection ---
        hw_group = QGroupBox("6. Hardware Connection (하드웨어 제어)")
        hw_layout = QFormLayout()
        
        from PySide6.QtWidgets import QLineEdit, QHBoxLayout
        self.serial_port_edit = QLineEdit("COM3")
        self.serial_baud_edit = QLineEdit("115200")
        
        self.btn_connect_hw = QPushButton("Connect (연결)")
        self.btn_send_phase = QPushButton("Send Phase Data")
        self.btn_send_phase.setEnabled(False)
        
        hw_layout.addRow("Port:", self.serial_port_edit)
        hw_layout.addRow("Baud Rate:", self.serial_baud_edit)
        
        btn_hw_layout = QHBoxLayout()
        btn_hw_layout.addWidget(self.btn_connect_hw)
        btn_hw_layout.addWidget(self.btn_send_phase)
        hw_layout.addRow(btn_hw_layout)
        
        hw_group.setLayout(hw_layout)
        control_layout.addWidget(hw_group)
        
        # Spacer'''

text = text.replace('# Spacer', hw_ui)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Hardware UI added!")
