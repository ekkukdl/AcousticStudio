import re
filename = r'src/acousticstudio/app.py'
with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('print(f"Selection Error: {e}")', 'import traceback; traceback.print_exc()')

with open(filename, 'w', encoding='utf-8') as f:
    f.write(text)
