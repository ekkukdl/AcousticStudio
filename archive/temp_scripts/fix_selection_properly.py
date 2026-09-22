import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the process_selection method
def fix_process_selection(match):
    return """
        if dx < 5 and dy < 5:
            prop_picker = vtk.vtkPropPicker()
            prop_picker.Pick(x0, vtk_y0, 0, renderer)
            prop = prop_picker.GetViewProp()
            pv_act = self.get_pyvista_actor(prop)
            if pv_act is not None:
                picked_props.append(pv_act)
        else:
            xmin, xmax = min(x0, x1), max(x0, x1)
            ymin, ymax = min(vtk_y0, vtk_y1), max(vtk_y0, vtk_y1)
            self.area_picker.AreaPick(xmin, ymin, xmax, ymax, renderer)
            
            props = self.area_picker.GetProp3Ds()
            props.InitTraversal()
            prop = props.GetNextProp3D()
            while prop:
                pv_act = self.get_pyvista_actor(prop)
                if pv_act is not None:
                    picked_props.append(pv_act)
                prop = props.GetNextProp3D()
"""

# Replace the whole if-else block
pattern = r'if dx < 5 and dy < 5:.*?prop = props\.GetNextProp3D\(\)'
text = re.sub(pattern, fix_process_selection, text, flags=re.DOTALL)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Re-fixed selection bug properly")
