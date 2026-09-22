import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from pyvistaqt import QtInteractor
import pyvista as pv
import vtk

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(800, 600)
        self.central = QWidget()
        self.setCentralWidget(self.central)
        layout = QVBoxLayout(self.central)
        
        self.plotter = QtInteractor(self.central)
        layout.addWidget(self.plotter.interactor)
        
        self.mesh = pv.Sphere(radius=10, center=(0,0,0))
        self.actor = self.plotter.add_mesh(self.mesh, color='green')
        
        # Setup Gizmo
        self.gizmo_rep = vtk.vtkAxesTransformRepresentation()
        self.gizmo_widget = vtk.vtkAxesTransformWidget()
        self.gizmo_widget.SetRepresentation(self.gizmo_rep)
        self.gizmo_widget.SetInteractor(self.plotter.iren.interactor)
        self.gizmo_widget.SetCurrentRenderer(self.plotter.renderer)
        self.gizmo_widget.SetDefaultRenderer(self.plotter.renderer)
        
        self.gizmo_widget.On()
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    # close after 2 seconds
    import threading
    threading.Timer(2.0, app.quit).start()
    sys.exit(app.exec())
