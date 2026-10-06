"""Render actual STEP meshes with VTK depth buffering, project-local Python."""
from pathlib import Path
import json,numpy as np,cadquery as cq,vtk
from vtk.util.numpy_support import numpy_to_vtk
r=Path(__file__).resolve().parents[1];d=r/'outputs/panel_8faces_32ch_R1/mechanical/creo32_R1';data=json.loads((d/'geometry_checks.json').read_text())
colors={'pcb32_r1':(.07,.4,.25),'tx16_r1':(.68,.72,.76),'r0805_r1':(.15,.16,.18),'c0805_r1':(.66,.48,.26),'so16_r1':(.12,.13,.15),'so8_r1':(.12,.13,.15),'sot23_r1':(.12,.13,.15),'cp63_r1':(.17,.25,.39),'hdr10_r1':(.15,.16,.18),'hdr3_r1':(.15,.16,.18)}
meshes={}
for p in data['parts']:
 name=p['name'];s=cq.importers.importStep(str(d/'geometry'/(name+'.step'))).val();v,f=s.tessellate(.3,.4);meshes[name]=(np.array([a.toTuple() for a in v]),f)
def items(renderer,face=None,upright=False):
 for p in data['panel_components']:
  v,f=meshes[p['model']];m=np.array(p['matrix']);pts=v@m[:3,:3]+m[3,:3]
  if face is not None:
   q=np.array(face);pts=pts@q[:3,:3]+q[3,:3]
  if upright:pts=np.column_stack((pts[:,0],-pts[:,2],pts[:,1]))
  points=vtk.vtkPoints();points.SetData(numpy_to_vtk(pts,deep=True));cells=vtk.vtkCellArray()
  for tri in f:
   cells.InsertNextCell(3)
   for idx in tri:cells.InsertCellPoint(int(idx))
  poly=vtk.vtkPolyData();poly.SetPoints(points);poly.SetPolys(cells)
  normals=vtk.vtkPolyDataNormals();normals.SetInputData(poly);normals.SetFeatureAngle(35)
  mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
  actor=vtk.vtkActor();actor.SetMapper(mapper);actor.GetProperty().SetColor(*colors[p['model']]);actor.GetProperty().SetAmbient(.35);actor.GetProperty().SetDiffuse(.65);renderer.AddActor(actor)
def text(renderer,value,x,y,size=22):
 actor=vtk.vtkTextActor();actor.SetInput(value);actor.SetDisplayPosition(x,y);actor.GetTextProperty().SetFontSize(size);actor.GetTextProperty().SetColor(.15,.17,.2);renderer.AddViewProp(actor)
def save(window,name):
 window.Render();im=vtk.vtkWindowToImageFilter();im.SetInput(window);im.ReadFrontBufferOff();im.Update();writer=vtk.vtkPNGWriter();writer.SetFileName(str(d/name));writer.SetInputConnection(im.GetOutputPort());writer.Write();window.Finalize()
window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.SetSize(2000,1500);window.SetMultiSamples(4)
for idx,(title,position) in enumerate([('Emitting side: 32 transducers',(150,260,160)),('Outside: drivers and connectors',(-65,-250,160))]):
 renderer=vtk.vtkRenderer();renderer.SetViewport(idx*.5,0,(idx+1)*.5,1);renderer.SetBackground(1,1,1);window.AddRenderer(renderer);items(renderer,upright=True)
 camera=renderer.GetActiveCamera();camera.SetFocalPoint(42,0,112);camera.SetPosition(*position);camera.SetViewUp(0,0,1);camera.ParallelProjectionOn();camera.SetParallelScale(142);renderer.ResetCameraClippingRange()
 text(renderer,title,idx*1000+45,1390,24);text(renderer,'84 x 224 x 1.6 mm | approximate component bodies',idx*1000+45,1350,18)
save(window,'panel32_model_preview.png')
window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.SetSize(1800,1800);window.SetMultiSamples(4);renderer=vtk.vtkRenderer();renderer.SetBackground(1,1,1);window.AddRenderer(renderer)
for face in data['face_matrices']:items(renderer,face=face)
camera=renderer.GetActiveCamera();camera.SetFocalPoint(0,0,0);camera.SetPosition(400,-550,420);camera.SetViewUp(0,0,1);camera.ParallelProjectionOn();camera.SetParallelScale(210);renderer.ResetCameraClippingRange()
text(renderer,'8 panels / 256 transducers | 210 mm emitting-plane separation',65,1700,28);text(renderer,'Exact PCB outline / hole positions; approximate component bodies. External frame omitted.',65,1650,22)
save(window,'tunnel8_model_preview.png');print('Rendered STEP body meshes with correct depth buffering.')
