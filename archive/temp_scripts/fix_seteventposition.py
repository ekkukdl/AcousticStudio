import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace pos.x() with scaled_x where scaled_x is available
text = re.sub(r'iren\.SetEventPosition\(pos\.x\(\), vtk_y\)', r'iren.SetEventPosition(scaled_x if "scaled_x" in locals() else int(round(pos.x() * scale)), vtk_y)', text)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Fixed SetEventPosition scaling")
