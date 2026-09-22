import pyvista as pv
import vtk

plotter = pv.Plotter()
mesh = pv.Sphere(radius=10, center=(0,0,0))
actor = plotter.add_mesh(mesh, color='green')

def callback(transform):
    # transform is a vtkTransform
    print("Transformed:", transform.GetPosition())

# Wait, PyVista does not have a native "add_transform_widget" attached to an actor.
# Let's try raw VTK.
transform_widget = vtk.vtkTransformWidget()
transform_widget.SetInteractor(plotter.interactor)
# We need to give it a Prop3D
transform_widget.SetProp3D(actor)
transform_widget.SetPlaceFactor(1.25)
transform_widget.PlaceWidget()
transform_widget.On()

plotter.show()
