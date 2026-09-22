import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

clean_method = '''    def update_ui_from_selection(self):
        self._is_updating_ui = True
        
        if not self.selected_actors:
            self.sel_x.setValue(0); self.sel_y.setValue(0); self.sel_z.setValue(0)
            self.sel_rx.setValue(0); self.sel_ry.setValue(0); self.sel_rz.setValue(0)
            self.prop_sensor_cb.setEnabled(False)
            self.prop_radius_spin.setEnabled(False)
            self.prop_type_lbl.setText("-")
            
            self._sel_base_centroid = [0.0, 0.0, 0.0]
            self._sel_base_rot = [0.0, 0.0, 0.0]
            if hasattr(self, 'gizmo_widget'):
                self.gizmo_widget.Off()
            self._is_updating_ui = False
            return
            
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
            
        cx, cy, cz = 0.0, 0.0, 0.0
        for act in self.selected_actors:
            c = act.center
            cx += c[0]; cy += c[1]; cz += c[2]
        n = len(self.selected_actors)
        cx /= n; cy /= n; cz /= n
        
        self._sel_base_centroid = [cx, cy, cz]
        self._sel_base_rot = [0.0, 0.0, 0.0]
        
        self.sel_x.setValue(cx)
        self.sel_y.setValue(cy)
        self.sel_z.setValue(cz)
        
        self._is_updating_ui = False
        
        # Update Gizmo
        if hasattr(self, 'gizmo_widget') and not getattr(self, '_is_gizmo_dragging', False):
            self.gizmo_rep.SetOriginWorldPosition((cx, cy, cz))
            self.gizmo_widget.On()
            
    def get_control_point_actors(self):'''

text = re.sub(r'\s*def update_ui_from_selection\(self\):.*?def get_control_point_actors\(self\):', '\n' + clean_method, text, flags=re.DOTALL)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("update_ui_from_selection fixed!")
