from pathlib import Path
import cadquery as cq
import vtk

ROOT=Path(__file__).resolve().parent
for n in (6,8):
    folder=ROOT/f'{n}faces'
    board_v=cq.importers.importStep(str(folder/f'pcb_{n}f.step')).val().Volume()
    shapes=cq.importers.importStep(str(folder/f'tunnel_{n}faces.step'))
    renderer=vtk.vtkRenderer()
    renderer.SetBackground(0.96,0.97,0.99)
    for shape in shapes.vals():
        for solid in shape.Solids():
            vertices,triangles=solid.tessellate(0.15)
            pts=vtk.vtkPoints()
            for p in vertices: pts.InsertNextPoint(p.x,p.y,p.z)
            cells=vtk.vtkCellArray()
            for tri in triangles:
                cells.InsertNextCell(3)
                for index in tri: cells.InsertCellPoint(index)
            poly=vtk.vtkPolyData(); poly.SetPoints(pts); poly.SetPolys(cells)
            normals=vtk.vtkPolyDataNormals(); normals.SetInputData(poly); normals.SetFeatureAngle(50)
            mapper=vtk.vtkPolyDataMapper(); mapper.SetInputConnection(normals.GetOutputPort())
            actor=vtk.vtkActor(); actor.SetMapper(mapper)
            volume=solid.Volume()
            color=(0.04,0.35,0.16) if abs(volume-board_v)<0.001 else ((0.7,0.71,0.74) if abs(volume-2513.274122871834)<0.001 else (0.3,0.32,0.36))
            actor.GetProperty().SetColor(*color)
            actor.GetProperty().SetSpecular(0.35)
            actor.GetProperty().SetSpecularPower(35)
            renderer.AddActor(actor)
    camera=renderer.GetActiveCamera(); camera.SetPosition(430,-550,380); camera.SetFocalPoint(0,0,90); camera.SetViewUp(0,0,1)
    window=vtk.vtkRenderWindow(); window.SetOffScreenRendering(1); window.SetSize(1200,1000); window.AddRenderer(renderer)
    renderer.ResetCamera(); camera.Zoom(1.15); window.Render()
    capture=vtk.vtkWindowToImageFilter(); capture.SetInput(window); capture.Update()
    writer=vtk.vtkPNGWriter(); writer.SetFileName(str(folder/f'tunnel_{n}faces_preview.png')); writer.SetInputConnection(capture.GetOutputPort()); writer.Write()
    window.Finalize()
    print(folder/f'tunnel_{n}faces_preview.png')
