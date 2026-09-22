import sys
import vtk

rep = vtk.vtkAxesTransformRepresentation()
rep.SetLabelFormat("%-#6.3g")

w = vtk.vtkAxesTransformWidget()
w.SetRepresentation(rep)

ren = vtk.vtkRenderer()
renWin = vtk.vtkRenderWindow()
renWin.AddRenderer(ren)
iren = vtk.vtkRenderWindowInteractor()
iren.SetRenderWindow(renWin)

w.SetInteractor(iren)
w.SetCurrentRenderer(ren)
w.SetDefaultRenderer(ren)

renWin.Render()

# we can just exit
