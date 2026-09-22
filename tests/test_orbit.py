import sys
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import QApplication, QMainWindow
import vtk

class CustomStyle(vtk.vtkInteractorStyleTrackballCamera):
    def __init__(self):
        super().__init__()
        self.AddObserver("RightButtonPressEvent", self.on_right_down)
        self.AddObserver("RightButtonReleaseEvent", self.on_right_up)

    def on_right_down(self, obj, event):
        self.OnLeftButtonDown()

    def on_right_up(self, obj, event):
        self.OnLeftButtonUp()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.plotter = QtInteractor(self)
        self.setCentralWidget(self.plotter.interactor)
        self.plotter.add_mesh(pv.Cube())
        
        self.style = CustomStyle()
        self.plotter.interactor.SetInteractorStyle(self.style)
        
        # add gizmo
        self.gizmo = vtk.vtkAxesTransformWidget()
        self.gizmo.SetInteractor(self.plotter.interactor)
        rep = vtk.vtkAxesTransformRepresentation()
        self.gizmo.SetRepresentation(rep)
        rep.PlaceWidget([-1, 1, -1, 1, -1, 1])
        self.gizmo.On()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    import threading
    threading.Timer(2.0, app.quit).start()
    sys.exit(app.exec())
