import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if 'if dx < 5 and dy < 5:' in line and 'prop_picker' not in line:
        # Starting block
        skip = True
        new_lines.append("""        if dx < 5 and dy < 5:
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
""")
    if skip:
        if 'is_ctrl = ' in line:
            skip = False
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(filename, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Fixed Indentation and Duplication!')
