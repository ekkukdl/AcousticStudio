import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Fix eventFilter MouseButtonPress
press_replacement = r'''
        if event.type() == QEvent.MouseButtonPress:
            scale = self.main.plotter.interactor.devicePixelRatioF()
            pos = event.position().toPoint()
            scaled_x = int(round(pos.x() * scale))
            scaled_y = int(round(pos.y() * scale))
            vtk_y = self.main.plotter.window_size[1] - scaled_y - 1
'''
text = re.sub(r'\s*if event\.type\(\) == QEvent\.MouseButtonPress:\s*pos = event\.position\(\)\.toPoint\(\)\s*vtk_y = self\.main\.plotter\.window_size\[1\] - pos\.y\(\)', press_replacement, text)

# 2. Fix eventFilter MouseMove
move_replacement = r'''
        elif event.type() == QEvent.MouseMove:
            scale = self.main.plotter.interactor.devicePixelRatioF()
            pos = event.position().toPoint()
            scaled_y = int(round(pos.y() * scale))
            vtk_y = self.main.plotter.window_size[1] - scaled_y - 1
'''
text = re.sub(r'\s*elif event\.type\(\) == QEvent\.MouseMove:\s*pos = event\.position\(\)\.toPoint\(\)\s*vtk_y = self\.main\.plotter\.window_size\[1\] - pos\.y\(\)', move_replacement, text)

# 3. Fix eventFilter MouseButtonRelease
release_replacement = r'''
        elif event.type() == QEvent.MouseButtonRelease:
            scale = self.main.plotter.interactor.devicePixelRatioF()
            pos = event.position().toPoint()
            scaled_y = int(round(pos.y() * scale))
            vtk_y = self.main.plotter.window_size[1] - scaled_y - 1
'''
text = re.sub(r'\s*elif event\.type\(\) == QEvent\.MouseButtonRelease:\s*pos = event\.position\(\)\.toPoint\(\)\s*vtk_y = self\.main\.plotter\.window_size\[1\] - pos\.y\(\)', release_replacement, text)

# 4. Fix process_selection
selection_replacement = r'''
    def process_selection(self, start_pos, end_pos, modifiers):
        scale = self.plotter.interactor.devicePixelRatioF()
        x0 = int(round(start_pos.x() * scale))
        y0 = int(round(start_pos.y() * scale))
        x1 = int(round(end_pos.x() * scale))
        y1 = int(round(end_pos.y() * scale))
        
        vtk_y0 = self.plotter.window_size[1] - y0 - 1
        vtk_y1 = self.plotter.window_size[1] - y1 - 1
'''
text = re.sub(r'\s*def process_selection\(self, start_pos, end_pos, modifiers\):\s*vtk_y0 = self\.plotter\.window_size\[1\] - start_pos\.y\(\)\s*vtk_y1 = self\.plotter\.window_size\[1\] - end_pos\.y\(\)\s*x0, x1 = start_pos\.x\(\), end_pos\.x\(\)', selection_replacement, text)

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
print("Fixed DPI coordinate scaling!")
