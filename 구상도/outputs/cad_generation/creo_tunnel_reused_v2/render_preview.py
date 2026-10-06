from pathlib import Path
import cadquery as cq
import vtk

ROOT=Path(__file__).resolve().parent
for n in (6,8):
    board=cq.importers.importStep(str(ROOT.parent/'creo_tunnel_models'/f'{n}faces'/f'pcb_{n}f.step')).val()
    source=cq.importers.importStep(str(ROOT/'geometry'/f'tunnel_{n}f_v2.step'))
    ren=vtk.vtkRenderer();ren.SetBackground(.96,.97,.99)
    for shape in source.vals():
        for solid in shape.Solids():
            vertices,triangles=solid.tessellate(.15)
            pts=vtk.vtkPoints()
            for p in vertices:pts.InsertNextPoint(p.x,p.y,p.z)
            cells=vtk.vtkCellArray()
            for t in triangles:
                cells.InsertNextCell(3)
                for i in t:cells.InsertCellPoint(i)
            poly=vtk.vtkPolyData();poly.SetPoints(pts);poly.SetPolys(cells)
            normal=vtk.vtkPolyDataNormals();normal.SetInputData(poly);normal.SetFeatureAngle(50)
            mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normal.GetOutputPort())
            actor=vtk.vtkActor();actor.SetMapper(mapper)
            vol=solid.Volume()
            actor.GetProperty().SetColor(*((.04,.35,.16) if abs(vol-board.Volume())<.001 else ((.7,.71,.74) if abs(vol-2513.274122871834)<.001 else (.3,.32,.36))))
            ren.AddActor(actor)
    cam=ren.GetActiveCamera();cam.SetPosition(650,-850,600);cam.SetFocalPoint(0,0,90);cam.SetViewUp(0,0,1)
    win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.SetSize(1200,1000);win.AddRenderer(ren)
    ren.ResetCamera();cam.Zoom(1.12);win.Render()
    capture=vtk.vtkWindowToImageFilter();capture.SetInput(win);capture.Update()
    writer=vtk.vtkPNGWriter();writer.SetFileName(str(ROOT/f'preview_{n}f.png'));writer.SetInputConnection(capture.GetOutputPort());writer.Write();win.Finalize()
    print(f'preview_{n}f.png')
