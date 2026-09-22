import sys
import os
os.environ["QT_API"] = "pyside6"
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import QApplication, QMainWindow
import vtk

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.plotter = QtInteractor(self)
        self.setCentralWidget(self.plotter.interactor)
        self.plotter.add_mesh(pv.Cube())
        
        # Test getting interactor
        try:
            iren1 = self.plotter.interactor
            gizmo1 = vtk.vtkAxesTransformWidget()
            gizmo1.SetInteractor(iren1)
            print("SetInteractor with plotter.interactor SUCCESS")
        except Exception as e:
            print(f"SetInteractor with plotter.interactor FAILED: {e}")
            
        try:
            iren2 = self.plotter.render_window.GetInteractor()
            gizmo2 = vtk.vtkAxesTransformWidget()
            gizmo2.SetInteractor(iren2)
            print("SetInteractor with render_window.GetInteractor() SUCCESS")
        except Exception as e:
            print(f"SetInteractor with render_window.GetInteractor() FAILED: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    import threading
    threading.Timer(1.0, app.quit).start()
    sys.exit(app.exec())
