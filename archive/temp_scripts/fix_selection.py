import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# Create a safe matching function at the class level
match_func = """
    def get_pyvista_actor(self, vtk_prop):
        if vtk_prop is None: return None
        addr = vtk_prop.GetAddressAsString("vtkProp")
        for a in self.transducer_actors:
            if a.GetAddressAsString("vtkProp") == addr: return a
        for a in self.get_control_point_actors():
            if a.GetAddressAsString("vtkProp") == addr: return a
        return None
"""

if 'def get_pyvista_actor' not in text:
    text = text.replace('def get_control_point_actors(self):', match_func + '\n    def get_control_point_actors(self):')

# Replace the condition in process_selection
text = text.replace('if prop and (prop in self.transducer_actors or prop in cp_actors):',
                    'pv_act = self.get_pyvista_actor(prop)\n        if pv_act is not None:\n            prop = pv_act')

text = text.replace('if prop in self.transducer_actors or prop in cp_actors:',
                    'pv_act = self.get_pyvista_actor(prop)\n            if pv_act is not None:\n                prop = pv_act')

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Selection bug fixed")
