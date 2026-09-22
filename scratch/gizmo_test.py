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
        self.rep = vtk.vtkBoxRepresentation()
        self.rep.SetPlaceFactor(1.25)
        self.rep.PlaceWidget(self.actor.GetBounds())
        
        self.widget = vtk.vtkBoxWidget2()
        self.widget.SetRepresentation(self.rep)
        self.widget.SetInteractor(self.plotter.interactor)
        
        # Disable rotation and scaling for simple translation
        self.widget.SetTranslationEnabled(True)
        self.widget.SetRotationEnabled(False)
        self.widget.SetScalingEnabled(False)
        
        self.widget.AddObserver("InteractionEvent", self.on_interaction)
        self.widget.On()
        
    def on_interaction(self, caller, event):
        transform = vtk.vtkTransform()
        self.rep.GetTransform(transform)
        self.actor.SetUserTransform(transform)
        self.plotter.render()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
