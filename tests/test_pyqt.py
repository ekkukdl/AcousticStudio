import sys
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
import vtk

class CustomRubberBandStyle(vtk.vtkInteractorStyleRubberBandPick):
    def __init__(self):
        super().__init__()
        self.AddObserver("LeftButtonPressEvent", self.on_left_press)

    def on_left_press(self, obj, event):
        iren = self.GetInteractor()
        if iren:
            iren.SetKeyCode('r')
            self.OnChar()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.plotter = QtInteractor(self)
        self.setCentralWidget(self.plotter.interactor)
        self.plotter.add_mesh(pv.Cube())
        
        self.style = CustomRubberBandStyle()
        self.plotter.interactor.SetInteractorStyle(self.style)
        
        def on_pick(caller, event):
            print("Picked!")
            
        self.style.AddObserver("EndPickEvent", on_pick)
        
        # Simulate click
        iren = self.plotter.interactor
        iren.SetEventPosition(100, 100)
        iren.LeftButtonPressEvent()
        iren.SetEventPosition(200, 200)
        iren.MouseMoveEvent()
        iren.LeftButtonReleaseEvent()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    # Close automatically after 2 seconds for test
    import threading
    threading.Timer(2.0, app.quit).start()
    sys.exit(app.exec())
