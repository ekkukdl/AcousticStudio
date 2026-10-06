"""CAD coordinates, VTK adapter and actual state/Undo handlers, without serial."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np
import pyvista as pv
import pytest
import vtk
from PySide6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QLabel, QListWidget, QSpinBox

from acousticstudio.app import AcousticStudioMain
from acousticstudio import file_io
from acousticstudio.geometry import CREO_PRESET_LABEL, SOURCE_DIR, load_creo_tunnel, transform_geometry, validate_geometry
from acousticstudio.geometry_scene import create_geometry_actors, transducer_inputs
from acousticstudio.hardware import HardwareController
from acousticstudio.state_manager import StateManager


def test_existing_json_matches_all_native_creo_emitting_faces_and_normals():
    geometry = load_creo_tunnel()
    source = json.loads((SOURCE_DIR / 'array_positions_256.json').read_text(encoding='utf-8'))
    assembly = json.loads((SOURCE_DIR / 'mechanical/creo32_frame_R2/geometry_checks.json').read_text(encoding='utf-8'))
    components = {component['reference']: np.asarray(component['matrix']) for component in assembly['panel_components']}
    assert len(geometry['elements']) == 256 and len({element['face'] for element in geometry['elements']}) == 8
    assert len({element['id'] for element in geometry['elements']}) == 256
    for element, original in zip(geometry['elements'], source['elements']):
        face = np.asarray(assembly['face_matrices'][element['face']])
        emitting_point = np.array([0., 0., -12.5, 1.]) @ components[element['reference']] @ face
        np.testing.assert_allclose(element['position_mm'], original['position_mm'], atol=1e-12)
        np.testing.assert_allclose(element['position_mm'], emitting_point[:3], atol=1e-12)
        np.testing.assert_allclose(element['normal'], np.array([0., 0., -1.]) @ face[:3, :3], atol=1e-12)
    np.testing.assert_allclose([element['position_mm'][1] for element in geometry['elements'][:4]], [-29., -11., 11., 29.])
    np.testing.assert_allclose([geometry['elements'][row * 4]['position_mm'][2] for row in range(8)], np.arange(-70., 71., 20.))
    for entry in geometry['sources']:
        assert sha256((SOURCE_DIR / entry['path']).read_bytes()).hexdigest() == entry['sha256']


def test_loader_does_not_depend_on_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert len(load_creo_tunnel()['elements']) == 256


def test_whole_layout_transform_preserves_ids_and_transforms_normals_and_structures():
    original = load_creo_tunnel()
    pose = np.array([[0., -1., 0., 10.], [1., 0., 0., 20.], [0., 0., 1., 30.], [0., 0., 0., 1.]])
    transformed = transform_geometry(original, pose)
    np.testing.assert_allclose(transformed['elements'][0]['position_mm'], [39., 125., -40.])
    np.testing.assert_allclose(transformed['elements'][0]['normal'], [0., -1., 0.], atol=1e-12)
    assert [e['id'] for e in transformed['elements']] == [e['id'] for e in original['elements']]
    for before, after in zip(original['supports'], transformed['supports']):
        np.testing.assert_allclose(after['matrix'], pose @ before['matrix'])
    assert original['elements'][0]['position_mm'] == [105., -29., -70.]


@pytest.mark.parametrize('pose', [np.diag([2., 1., 1., 1.]), np.diag([-1., 1., 1., 1.]), np.full((4, 4), np.nan)])
def test_cad_preset_rejects_scaling_reflection_and_nonfinite_pose(pose):
    with pytest.raises(ValueError):
        transform_geometry(load_creo_tunnel(), pose)


@pytest.mark.parametrize('field,value', [('position_mm', [0., 0., 0.]), ('normal', [0., 0., 1.]), ('channel', 1)])
def test_inconsistent_saved_geometry_is_rejected(field, value):
    geometry = load_creo_tunnel()
    geometry['elements'][0][field] = value
    with pytest.raises(ValueError):
        validate_geometry(geometry)


@pytest.mark.parametrize('channel', [0, 64, 128])
def test_vtk_body_and_emitting_face_are_distinct_and_match_cad(channel):
    geometry = load_creo_tunnel()
    renderer = vtk.vtkRenderer()
    actors, supports = create_geometry_actors(geometry, renderer)
    positions, weights = transducer_inputs(actors)
    element = geometry['elements'][channel]
    actor = actors[channel]
    np.testing.assert_allclose(positions[channel], element['position_mm'])
    np.testing.assert_allclose(actor.GetUserMatrix().MultiplyPoint([0., 0., 0., 1.])[:3], positions[channel])
    np.testing.assert_allclose(actor.center, positions[channel] - 6.25 * np.asarray(element['normal']), atol=1e-10)
    assert weights.shape == (256,) and len(supports) == 10
    # Row-vector CAD matrices must be transposed exactly once.
    np.testing.assert_allclose(supports[0].bounds, [117.5, 119.1, -42., 42., -112., 112.], atol=1e-9)
    np.testing.assert_allclose(supports[-1].bounds[-2:], [97., 105.], atol=1e-9)


@pytest.fixture
def window():
    qt_app = QApplication.instance() or QApplication([])
    renderer = vtk.vtkRenderer()

    def add_mesh(mesh, color='orange', **kwargs):
        actor = pv.Actor(mapper=pv.DataSetMapper(mesh))
        actor.prop.color = color
        renderer.AddActor(actor)
        return actor

    messages = []
    view = SimpleNamespace(renderer=renderer, render=lambda: None, reset_camera=lambda: None,
                           remove_actor=lambda actor, **kwargs: renderer.RemoveActor(actor), add_mesh=add_mesh)
    result = SimpleNamespace(plotter=view, transducer_actors=[], control_points=[], selected_actors=[],
                             geometry_arrays=[], geometry_support_actors=[], points_list=QListWidget(),
                             hw_controller=HardwareController(), state_mgr=StateManager(),
                             update_gizmo=lambda: None, update_ui_from_selection=lambda: None,
                             simulate_colors=lambda: None, show_silent_msg=lambda *args: messages.append(args),
                             _is_updating_ui=False, _sel_base_centroid=[0., 0., 0.], _sel_base_rot=[0., 0., 0.])
    for name, entries in (
        ('array_type_cb', ['NxM Matrix (평면)', '튜브형 (Tube)', CREO_PRESET_LABEL]),
        ('transducer_type_cb', ['일반 초음파 (10mm)', '일반 초음파 (16mm)']),
        ('trap_type_cb', ['Twin Trap', 'Vortex Trap']),
    ):
        widget = QComboBox(); widget.addItems(entries); setattr(result, name, widget)
    for name in ('grid_x_spin', 'grid_y_spin'):
        widget = QSpinBox(); widget.setRange(1, 100); widget.setValue(16); setattr(result, name, widget)
    for name in ('spacing_spin', 'point_size_spin', 'prop_radius_spin', 'gen_pos_x', 'gen_pos_y', 'gen_pos_z',
                 'gen_rot_x', 'gen_rot_y', 'gen_rot_z', 'sel_x', 'sel_y', 'sel_z', 'sel_rx', 'sel_ry', 'sel_rz'):
        widget = QDoubleSpinBox(); widget.setRange(-1000, 1000); setattr(result, name, widget)
    result.spacing_spin.setValue(10.5)
    result.array_preset_info = QLabel()
    for name in ('get_state', 'set_state', 'push_state', 'undo', 'redo', 'generate_array', 'generate_creo_tunnel',
                 'update_array_preset_controls', '_clear_geometry_supports', '_sync_cad_geometry',
                 'make_truncated_cone', 'make_langevin_mesh', 'clear_view', 'delete_selected_objects', 'apply_ui_transform'):
        setattr(result, name, MethodType(getattr(AcousticStudioMain, name), result))
    result._messages = messages
    yield result
    renderer.RemoveAllViewProps()
    qt_app.processEvents()


def add_preset(window):
    window.array_type_cb.setCurrentText(CREO_PRESET_LABEL)
    window.update_array_preset_controls()
    window.generate_array()
    assert not window._messages
    assert len(window.transducer_actors) == 256 and len(window.geometry_support_actors) == 10


def test_preset_ignores_generic_grid_spacing_and_preserves_existing_tube(window):
    window.grid_x_spin.setValue(3); window.grid_y_spin.setValue(2); window.spacing_spin.setValue(99.)
    add_preset(window)
    assert not window.spacing_spin.isEnabled() and not window.transducer_type_cb.isEnabled()
    np.testing.assert_allclose(transducer_inputs(window.transducer_actors)[0][0], [105., -29., -70.])
    window.array_type_cb.setCurrentText('튜브형 (Tube)'); window.update_array_preset_controls()
    assert window.spacing_spin.isEnabled()
    window.generate_array()
    assert len(window.transducer_actors) == 262


def test_actual_generation_applies_whole_rotation_and_translation(window):
    window.gen_rot_z.setValue(90.); window.gen_pos_x.setValue(10.); window.gen_pos_y.setValue(20.); window.gen_pos_z.setValue(30.)
    add_preset(window)
    np.testing.assert_allclose(transducer_inputs(window.transducer_actors)[0][0], [39., 125., -40.])
    np.testing.assert_allclose(window.geometry_arrays[0]['elements'][0]['normal'], [0., -1., 0.], atol=1e-12)


def test_model_save_restore_undo_redo_and_clear_keep_geometry_identity(window, tmp_path):
    window.push_state()
    add_preset(window)
    window.push_state()
    original = window.get_state()
    window.selected_actors = list(window.transducer_actors)
    window.sel_x.setValue(10.); window.sel_y.setValue(20.); window.sel_z.setValue(30.); window.sel_rz.setValue(90.)
    window.apply_ui_transform()
    window.push_state()
    moved = window.get_state()
    np.testing.assert_allclose(moved['geometry_arrays'][0]['elements'][0]['position_mm'], [39., 125., -40.])
    assert original['geometry_arrays'][0]['elements'][0]['position_mm'] == [105., -29., -70.]
    window.undo()
    assert window.get_state() == original
    window.redo()
    assert window.get_state() == moved
    saved = window.get_state(for_file=True)
    path = tmp_path / 'project.json'
    file_io.save_project(path, saved)
    window.clear_view()
    assert window.geometry_arrays == [] and window.geometry_support_actors == []
    window.set_state(file_io.load_project(path))
    assert window.get_state(for_file=True) == saved
    assert len(window.transducer_actors) == 256 and len(window.geometry_support_actors) == 10


def test_saved_snapshot_restores_without_source_and_rejects_bad_channel_order(window, monkeypatch):
    add_preset(window)
    state = window.get_state()
    monkeypatch.setattr('acousticstudio.geometry.SOURCE_DIR', Path('missing_source'))
    window.clear_view()
    window.set_state(state)
    bad = deepcopy(state)
    bad['transducers'][0], bad['transducers'][1] = bad['transducers'][1], bad['transducers'][0]
    with pytest.raises(ValueError, match='채널 순서'):
        window.set_state(bad)
    assert window.get_state() == state


def test_deleting_one_selected_cad_transducer_removes_whole_assembly(window):
    add_preset(window)
    window.selected_actors = [window.transducer_actors[10]]
    window.delete_selected_objects()
    assert window.transducer_actors == [] and window.geometry_arrays == [] and window.geometry_support_actors == []


def test_previous_project_transducer_matrices_still_load(window):
    legacy = json.loads((SOURCE_DIR.parents[2] / 'test1.json').read_text(encoding='utf-8'))
    allowed = {'transducer_type', 'array_type', 'spacing', 'trap_type', 'grid_x', 'grid_y', 'point_size', 'prop_radius', 'transducers', 'control_points'}
    state = {key: value for key, value in legacy.items() if key in allowed}
    window.set_state(state)
    assert len(window.transducer_actors) == len(state['transducers'])
    assert window.geometry_arrays == []
    for actor, tx in zip(window.transducer_actors, state['transducers']):
        np.testing.assert_allclose([actor.GetUserMatrix().GetElement(row, col) for row in range(4) for col in range(4)], tx['matrix'])


def test_acoustic_settings_persist_with_cad_undo_redo_and_old_project_defaults(window):
    from acousticstudio.acoustic_model_ui import AcousticModelControls
    window.acoustic_model_controls = AcousticModelControls(lambda *_: None)
    add_preset(window)
    before = window.get_state()
    window.push_state()
    window.acoustic_model_controls.model.setCurrentIndex(1)
    window.acoustic_model_controls.radius.setValue(4.5)
    window.acoustic_model_controls.frequency.setValue(39500.)
    window.acoustic_model_controls.speed.setValue(340.)
    window.push_state()
    after = window.get_state()
    window.undo()
    assert window.get_state() == before
    window.redo()
    assert window.get_state() == after
    old = deepcopy(before)
    old.pop('acoustic_model')
    window.set_state(old)
    assert window.acoustic_model_controls.config().model == 'point_source'
    assert window.acoustic_model_controls.config().aperture_radius_mm is None


def test_invalid_saved_acoustic_model_does_not_modify_scene_or_block_controls(window):
    from acousticstudio.acoustic_model_ui import AcousticModelControls
    window.acoustic_model_controls = AcousticModelControls(lambda *_: None)
    add_preset(window)
    before = window.get_state()
    for key, value in [('sound_speed_m_s', -1.), ('model', 'bad'), ('frequency_hz', 2e6)]:
        corrupted = deepcopy(before)
        corrupted['acoustic_model'][key] = value
        with pytest.raises(ValueError):
            window.set_state(corrupted)
        assert window.get_state() == before
        assert not window.trap_type_cb.signalsBlocked()


def test_force_settings_persist_undo_redo_and_reject_corrupt_particle_before_scene_change(window):
    from acousticstudio.force_analysis import AnalysisSettings
    window.force_analysis_settings = AnalysisSettings().to_dict()
    add_preset(window)
    before = window.get_state()
    window.push_state()
    window.force_analysis_settings['particle']['radius_mm'] = .3
    window.force_analysis_settings['particle']['source'] = 'synthetic fixture'
    window.push_state()
    after = window.get_state()
    window.undo()
    assert window.get_state() == before
    window.redo()
    assert window.get_state() == after
    corrupted = deepcopy(after)
    corrupted['force_analysis_settings']['particle']['radius_mm'] = -1.
    with pytest.raises(ValueError):
        window.set_state(corrupted)
    assert window.get_state() == after
    old = deepcopy(before)
    old.pop('force_analysis_settings')
    window.set_state(old)
    assert window.force_analysis_settings == AnalysisSettings().to_dict()
