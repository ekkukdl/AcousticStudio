import re

filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add Gizmo initialization in __init__
gizmo_init = '''
        self.plotter.add_axes()
        
        # 3D Gizmo Initialization
        import vtk
        self.gizmo_rep = vtk.vtkAxesTransformRepresentation()
        self.gizmo_rep.GetLabelFormat().SetDrawLabels(False) # Hide coordinate labels to avoid clutter
        self.gizmo_widget = vtk.vtkAxesTransformWidget()
        self.gizmo_widget.SetRepresentation(self.gizmo_rep)
        self.gizmo_widget.SetInteractor(self.plotter.interactor)
        self.gizmo_widget.AddObserver("InteractionEvent", self.on_gizmo_interaction)
        self.gizmo_widget.Off()
'''
text = text.replace('self.plotter.add_axes()', gizmo_init)

# 2. Add Gizmo callback method
gizmo_callback = '''
    def on_gizmo_interaction(self, caller, event):
        if not self.selected_actors: return
        pos = self.gizmo_rep.GetOriginWorldPosition()
        
        # Temporarily disconnect spinboxes to avoid double-triggering or loops if needed,
        # but apply_ui_transform is exactly what we need to move the actors.
        # We just set the values and let the spinbox signals do the rest!
        # Wait, if we drag the gizmo, it updates the spinbox.
        # The spinbox triggers apply_ui_transform.
        # apply_ui_transform will move the actors, but it also tries to update the gizmo position...
        # We need to make sure apply_ui_transform doesn't reset the gizmo while we are dragging it!
        self._is_gizmo_dragging = True
        self.sel_x.setValue(pos[0])
        self.sel_y.setValue(pos[1])
        self.sel_z.setValue(pos[2])
        self._is_gizmo_dragging = False
        
    def process_selection(self, start_pos, end_pos, modifiers):
'''
text = text.replace('    def process_selection(self, start_pos, end_pos, modifiers):', gizmo_callback)


# 3. Update update_ui_from_selection to place and enable the Gizmo
gizmo_update = '''
        self.sel_z.setValue(cz)
        
        self._is_updating_ui = False
        
        # Update Gizmo
        if not getattr(self, '_is_gizmo_dragging', False):
            self.gizmo_rep.SetOriginWorldPosition((cx, cy, cz))
            self.gizmo_widget.On()
'''
text = text.replace('self.sel_z.setValue(cz)\n        \n        self._is_updating_ui = False', gizmo_update)

# 4. Hide Gizmo when nothing is selected
gizmo_hide = '''
        if not self.selected_actors:
            self._is_updating_ui = True
            self.sel_x.setValue(0); self.sel_y.setValue(0); self.sel_z.setValue(0)
            self.sel_rx.setValue(0); self.sel_ry.setValue(0); self.sel_rz.setValue(0)
            
            self.prop_sensor_cb.setEnabled(False)
            self.prop_radius_spin.setEnabled(False)
            self.prop_type_lbl.setText("-")
            
            self._is_updating_ui = False
            self.gizmo_widget.Off()
            return
'''
# We need to replace the exact block in update_ui_from_selection
# Wait, I'll use regex to inject self.gizmo_widget.Off()
text = re.sub(r'(self\._is_updating_ui = False\s*return)', r'self.gizmo_widget.Off()\n            \1', text)


with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Gizmo injected!")
