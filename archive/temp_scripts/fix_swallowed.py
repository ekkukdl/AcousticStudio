# -*- coding: utf-8 -*-
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.strip().startswith('#') and 'self.plotter.add_key_event' in line:
        parts = line.split('self.plotter.add_key_event')
        lines[i] = parts[0] + '\n        self.plotter.add_key_event' + parts[1]
    
    if line.strip().startswith('#') and 'actor.prop.color = rgba[:3]' in line:
        parts = line.split('actor.prop.color = rgba[:3]')
        lines[i] = parts[0] + '\n            actor.prop.color = rgba[:3]' + parts[1]
        
    if line.strip().startswith('#') and 'c = 343000.0' in line:
        parts = line.split('c = 343000.0')
        lines[i] = parts[0] + '\n        c = 343000.0' + parts[1]

with open(filename, 'w', encoding='utf-8') as f:
    f.writelines(lines)
