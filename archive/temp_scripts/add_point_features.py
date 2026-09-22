import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add point size UI
ui_insertion = """
        self.point_size_spin = QDoubleSpinBox()
        self.point_size_spin.setRange(0.1, 50.0)
        self.point_size_spin.setValue(5.0)
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("타겟 반경 (mm):"))
        size_layout.addWidget(self.point_size_spin)
        points_layout.addLayout(size_layout)
        
        self.points_list = QListWidget()
"""
text = text.replace('self.points_list = QListWidget()', ui_insertion)

# Fix the auto_calc_cb label properly
text = re.sub(r'self\.auto_calc_cb = QCheckBox\(\".*?\"\)', 'self.auto_calc_cb = QCheckBox("Point 위치 변동 시 위상/음압 실시간 자동 계산")', text)

# 2. Modify add_control_point to use checkable items and point_size_spin
add_point_replacement = """
        radius = getattr(self, 'point_size_spin', None)
        r = radius.value() if radius else 5.0
        sphere = pv.Sphere(radius=r, center=(x, y, z))
        actor = self.plotter.add_mesh(sphere, color="green", show_edges=False)
        actor._original_color = "green"
        self.control_points.append({"name": name, "actor": actor, "x": x, "y": y, "z": z, "radius": r})
        
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self.points_list.addItem(item)
"""
# We need to replace the old append/addItem logic
text = re.sub(r'sphere = pv\.Sphere\(radius=5\.0, center=\(x, y, z\)\).*?self\.points_list\.addItem\(name\)', add_point_replacement, text, flags=re.DOTALL)


# 3. Block signals in update_ui_from_selection to prevent ANY accidental auto-calc
block_signals_start = """
        self.sel_x.blockSignals(True)
        self.sel_y.blockSignals(True)
        self.sel_z.blockSignals(True)
        self.sel_rx.blockSignals(True)
        self.sel_ry.blockSignals(True)
        self.sel_rz.blockSignals(True)
        
        self.sel_x.setValue(cx); self.sel_y.setValue(cy); self.sel_z.setValue(cz)
        self.sel_rx.setValue(0); self.sel_ry.setValue(0); self.sel_rz.setValue(0)
"""
block_signals_end = """
        self.sel_x.blockSignals(False)
        self.sel_y.blockSignals(False)
        self.sel_z.blockSignals(False)
        self.sel_rx.blockSignals(False)
        self.sel_ry.blockSignals(False)
        self.sel_rz.blockSignals(False)
        
        self._is_updating_ui = False
"""
text = re.sub(r'self\.sel_x\.setValue\(cx\);\s*self\.sel_y\.setValue\(cy\);\s*self\.sel_z\.setValue\(cz\).*?self\.sel_rz\.setValue\(0\)', block_signals_start, text, flags=re.DOTALL)
text = text.replace('self._is_updating_ui = False', block_signals_end)


# 4. Modify simulate_colors to check item state
simulate_loop_replacement = """
            complex_p = 0.0 + 0.0j
            
            # Check which points are active
            active_pts = []
            for idx, pt in enumerate(self.control_points):
                item = self.points_list.item(idx)
                if item and item.checkState() == Qt.Checked:
                    active_pts.append(pt)
            
            for pt in active_pts:
"""
text = re.sub(r'complex_p = 0\.0 \+ 0\.0j.*?for pt in self\.control_points:', simulate_loop_replacement, text, flags=re.DOTALL)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Features added successfully!")
