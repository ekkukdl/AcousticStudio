"""Main-thread VTK adapter; simplified PCB/ring preview uses CAD dimensions."""
import numpy as np
import pyvista as pv
import vtk


def transducer_inputs(actors):
    """CAD model owns emitting coordinates; old projects retain their adapter."""
    positions, amplitudes = [], []
    for actor in actors:
        element = getattr(actor, '_geometry_element', None)
        positions.append(element['position_mm'] if element is not None else actor.center)
        gain = element['amplitude'] if element is not None else getattr(actor, '_amplitude', 1.)
        enabled = (element.get('enabled', True) if element is not None else True) and getattr(actor, '_enabled', True)
        amplitudes.append(gain if enabled else 0.)
    return np.asarray(positions, dtype=float).reshape(-1, 3), np.asarray(amplitudes, dtype=float)


def transducer_acoustic_inputs(actors):
    """Use CAD normals or the legacy actor's actual local +Z orientation."""
    normals, radii = [], []
    for actor in actors:
        element = getattr(actor, '_geometry_element', None)
        if element is not None:
            normals.append(element['normal'])
            radii.append(element.get('effective_aperture_radius_mm'))
        else:
            matrix = actor.GetMatrix() if hasattr(actor, 'GetMatrix') else None
            normals.append([matrix.GetElement(row, 2) for row in range(3)] if matrix else [0., 0., 1.])
            radii.append(getattr(actor, '_effective_aperture_radius_mm', None))
    return np.asarray(normals, dtype=float).reshape(-1, 3), radii


def vtk_matrix(values):
    matrix = vtk.vtkMatrix4x4()
    matrix.DeepCopy(np.asarray(values, dtype=float).ravel())
    return matrix


def frame_ring_mesh(frame):
    angles = np.pi / 8 + np.arange(8) * np.pi / 4
    outer = frame['outer_apothem_mm'] / np.cos(np.pi / 8)
    inner = frame['inner_apothem_mm'] / np.cos(np.pi / 8)
    points = [[radius * np.cos(angle), radius * np.sin(angle), z]
              for z in (0., frame['ring_height_mm']) for radius in (outer, inner) for angle in angles]
    faces = []
    for index in range(8):
        nxt = (index + 1) % 8
        for quad in ([index, nxt, nxt + 16, index + 16],
                     [index + 8, index + 24, nxt + 24, nxt + 8],
                     [index, index + 8, nxt + 8, nxt],
                     [index + 16, nxt + 16, nxt + 24, index + 24]):
            faces.extend([4, *quad])
    return pv.PolyData(points, faces)


def create_geometry_actors(geometry, renderer):
    parameters = geometry['parameters']
    height = parameters['transducer_height_mm']
    body = pv.Cylinder(center=(0, 0, -height / 2), direction=(0, 0, 1),
                       radius=parameters['transducer_diameter_mm'] / 2, height=height, resolution=24)
    mapper = pv.DataSetMapper(body)
    actors = []
    for element in geometry['elements']:
        actor = pv.Actor(mapper=mapper)
        actor.SetUserMatrix(vtk_matrix(element['matrix']))
        actor._initial_matrix = vtk_matrix(element['matrix'])
        actor._geometry_instance = geometry['instance_id']
        actor._geometry_element = element
        actor._amplitude = element['amplitude']
        actor._original_color = pv.Color('orange').float_rgb
        actor.prop.color = actor._original_color
        renderer.AddActor(actor)
        actors.append(actor)
    pcb = pv.Box(bounds=(0, parameters['board_width_mm'], 0, parameters['board_length_mm'],
                         0, parameters['board_thickness_mm']))
    support_mappers = {'pcb': pv.DataSetMapper(pcb), 'ring': pv.DataSetMapper(frame_ring_mesh(geometry['frame']))}
    support_actors = []
    for support in geometry['supports']:
        actor = pv.Actor(mapper=support_mappers[support['kind']])
        actor.SetUserMatrix(vtk_matrix(support['matrix']))
        actor._initial_matrix = vtk_matrix(support['matrix'])
        actor._geometry_instance = geometry['instance_id']
        actor._geometry_support = support
        actor.prop.color = 'seagreen' if support['kind'] == 'pcb' else 'silver'
        actor.prop.opacity = 0.25
        actor.SetPickable(False)
        renderer.AddActor(actor)
        support_actors.append(actor)
    return actors, support_actors
