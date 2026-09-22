import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

hw_logic = '''
    def connect_hw(self):
        if not hasattr(self, 'serial_port') or self.serial_port is None:
            port = self.serial_port_edit.text()
            try:
                baud = int(self.serial_baud_edit.text())
            except ValueError:
                QMessageBox.critical(self, "Error", "Invalid Baud Rate.")
                return
                
            try:
                import serial
                self.serial_port = serial.Serial(port, baud, timeout=1)
                self.btn_connect_hw.setText("Disconnect (연결 해제)")
                self.btn_send_phase.setEnabled(True)
                QMessageBox.information(self, "Hardware", f"Connected to {port} at {baud} baud.")
            except Exception as e:
                QMessageBox.critical(self, "Connection Error", f"Failed to connect to {port}:\\n{str(e)}")
        else:
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None
            self.btn_connect_hw.setText("Connect (연결)")
            self.btn_send_phase.setEnabled(False)
            QMessageBox.information(self, "Hardware", "Disconnected.")

    def send_phase_data(self):
        if not hasattr(self, 'serial_port') or self.serial_port is None:
            return
            
        import numpy as np
        phases = []
        for act in self.transducer_actors:
            phase = getattr(act, '_phase', 0.0)
            # Map 0 ~ 2*pi to 0 ~ 255 (8-bit)
            val = int(round((phase / (2.0 * np.pi)) * 255))
            val = max(0, min(255, val))
            phases.append(val)
            
        if not phases:
            return
            
        try:
            data = bytes(phases)
            # Protocol: 'S' (1 byte) + Length (2 bytes) + Data (N bytes)
            header = b'S' + len(data).to_bytes(2, byteorder='little')
            self.serial_port.write(header + data)
            print(f"HW: Sent phase data for {len(phases)} transducers.")
        except Exception as e:
            print(f"HW Send Error: {e}")
            
    def apply_ui_transform(self):'''

text = text.replace('    def apply_ui_transform(self):', hw_logic)

# Connect the buttons
btn_connects = '''        self.btn_connect_hw.clicked.connect(self.connect_hw)
        self.btn_send_phase.clicked.connect(self.send_phase_data)
        
        # Connect signals for Grid updates'''
text = text.replace('        # Connect signals for Grid updates', btn_connects)

# Auto-send when calculate phase is done
auto_send = '''        self.plotter.render()
        
        # 6. 하드웨어가 연결되어 있다면 실시간으로 데이터 전송
        if hasattr(self, 'serial_port') and self.serial_port is not None:
            self.send_phase_data()
'''
text = text.replace('        self.plotter.render()\n\n        # 각 객체별 마다의 위상 값을 디스플레이', auto_send + '\n        # 각 객체별 마다의 위상 값을 디스플레이')

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Hardware Logic Added!")
