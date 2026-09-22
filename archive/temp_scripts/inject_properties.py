import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

if 'QFormLayout' not in text:
    text = text.replace('QVBoxLayout,', 'QVBoxLayout, QFormLayout,')

prop_ui = r'''
        # Properties Group
        self.prop_group = QGroupBox("Selected Properties (속성 조절)")
        prop_layout = QFormLayout()
        
        self.prop_type_lbl = QLabel("-")
        self.prop_sensor_cb = QComboBox()
        self.prop_sensor_cb.addItems(["소형 초음파센서 (10mm)", "소형 초음파센서 (16mm)", "랑주뱅 진동자 (Langevin)"])
        
        self.prop_radius_spin = QDoubleSpinBox()
        self.prop_radius_spin.setRange(0.1, 100.0)
        self.prop_radius_spin.setSuffix(" mm")
        
        prop_layout.addRow("선택 객체:", self.prop_type_lbl)
        prop_layout.addRow("센서 변경:", self.prop_sensor_cb)
        prop_layout.addRow("반경 조절:", self.prop_radius_spin)
        
        self.prop_group.setLayout(prop_layout)
        control_layout.addWidget(self.prop_group)

        self.prop_sensor_cb.currentIndexChanged.connect(self.on_prop_sensor_changed)
        self.prop_radius_spin.valueChanged.connect(self.on_prop_radius_changed)
'''

text = text.replace('control_layout.addWidget(transform_group)', 'control_layout.addWidget(transform_group)\n' + prop_ui)

callbacks = r'''
    def on_prop_sensor_changed(self, idx):
        if getattr(self, '_is_updating_ui', False) or not self.selected_actors: return
        sensor_type = self.prop_sensor_cb.currentText()
        if "10mm" in sensor_type:
            r_wide, r_narrow, height, color = 5.0, 3.5, 4.0, "lightblue"
        elif "16mm" in sensor_type:
            r_wide, r_narrow, height, color = 8.0, 5.0, 6.0, "orange"
        else: # Langevin
            r_wide, r_narrow, height, color = 25.0, 15.0, 40.0, "gray"
            
        new_actors = []
        for act in self.selected_actors:
            if act in self.transducer_actors:
                mat = act.GetUserMatrix() or getattr(act, '_initial_matrix', None)
                self.plotter.remove_actor(act)
                self.transducer_actors.remove(act)
                
                pts = self.make_truncated_cone(r_wide, r_narrow, height)
                faces = [[len(pts)] + list(range(len(pts)))]
                import pyvista as pv
                mesh = pv.PolyData(pts, faces)
                
                new_act = self.plotter.add_mesh(mesh, color=color, show_edges=True)
                if mat:
                    new_act.SetUserMatrix(mat)
                    new_act._initial_matrix = mat
                new_act._original_color = color
                new_act.prop.color = "pink"
                self.transducer_actors.append(new_act)
                new_actors.append(new_act)
            else:
                new_actors.append(act)
        self.selected_actors = new_actors
        self.plotter.render()
        
    def on_prop_radius_changed(self, val):
        if getattr(self, '_is_updating_ui', False) or not self.selected_actors: return
        new_actors = []
        for act in self.selected_actors:
            is_cp = False
            for pt in self.control_points:
                if pt["actor"] == act:
                    is_cp = True
                    x, y, z = pt["x"], pt["y"], pt["z"]
                    pt["radius"] = val
                    self.plotter.remove_actor(act)
                    import pyvista as pv
                    import vtk
                    sphere = pv.Sphere(radius=val, center=(x, y, z))
                    new_act = self.plotter.add_mesh(sphere, color="green", show_edges=False)
                    new_act._original_color = "green"
                    new_act.prop.color = "pink"
                    pt["actor"] = new_act
                    
                    mat = act.GetUserMatrix()
                    if mat: new_act.SetUserMatrix(mat)
                    new_act._initial_matrix = getattr(act, '_initial_matrix', vtk.vtkMatrix4x4())
                    new_actors.append(new_act)
                    break
            if not is_cp:
                new_actors.append(act)
        self.selected_actors = new_actors
        self.plotter.render()
'''

text = text.replace('def delete_selected_objects(self):', callbacks + '\n    def delete_selected_objects(self):')

ui_update = r'''
        self.prop_sensor_cb.setEnabled(False)
        self.prop_radius_spin.setEnabled(False)
        self.prop_type_lbl.setText("-")
        
        has_sensor = any(a in self.transducer_actors for a in self.selected_actors)
        cp_actor = None
        has_cp = False
        for a in self.selected_actors:
            if any(pt["actor"] == a for pt in self.control_points):
                has_cp = True
                cp_actor = a
                break
                
        if has_sensor and not has_cp:
            self.prop_type_lbl.setText("초음파 센서")
            self.prop_sensor_cb.setEnabled(True)
        elif has_cp and not has_sensor:
            self.prop_type_lbl.setText("타겟 (Control Point)")
            self.prop_radius_spin.setEnabled(True)
            for pt in self.control_points:
                if pt["actor"] == cp_actor:
                    self.prop_radius_spin.setValue(pt.get("radius", 5.0))
                    break
        elif has_sensor and has_cp:
            self.prop_type_lbl.setText("다중 선택 (혼합)")
'''

text = re.sub(r'(self\.sel_rx\.setValue\(0\);\s*self\.sel_ry\.setValue\(0\);\s*self\.sel_rz\.setValue\(0\))', r'\1\n' + ui_update, text)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("UI Properties Panel injected")
