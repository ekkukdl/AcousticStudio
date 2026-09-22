import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
from acousticstudio.app import AcousticStudioMain
from PySide6.QtWidgets import QApplication
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = AcousticStudioMain()
    window.show()
    sys.exit(app.exec())
