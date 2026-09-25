# -*- coding: utf-8 -*-
import sys
import os
os.environ["QT_API"] = "pyside6"
import numpy as np
import numba
@numba.njit(parallel=True)
def calculate_field_slice_numba(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k):
    num_pts = len(pts_x)
    num_tx = len(tx_x)
    real_out = np.zeros(num_pts, dtype=np.float64)
    imag_out = np.zeros(num_pts, dtype=np.float64)
    for p in numba.prange(num_pts):
        px, py, pz = pts_x[p], pts_y[p], pts_z[p]
        r_sum, i_sum = 0.0, 0.0
        for t in range(num_tx):
            dx = px - tx_x[t]
            dy = py - tx_y[t]
            dz = pz - tx_z[t]
            dist = np.sqrt(dx*dx + dy*dy + dz*dz)
            if dist < 1e-3: dist = 1e-3
            amp = tx_amplitudes[t] / dist
            phase = k * dist + tx_phases[t]
            r_sum += amp * np.cos(phase)
            i_sum += amp * np.sin(phase)
        real_out[p] = r_sum
        imag_out[p] = i_sum
    return real_out, imag_out
import pyvista as pv
import vtk
vtk.vtkObject.GlobalWarningDisplayOff() # VTK쓽 遺덊븘슂븳 궡遺 뿉윭(vtkVectorText 벑) 異쒕젰 諛⑹
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import (QApplication, QSplitter, QMainWindow, QWidget, QVBoxLayout, 
                                     QHBoxLayout, QPushButton, QLabel, 
                                     QDoubleSpinBox, QSpinBox, QComboBox, QGroupBox, 
                                     QListWidget, QAbstractItemView, QRubberBand, QSlider, QCheckBox,
                                     QScrollArea, QFormLayout, QListWidgetItem, QMessageBox)
from PySide6.QtCore import Qt, QObject, QEvent, QRect
class MouseEventFilter(QObject):
    def __init__(self, main_window):
        super().__init__()
        
        
        self.main = main_window
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self.main.plotter.interactor)
        self.origin = None
        self.right_dragging = False
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            scale = self.main.plotter.interactor.devicePixelRatioF()
            pos = event.position().toPoint()
            scaled_x = int(round(pos.x() * scale))
            scaled_y = int(round(pos.y() * scale))
            vtk_y = self.main.plotter.window_size[1] - scaled_y - 1
            if event.button() == Qt.LeftButton:
                if hasattr(self.main, 'gizmo_actors') and self.main.gizmo_actors:
                    import vtk
                    prop_picker = vtk.vtkPropPicker()
                    renderer = self.main.plotter.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    
                    # 1. First Pass: Gizmo Only
                    other_actors = getattr(self.main, 'transducer_actors', []) + [p["actor"] for p in getattr(self.main, 'control_points', [])]
                    for a in other_actors:
                        if hasattr(a, 'SetPickable'): a.SetPickable(False)
                        
                    prop_picker.Pick(scaled_x, vtk_y, 0, renderer)
                    act = prop_picker.GetActor()
                    
                    gizmo_clicked = None
                    if act is not None:
                        act_addr = act.GetAddressAsString("vtkProp")
                        for axis, g_act in self.main.gizmo_actors.items():
                            if g_act.GetAddressAsString("vtkProp") == act_addr and g_act.GetVisibility():
                                gizmo_clicked = axis
                                break
                                
                    # Restore pickability
                    for a in other_actors:
                        if hasattr(a, 'SetPickable'): a.SetPickable(True)
                            
                    if gizmo_clicked:
                        self.main.active_gizmo_axis = gizmo_clicked
                        self.main.gizmo_start_pos = pos
                        self.main.gizmo_start_values = (self.main.sel_x.value(), self.main.sel_y.value(), self.main.sel_z.value())
                        for a, g in self.main.gizmo_actors.items():
                            g.prop.color = "yellow" if a == gizmo_clicked else {'x':'red','y':'green','z':'blue','center':'white'}.get(a, 'white')
                        self.main.plotter.render()
                        return True
                self.origin = pos
                self.rubber_band.setGeometry(self.origin.x(), self.origin.y(), 0, 0)
                self.rubber_band.show()
                return True
                
            elif event.button() == Qt.RightButton:
                self.right_dragging = True
                iren = self.main.plotter.interactor
                iren.SetEventPosition(scaled_x, vtk_y)
                style = iren.GetInteractorStyle()
                if hasattr(style, 'OnLeftButtonDown'):
                    style.OnLeftButtonDown()
                return True
                
        elif event.type() == QEvent.MouseMove:
            scale = self.main.plotter.interactor.devicePixelRatioF()
            pos = event.position().toPoint()
            scaled_x = int(round(pos.x() * scale))
            scaled_y = int(round(pos.y() * scale))
            vtk_y = self.main.plotter.window_size[1] - scaled_y - 1
            
            # --- Hover Logic ---
            if event.buttons() == Qt.NoButton and hasattr(self.main, 'gizmo_actors') and self.main.gizmo_actors:
                import vtk
                prop_picker = vtk.vtkPropPicker()
                renderer = self.main.plotter.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                
                other_actors = getattr(self.main, 'transducer_actors', []) + [p["actor"] for p in getattr(self.main, 'control_points', [])]
                for a in other_actors:
                    if hasattr(a, 'SetPickable'): a.SetPickable(False)
                    
                prop_picker.Pick(scaled_x, vtk_y, 0, renderer)
                act = prop_picker.GetActor()
                
                hovered_axis = None
                if act is not None:
                    act_addr = act.GetAddressAsString("vtkProp")
                    for axis, g_act in self.main.gizmo_actors.items():
                        if g_act.GetAddressAsString("vtkProp") == act_addr and g_act.GetVisibility():
                            hovered_axis = axis
                            break
                            
                for a in other_actors:
                    if hasattr(a, 'SetPickable'): a.SetPickable(True)
                    
                # Second pass: pick others if no gizmo
                hovered_obj = None
                if hovered_axis is None:
                    prop_picker.Pick(scaled_x, vtk_y, 0, renderer)
                    act2 = prop_picker.GetActor()
                    if act2 is not None:
                        act2_addr = act2.GetAddressAsString("vtkProp")
                        for t in getattr(self.main, 'transducer_actors', []):
                            if t.GetAddressAsString("vtkProp") == act2_addr:
                                hovered_obj = t
                                break
                        if hovered_obj is None:
                            for p in getattr(self.main, 'control_points', []):
                                if p["actor"].GetAddressAsString("vtkProp") == act2_addr:
                                    hovered_obj = p["actor"]
                                    break
                                    
                base_colors = {'x':'red', 'y':'green', 'z':'blue', 'center':'white'}
                hover_colors = {'x':'#FF6666', 'y':'#66FF66', 'z':'#6666FF', 'center':'yellow'}
                
                needs_render = False
                for a, g in self.main.gizmo_actors.items():
                    target_color = hover_colors.get(a, base_colors.get(a, 'white')) if a == hovered_axis else base_colors.get(a, 'white')
                    if getattr(g, '_current_color', None) != target_color:
                        g.prop.color = target_color
                        g._current_color = target_color
                        needs_render = True
                        
                for t in other_actors:
                    if hasattr(t, 'prop'):
                        is_selected = (t in getattr(self.main, 'selected_actors', []))
                        is_hovered = (t == hovered_obj)
                        
                        if is_selected: target_op = 0.5
                        elif is_hovered: target_op = 0.7
                        else: target_op = 1.0
                        
                        if getattr(t, '_current_opacity', 1.0) != target_op:
                            t.prop.opacity = target_op
                            t._current_opacity = target_op
                            needs_render = True
                            
                if needs_render:
                    self.main.plotter.render()
            # -------------------
            
            if getattr(self.main, 'active_gizmo_axis', None) is not None:
                axis = self.main.active_gizmo_axis
                cx, cy, cz = self.main._sel_base_centroid
                renderer = self.main.plotter.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                
                import numpy as np
                
                def get_ray(px, py):
                    renderer.SetDisplayPoint(px, py, 0.0)
                    renderer.DisplayToWorld()
                    wp1 = renderer.GetWorldPoint()
                    p1 = np.array([wp1[0]/wp1[3], wp1[1]/wp1[3], wp1[2]/wp1[3]])
                    renderer.SetDisplayPoint(px, py, 1.0)
                    renderer.DisplayToWorld()
                    wp2 = renderer.GetWorldPoint()
                    p2 = np.array([wp2[0]/wp2[3], wp2[1]/wp2[3], wp2[2]/wp2[3]])
                    d = p2 - p1
                    norm = np.linalg.norm(d)
                    if norm > 0: d = d / norm
                    return p1, d
                    
                ray_p1, ray_dir = get_ray(scaled_x, vtk_y)
                
                scaled_x_start = int(round(self.main.gizmo_start_pos.x() * scale))
                vtk_y_start = self.main.plotter.window_size[1] - int(round(self.main.gizmo_start_pos.y() * scale)) - 1
                s_ray_p1, s_ray_dir = get_ray(scaled_x_start, vtk_y_start)
                
                if axis == 'center':
                    cam = renderer.GetActiveCamera()
                    cam_dir = np.array(cam.GetDirectionOfProjection())
                    
                    denom = np.dot(cam_dir, ray_dir)
                    if abs(denom) > 1e-6:
                        t = np.dot(cam_dir, np.array([cx, cy, cz]) - ray_p1) / denom
                        curr_world = ray_p1 + t * ray_dir
                    else: curr_world = np.array([cx, cy, cz])
                    
                    denom_s = np.dot(cam_dir, s_ray_dir)
                    if abs(denom_s) > 1e-6:
                        t_s = np.dot(cam_dir, np.array([cx, cy, cz]) - s_ray_p1) / denom_s
                        start_world = s_ray_p1 + t_s * s_ray_dir
                    else: start_world = np.array([cx, cy, cz])
                    
                    dx, dy, dz = curr_world - start_world
                    
                    self.main._is_gizmo_dragging = True
                    self.main.sel_x.setValue(self.main.gizmo_start_values[0] + dx)
                    self.main.sel_y.setValue(self.main.gizmo_start_values[1] + dy)
                    self.main.sel_z.setValue(self.main.gizmo_start_values[2] + dz)
                    self.main._is_gizmo_dragging = False
                    
                else:
                    dir_vec = np.array({'x':[1,0,0], 'y':[0,1,0], 'z':[0,0,1]}[axis])
                    center = np.array([cx, cy, cz])
                    
                    def closest_t_on_axis(rp, rd):
                        w0 = rp - center
                        a = np.dot(rd, rd)
                        b = np.dot(rd, dir_vec)
                        c = np.dot(dir_vec, dir_vec)
                        d = np.dot(rd, w0)
                        e = np.dot(dir_vec, w0)
                        denom = a*c - b*b
                        if abs(denom) > 1e-6:
                            return (a*e - b*d) / denom
                        return 0.0
                        
                    t_axis = closest_t_on_axis(ray_p1, ray_dir)
                    t_axis_start = closest_t_on_axis(s_ray_p1, s_ray_dir)
                    
                    delta_world = t_axis - t_axis_start
                    
                    self.main._is_gizmo_dragging = True
                    if axis == 'x': self.main.sel_x.setValue(self.main.gizmo_start_values[0] + delta_world)
                    if axis == 'y': self.main.sel_y.setValue(self.main.gizmo_start_values[1] + delta_world)
                    if axis == 'z': self.main.sel_z.setValue(self.main.gizmo_start_values[2] + delta_world)
                    self.main._is_gizmo_dragging = False
                
                return True
            if self.origin is not None:
                self.rubber_band.setGeometry(QRect(self.origin, pos).normalized())
                return True
                
            elif self.right_dragging:
                iren = self.main.plotter.interactor
                iren.SetEventPosition(int(round(pos.x() * scale)), vtk_y)
                style = iren.GetInteractorStyle()
                if hasattr(style, 'OnMouseMove'):
                    style.OnMouseMove()
                return True
                
        elif event.type() == QEvent.MouseButtonRelease:
            scale = self.main.plotter.interactor.devicePixelRatioF()
            pos = event.position().toPoint()
            scaled_y = int(round(pos.y() * scale))
            vtk_y = self.main.plotter.window_size[1] - scaled_y - 1
            if event.button() == Qt.LeftButton and getattr(self.main, 'active_gizmo_axis', None) is not None:
                self.main.active_gizmo_axis = None
                for a, g in self.main.gizmo_actors.items():
                    g.prop.color = {'x':'red','y':'green','z':'blue','center':'white'}.get(a, 'white')
                if self.main.show_field_btn.isChecked():
                    self.main.update_field_slice()
                self.main.plotter.render()
                return True
            if event.button() == Qt.LeftButton and self.origin is not None:
                self.rubber_band.hide()
                end_pos = pos
                start_pos = self.origin
                self.origin = None 
                try:
                    self.main.process_selection(start_pos, end_pos, event.modifiers())
                except Exception as e:
                    import traceback; traceback.print_exc()
                return True
                
            elif event.button() == Qt.RightButton and self.right_dragging:
                self.right_dragging = False
                iren = self.main.plotter.interactor
                iren.SetEventPosition(int(round(pos.x() * scale)), vtk_y)
                style = iren.GetInteractorStyle()
                if hasattr(style, 'OnLeftButtonUp'):
                    style.OnLeftButtonUp()
                return True
        
        if event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton:
                if hasattr(self.main, 'push_state'):
                    # To avoid spamming, only push if state changed. push_state already checks this.
                    self.main.push_state()
        return False
class WheelBlocker(QObject):
    def __init__(self, scroll_area, main_window=None):
        super().__init__()
        self.scroll_area = scroll_area
        self.main = main_window
    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Wheel:
            from PySide6.QtWidgets import QApplication
            # 뒪겕濡ㅻ컮뿉 씠踰ㅽ듃瑜 吏곸젒 쟾떖븯뿬 뒪겕濡ㅼ씠 릺寃 븿
            QApplication.sendEvent(self.scroll_area.verticalScrollBar(), event)
            return True # SpinBox/ComboBox媛 씠踰ㅽ듃瑜 泥섎━븯吏 紐삵븯寃 셿쟾 李⑤떒
        
        if event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton:
                if getattr(self, 'main', None) and hasattr(self.main, 'push_state'):
                    # To avoid spamming, only push if state changed. push_state already checks this.
                    self.main.push_state()
        return False
class AcousticStudioMain(QMainWindow):
    def __init__(self):
        super().__init__()
        
        
        self.setWindowTitle("Acoustic Control Studio - PyVista 3D Viewer")
        self.resize(1400, 950)
        # File Menu
        from PySide6.QtGui import QAction
        from PySide6.QtCore import Qt
        menubar = self.menuBar()
        file_menu = menubar.addMenu("파일 (File)")
        
        save_action = QAction("저장 (Save)", self)
        save_action.setShortcut("Ctrl+S")
        save_action.setShortcutContext(Qt.ApplicationShortcut)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("다른 이름으로 저장 (Save As...)", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.setShortcutContext(Qt.ApplicationShortcut)
        save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_action)
        
        load_action = QAction("불러오기 (Load)", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self.load_project)
        file_menu.addAction(load_action)
        
        edit_menu = menubar.addMenu("편집 (Edit)")
        
        undo_action = QAction("실행 취소 (Undo)", self)
        undo_action.setShortcut("Ctrl+Z")
        from PySide6.QtCore import Qt
        undo_action.setShortcutContext(Qt.ApplicationShortcut)
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("다시 실행 (Redo)", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.setShortcutContext(Qt.ApplicationShortcut)
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)
        tools_menu = self.menuBar().addMenu("도구(Tools)")
        lib_mgr_action = tools_menu.addAction("라이브러리 관리자 (Library Manager)")
        lib_mgr_action.triggered.connect(self.open_library_manager)

        
        # Initialize undo stack
        self.push_state()
        self._initial_state = self.get_state()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        self.view_panel = QWidget()
        self.view_panel.setMinimumWidth(50)
        view_layout = QVBoxLayout(self.view_panel)
        view_layout.setContentsMargins(0, 0, 0, 0)
        
        self.plotter = QtInteractor(self.view_panel)
        self.plotter.interactor.setMinimumWidth(50)
        view_layout.addWidget(self.plotter.interactor)
        
        self.plotter.set_background("#2b2b2b")
        
        self.plotter.add_axes()
        
        # 3D Gizmo Initialization
        import pyvista as pv
        self.gizmo_actors = {}
        d = 1.0
        for axis, color, dir_vec in [('x', 'red', (1,0,0)), ('y', 'green', (0,1,0)), ('z', 'blue', (0,0,1))]:
            mesh = pv.Cylinder(center=(d/2*dir_vec[0], d/2*dir_vec[1], d/2*dir_vec[2]), direction=dir_vec, radius=d*0.015, height=d).merge(
                   pv.Sphere(center=(d*dir_vec[0], d*dir_vec[1], d*dir_vec[2]), radius=d*0.06))
            act = self.plotter.add_mesh(mesh, color=color, lighting=True)
            act.SetPickable(True)
            act.SetVisibility(False)
            self.gizmo_actors[axis] = act
            
        center_mesh = pv.Sphere(center=(0,0,0), radius=d*0.06)
        c_act = self.plotter.add_mesh(center_mesh, color='white', lighting=True)
        c_act.SetPickable(True)
        c_act.SetVisibility(False)
        self.gizmo_actors['center'] = c_act
            
        self.active_gizmo_axis = None
        self.gizmo_start_pos = None
        self.gizmo_start_values = None
        
        self.plotter.disable_depth_peeling()
        
        # ??占쏙옙 ??(Del) 諛붿씤??        
        self.plotter.add_key_event('Delete', self.delete_selected_objects)
        
        self.transducer_actors = []
        self.control_points = []
        self.selected_actors = []
        self.selected_point_index = -1
        
        self.area_picker = vtk.vtkAreaPicker()
        self.mouse_filter = MouseEventFilter(self)
        self.plotter.interactor.installEventFilter(self.mouse_filter)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(128, 128, 128, 150);
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        
        control_panel = QWidget()
        control_panel.setMinimumWidth(380)
        control_layout = QVBoxLayout(control_panel)
        from PySide6.QtCore import Qt
        control_layout.setAlignment(Qt.AlignTop)
        control_layout.setContentsMargins(5, 10, 15, 10)
        
        
        scroll_area.setWidget(control_panel)
        
        from PySide6.QtWidgets import QSplitter
        from PySide6.QtCore import Qt
        
        # --- Create Left Panel for 3D Viewer & Hardware Control ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Hardware Control (Top Bar)
        hw_top_bar = QWidget()
        hw_top_bar.setMaximumHeight(50)
        hw_layout = QHBoxLayout(hw_top_bar)
        hw_layout.setContentsMargins(10, 5, 10, 5)
        
        import serial.tools.list_ports
        self.serial_port_cb = QComboBox()
        self.btn_refresh_ports = QPushButton("새로고침")
        self.btn_refresh_ports.setFixedWidth(60)
        self.btn_refresh_ports.clicked.connect(self.refresh_ports)
        
        self.serial_baud_cb = QComboBox()
        baud_rates = ["9600", "19200", "38400", "57600", "115200", "230400", "250000", "500000", "1000000"]
        self.serial_baud_cb.addItems(baud_rates)
        self.serial_baud_cb.setCurrentText("115200")
        
        self.btn_connect_hw = QPushButton("Connect (연결)")
        self.btn_send_phase = QPushButton("Send Phase Data")
        self.btn_send_phase.setEnabled(False)
        self.btn_connect_hw.clicked.connect(self.connect_hw)
        self.btn_send_phase.clicked.connect(self.send_phase_data)
        self.refresh_ports()
        
        hw_layout.addWidget(QLabel("하드웨어 제어 (USB Port):"))
        hw_layout.addWidget(self.serial_port_cb)
        hw_layout.addWidget(self.btn_refresh_ports)
        hw_layout.addWidget(QLabel("Baud Rate:"))
        hw_layout.addWidget(self.serial_baud_cb)
        hw_layout.addWidget(self.btn_connect_hw)
        hw_layout.addWidget(self.btn_send_phase)
        
        # Add Compute Mode UI
        try:
            from acousticstudio.sonic_wrapper import is_gpu_available, get_cpu_name, get_gpu_name
            has_gpu = is_gpu_available()
            cpu_name = get_cpu_name()
            gpu_name = get_gpu_name()
        except ImportError:
            has_gpu = False
            cpu_name = "Unknown CPU"
            gpu_name = "Unknown GPU"
            
        import importlib.util
        self.has_taichi = importlib.util.find_spec("taichi") is not None
        self.has_pytorch = importlib.util.find_spec("torch") is not None
            
        self.compute_mode_cb = QComboBox()
        self.compute_mode_cb.setStyleSheet("QComboBox { combobox-popup: 0; }")
        self.compute_mode_cb.addItem(f"CPU: {cpu_name} (보통) (Numba JIT)")
        self.compute_mode_cb.addItem(f"CPU: {cpu_name} (빠름) (C++ 최적화)")
        self.compute_mode_cb.addItem(f"GPU: 범용 그래픽 (매우 빠름) (Taichi 가속)")
        self.compute_mode_cb.addItem(f"GPU: {gpu_name} (가장 빠름) (PyTorch/CUDA 가속)")
        
        if hasattr(self, "update_compute_mode_styles"):
            self.update_compute_mode_styles()
            
        best_idx = 0
        try:
            from acousticstudio.sonic_wrapper import _cpp_lib
            if _cpp_lib is not None: best_idx = 1
        except: pass
        if getattr(self, 'has_taichi', False): best_idx = 2
        if getattr(self, 'has_pytorch', False): best_idx = 3
        self.compute_mode_cb.setCurrentIndex(best_idx)
            
        self.compute_mode_cb.currentIndexChanged.connect(self.on_compute_mode_changed)
            
        hw_layout.addWidget(QLabel(" | 연산 모드:"))
        hw_layout.addWidget(self.compute_mode_cb)
        hw_layout.addStretch()
        
        main_layout.addWidget(hw_top_bar)
        
        # --- Splitter Setup ---
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.view_panel)
        self.splitter.addWidget(scroll_area)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([1020, 380])
        
        main_layout.addWidget(self.splitter)
        
        # [1. Transform Properties (?占쏀깮??媛앹껜 ?占쎈룞/?占쎌쟾)] - ?占쎈줈 異뷂옙???
        transform_group = QGroupBox("1. Selected Object Transform (선택된 객체 이동/회전)")
        transform_group.setStyleSheet("QGroupBox { font-weight: bold; color: #2196F3; }")
        
        
        self.sel_x = QDoubleSpinBox(); self.sel_x.setRange(-2000, 2000)
        self.sel_y = QDoubleSpinBox(); self.sel_y.setRange(-2000, 2000)
        self.sel_z = QDoubleSpinBox(); self.sel_z.setRange(-2000, 2000)
        self.sel_rx = QDoubleSpinBox(); self.sel_rx.setRange(-360, 360)
        self.sel_ry = QDoubleSpinBox(); self.sel_ry.setRange(-360, 360)
        self.sel_rz = QDoubleSpinBox(); self.sel_rz.setRange(-360, 360)
        
        from PySide6.QtWidgets import QGridLayout
        t_layout = QGridLayout()
        t_layout.addWidget(QLabel("이동 (mm):"), 0, 0)
        t_layout.addWidget(QLabel("X:"), 0, 1)
        t_layout.addWidget(self.sel_x, 0, 2)
        t_layout.addWidget(QLabel("Y:"), 0, 3)
        t_layout.addWidget(self.sel_y, 0, 4)
        t_layout.addWidget(QLabel("Z:"), 0, 5)
        t_layout.addWidget(self.sel_z, 0, 6)
        t_layout.addWidget(QLabel("회전 (deg):"), 1, 0)
        t_layout.addWidget(QLabel("Rx:"), 1, 1)
        t_layout.addWidget(self.sel_rx, 1, 2)
        t_layout.addWidget(QLabel("Ry:"), 1, 3)
        t_layout.addWidget(self.sel_ry, 1, 4)
        t_layout.addWidget(QLabel("Rz:"), 1, 5)
        t_layout.addWidget(self.sel_rz, 1, 6)
        t_layout.setColumnStretch(7, 1)
        transform_group.setLayout(t_layout)
        control_layout.addWidget(transform_group)
        # Properties Group
        self.prop_group = QGroupBox("Selected Properties (선택 속성)")
        prop_layout = QFormLayout()
        
        self.prop_type_lbl = QLabel("-")
        self.prop_sensor_cb = QComboBox()
        self.prop_sensor_cb.addItems(["일반 초음파 (10mm)", "일반 초음파 (16mm)", "랑주뱅 진동자 (Langevin)"])
        
        self.prop_radius_spin = QDoubleSpinBox()
        self.prop_radius_spin.setRange(0.1, 100.0)
        self.prop_radius_spin.setSuffix(" mm")
        
        prop_layout.addRow("객체 종류:", self.prop_type_lbl)
        prop_layout.addRow("트랜스듀서 반경:", self.prop_sensor_cb)
        prop_layout.addRow("초점 반경:", self.prop_radius_spin)
        
        self.prop_group.setLayout(prop_layout)
        control_layout.addWidget(self.prop_group)
        self.prop_sensor_cb.currentIndexChanged.connect(self.on_prop_sensor_changed)
        self.prop_radius_spin.valueChanged.connect(self.on_prop_radius_changed)
        
        # UI 媛믪씠 諛뷂옙???3D 媛앹껜??利됱떆 諛섏쁺
        self.sel_x.valueChanged.connect(self.apply_ui_transform)
        self.sel_x.editingFinished.connect(self.push_state)
        self.sel_y.valueChanged.connect(self.apply_ui_transform)
        self.sel_y.editingFinished.connect(self.push_state)
        self.sel_z.valueChanged.connect(self.apply_ui_transform)
        self.sel_z.editingFinished.connect(self.push_state)
        self.sel_rx.valueChanged.connect(self.apply_ui_transform)
        self.sel_rx.editingFinished.connect(self.push_state)
        self.sel_ry.valueChanged.connect(self.apply_ui_transform)
        self.sel_ry.editingFinished.connect(self.push_state)
        self.sel_rz.valueChanged.connect(self.apply_ui_transform)
        self.sel_rz.editingFinished.connect(self.push_state)
        
        # [2. 諛곗뿴 ?占쎌젙 洹몃９]
        array_group = QGroupBox("2. Transducer Array Setup (트랜스듀서 배열 설정)")
        array_layout = QVBoxLayout()
        array_form = QFormLayout()
        
        self.transducer_type_cb = QComboBox()
        self.transducer_type_cb.addItems(["일반 초음파 (10mm)", "일반 초음파 (16mm)", "랑주뱅 진동자 (Langevin)"])
        self.array_type_cb = QComboBox()
        self.array_type_cb.addItems(["NxM Matrix (평면)", "다면체 (상하좌우)", "대향형 (상하)", "반구형 (Hemisphere)", "튜브형 (Tube)"])
        
        self.grid_x_spin = QSpinBox(); self.grid_x_spin.setValue(16); self.grid_x_spin.setRange(1, 100)
        self.grid_y_spin = QSpinBox(); self.grid_y_spin.setValue(16); self.grid_y_spin.setRange(1, 100)
        self.spacing_spin = QDoubleSpinBox(); self.spacing_spin.setValue(10.5); self.spacing_spin.setRange(1.0, 200.0); self.spacing_spin.setDecimals(2)
        # 諛곗뿴 ?占쎌꽦 ???占쎌튂/媛곷룄 吏??        
        self.gen_pos_x = QDoubleSpinBox(); self.gen_pos_x.setRange(-1000, 1000); self.gen_pos_x.setValue(0.0)
        self.gen_pos_y = QDoubleSpinBox(); self.gen_pos_y.setRange(-1000, 1000); self.gen_pos_y.setValue(0.0)
        self.gen_pos_z = QDoubleSpinBox(); self.gen_pos_z.setRange(-1000, 1000); self.gen_pos_z.setValue(0.0)
        
        self.gen_rot_x = QDoubleSpinBox(); self.gen_rot_x.setRange(-360, 360); self.gen_rot_x.setValue(0.0)
        self.gen_rot_y = QDoubleSpinBox(); self.gen_rot_y.setRange(-360, 360); self.gen_rot_y.setValue(0.0)
        self.gen_rot_z = QDoubleSpinBox(); self.gen_rot_z.setRange(-360, 360); self.gen_rot_z.setValue(0.0)
        
        array_form.addRow("트랜스듀서 모델:", self.transducer_type_cb)
        array_form.addRow("배열 형태:", self.array_type_cb)
        
        grid_layout = QHBoxLayout()
        grid_layout.addWidget(self.grid_x_spin)
        grid_layout.addWidget(self.grid_y_spin)
        array_form.addRow("Grid X, Y:", grid_layout)
        
        array_form.addRow("Spacing (간격 mm):", self.spacing_spin)
        array_layout.addLayout(array_form)
        
        def on_transducer_type_changed(t):
            if "10mm" in t: self.spacing_spin.setValue(10.5)
            elif "16mm" in t: self.spacing_spin.setValue(16.5)
            else: self.spacing_spin.setValue(50.0)
        self.transducer_type_cb.currentTextChanged.connect(on_transducer_type_changed)
        gen_grid = QGridLayout()
        gen_grid.addWidget(QLabel("배열 이동 (mm):"), 0, 0)
        gen_grid.addWidget(QLabel("X:"), 0, 1)
        gen_grid.addWidget(self.gen_pos_x, 0, 2)
        gen_grid.addWidget(QLabel("Y:"), 0, 3)
        gen_grid.addWidget(self.gen_pos_y, 0, 4)
        gen_grid.addWidget(QLabel("Z:"), 0, 5)
        gen_grid.addWidget(self.gen_pos_z, 0, 6)
        gen_grid.addWidget(QLabel("배열 회전 (deg):"), 1, 0)
        gen_grid.addWidget(QLabel("Rx:"), 1, 1)
        gen_grid.addWidget(self.gen_rot_x, 1, 2)
        gen_grid.addWidget(QLabel("Ry:"), 1, 3)
        gen_grid.addWidget(self.gen_rot_y, 1, 4)
        gen_grid.addWidget(QLabel("Rz:"), 1, 5)
        gen_grid.addWidget(self.gen_rot_z, 1, 6)
        gen_grid.setColumnStretch(7, 1)
        array_layout.addLayout(gen_grid)
        
        self.add_array_btn = QPushButton("배열 3D 렌더링 생성")
        self.add_array_btn.clicked.connect(self._hooked_generate_array)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._hooked_clear_view)
        
        array_layout.addWidget(self.add_array_btn)
        array_layout.addWidget(self.clear_btn)
        array_group.setLayout(array_layout)
        control_layout.addWidget(array_group)
        
        # [3. 而⑦듃占??占쎌씤??(?占쏙옙? 洹몃９]
        points_group = QGroupBox("3. Control Points (제어점 설정)")
        points_layout = QVBoxLayout()
        
        
        self.point_size_spin = QDoubleSpinBox()
        self.point_size_spin.setRange(0.1, 50.0)
        self.point_size_spin.setValue(5.0)
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("제어점 반경 (mm):"))
        size_layout.addWidget(self.point_size_spin)
        points_layout.addLayout(size_layout)
        
        self.points_list = QListWidget()
        self.points_list.setMinimumHeight(200)
        self.points_list.setMaximumHeight(600)
        self.points_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.points_list.currentRowChanged.connect(self.on_point_selected)
        points_layout.addWidget(self.points_list)
        
        btn_layout = QHBoxLayout()
        self.add_pt_btn = QPushButton("Add Point")
        self.add_pt_btn.clicked.connect(self._hooked_add_control_point)
        self.del_pt_btn = QPushButton("Delete Point")
        self.del_pt_btn.clicked.connect(self._hooked_del_control_point)
        btn_layout.addWidget(self.add_pt_btn)
        btn_layout.addWidget(self.del_pt_btn)
        points_layout.addLayout(btn_layout)
        
        self.auto_calc_cb = QCheckBox("Point 이동 시 실시간 위상 업데이트")
        self.auto_calc_cb.setChecked(True) # 湲곕낯쟻쑝濡 耳쒕몺
        points_layout.addWidget(self.auto_calc_cb)
        
        points_group.setLayout(points_layout)
        control_layout.addWidget(points_group)
        
        # [4. ?占쎈옪 占??占쏙옙??占쎌씠??洹몃９]
        field_group = QGroupBox("4. Phase Simulation (위상 계산)")
        field_layout = QFormLayout()
        self.trap_type_cb = QComboBox()
        self.trap_type_cb.addItems(["Twin Trap", "Vortex Trap"])
        field_layout.addRow("트랩 종류:", self.trap_type_cb)
        
        self.run_btn = QPushButton("Calculate Phase (위상 계산 및 시각화)")
        self.run_btn.setStyleSheet("background-color: #4CAF50; color: white; height: 30px; font-weight: bold;")
        self.run_btn.clicked.connect(self.simulate_colors)
        field_layout.addRow(self.run_btn)
        field_group.setLayout(field_layout)
        control_layout.addWidget(field_group)
        
        # [5. ?占쎌븬 ?占쎄컖??洹몃９]
        visual_group = QGroupBox("5. Acoustic Field Visualization (음압 단면 시각화)")
        visual_layout = QVBoxLayout()
        
        # XZ Plane
        xz_lyt = QHBoxLayout()
        self.xz_check = QCheckBox("XZ (정면)")
        self.xz_check.stateChanged.connect(self.update_field_slice)
        self.xz_slider = QSlider(Qt.Horizontal); self.xz_slider.setRange(-200, 200)
        self.xz_spin = QSpinBox(); self.xz_spin.setRange(-200, 200); self.xz_spin.setFixedWidth(60)
        def on_xz_sl(v): self.xz_spin.blockSignals(True); self.xz_spin.setValue(v); self.xz_spin.blockSignals(False); self.draw_ghost_plane('xz', v); (self.update_field_slice() if not self.xz_slider.isSliderDown() else None)
        def on_xz_sp(v): self.xz_slider.blockSignals(True); self.xz_slider.setValue(v); self.xz_slider.blockSignals(False); self.draw_ghost_plane('xz', v); self.update_field_slice()
        self.xz_slider.valueChanged.connect(on_xz_sl)
        self.xz_slider.sliderReleased.connect(self.update_field_slice)
        self.xz_spin.valueChanged.connect(on_xz_sp)
        xz_lyt.addWidget(self.xz_check); xz_lyt.addWidget(self.xz_slider); xz_lyt.addWidget(self.xz_spin)
        visual_layout.addLayout(xz_lyt)
        
        # YZ Plane
        yz_lyt = QHBoxLayout()
        self.yz_check = QCheckBox("YZ (측면)")
        self.yz_check.stateChanged.connect(self.update_field_slice)
        self.yz_slider = QSlider(Qt.Horizontal); self.yz_slider.setRange(-200, 200)
        self.yz_spin = QSpinBox(); self.yz_spin.setRange(-200, 200); self.yz_spin.setFixedWidth(60)
        def on_yz_sl(v): self.yz_spin.blockSignals(True); self.yz_spin.setValue(v); self.yz_spin.blockSignals(False); self.draw_ghost_plane('yz', v); (self.update_field_slice() if not self.yz_slider.isSliderDown() else None)
        def on_yz_sp(v): self.yz_slider.blockSignals(True); self.yz_slider.setValue(v); self.yz_slider.blockSignals(False); self.draw_ghost_plane('yz', v); self.update_field_slice()
        self.yz_slider.valueChanged.connect(on_yz_sl)
        self.yz_slider.sliderReleased.connect(self.update_field_slice)
        self.yz_spin.valueChanged.connect(on_yz_sp)
        yz_lyt.addWidget(self.yz_check); yz_lyt.addWidget(self.yz_slider); yz_lyt.addWidget(self.yz_spin)
        visual_layout.addLayout(yz_lyt)
        
        # XY Plane
        xy_lyt = QHBoxLayout()
        self.xy_check = QCheckBox("XY (평면)")
        self.xy_check.stateChanged.connect(self.update_field_slice)
        self.xy_slider = QSlider(Qt.Horizontal); self.xy_slider.setRange(-200, 200)
        self.xy_spin = QSpinBox(); self.xy_spin.setRange(-200, 200); self.xy_spin.setFixedWidth(60)
        def on_xy_sl(v): self.xy_spin.blockSignals(True); self.xy_spin.setValue(v); self.xy_spin.blockSignals(False); self.draw_ghost_plane('xy', v); (self.update_field_slice() if not self.xy_slider.isSliderDown() else None)
        def on_xy_sp(v): self.xy_slider.blockSignals(True); self.xy_slider.setValue(v); self.xy_slider.blockSignals(False); self.draw_ghost_plane('xy', v); self.update_field_slice()
        self.xy_slider.valueChanged.connect(on_xy_sl)
        self.xy_slider.sliderReleased.connect(self.update_field_slice)
        self.xy_spin.valueChanged.connect(on_xy_sp)
        xy_lyt.addWidget(self.xy_check); xy_lyt.addWidget(self.xy_slider); xy_lyt.addWidget(self.xy_spin)
        visual_layout.addLayout(xy_lyt)
        
        self.show_field_btn = QPushButton("음압 단면 시각화")
        self.show_field_btn.setStyleSheet("background-color: #2196F3; color: white; height: 30px; font-weight: bold;")
        self.show_field_btn.setCheckable(True)
        self.show_field_btn.clicked.connect(self.toggle_field_slice)
        show_field_lyt = QHBoxLayout()
        show_field_lyt.addWidget(self.show_field_btn)
        self.field_mode_combo = QComboBox()
        self.field_mode_combo.addItems(["음압 분포 (Pressure Magnitude)", "위상 분포 (Phase Angle)"])
        self.field_mode_combo.currentIndexChanged.connect(self.update_field_slice)
        show_field_lyt.addWidget(self.field_mode_combo)
        visual_layout.addLayout(show_field_lyt)
        
        visual_group.setLayout(visual_layout)
        control_layout.addWidget(visual_group)
        control_layout.addStretch(1)
        # Hardware UI moved to top bar
        
        self.field_actors = [] # ?占쎌쨷 ?占쎈씪?占쎌뒪 ?占쏀꽣占?愿由ы븯占??占쏀븳 由ъ뒪??        
        
        self._is_updating_ui = False
        self._sel_base_centroid = [0.0, 0.0, 0.0]
        self._sel_base_rot = [0.0, 0.0, 0.0]
        # Apply wheel blocker AFTER all widgets are created
        self.wheel_blocker = WheelBlocker(scroll_area, self)
        widgets = self.findChildren(QDoubleSpinBox) + self.findChildren(QSpinBox) + self.findChildren(QComboBox)
        for widget in widgets:
            widget.installEventFilter(self.wheel_blocker)
    
    def get_pyvista_actor(self, vtk_prop):
        if vtk_prop is None: return None
        addr = vtk_prop.GetAddressAsString("vtkProp")
        for a in self.transducer_actors:
            if a.GetAddressAsString("vtkProp") == addr: return a
        for a in self.get_control_point_actors():
            if a.GetAddressAsString("vtkProp") == addr: return a
        return None
    def get_control_point_actors(self):
        return [p["actor"] for p in self.control_points]
    def refresh_ports(self):
        import serial.tools.list_ports
        self.serial_port_cb.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Add port device name (e.g., COM3) and display description if needed
            self.serial_port_cb.addItem(p.device, userData=p.device)
        
        if not ports:
            self.serial_port_cb.addItem("No Ports Found")
    def connect_hw(self):
        if not hasattr(self, 'serial_port') or self.serial_port is None:
            port = self.serial_port_cb.currentText()
            if port == "No Ports Found" or not port:
                QMessageBox.critical(self, "Error", "No valid COM port selected.")
                return
            try:
                baud = int(self.serial_baud_cb.currentText())
            except ValueError:
                QMessageBox.critical(self, "Error", "Invalid Baud Rate.")
                return
                
            try:
                import serial
                self.serial_port = serial.Serial(port, baud, timeout=1)
                self.btn_connect_hw.setText("Disconnect (뿰寃 빐젣)")
                self.btn_send_phase.setEnabled(True)
                QMessageBox.information(self, "Hardware", f"Connected to {port} at {baud} baud.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"작업 중 오류가 발생했습니다: {str(e)}")
        else:
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None
            self.btn_connect_hw.setText("Connect (뿰寃)")
            self.btn_send_phase.setEnabled(False)
            QMessageBox.information(self, "Hardware", "Disconnected.")
    def send_phase_data(self):
        if not hasattr(self, 'serial_port') or self.serial_port is None:
            return
            
        try:
            if hasattr(self, '_last_packet') and self._last_packet is not None:
                self.serial_port.write(self._last_packet)
            else:
                import numpy as np
                phases = []
                for act in self.transducer_actors:
                    phase = getattr(act, '_phase', 0.0)
                    # Map 0 ~ 2*pi to 0 ~ 31 (SonicSurface format)
                    val = int(round((phase / (2.0 * np.pi)) * 32.0))
                    if val >= 32: val = 0
                    if val < 0: val = 0
                    phases.append(val)
                    
                if not phases:
                    return
                
                packet = bytearray([254])
                packet.extend(phases)
                packet.append(253)
                self.serial_port.write(bytes(packet))
        except Exception as e:
            print(f"HW Send Error: {e}")
            
    def apply_ui_transform(self):
        """doc"""""
        if self._is_updating_ui or not self.selected_actors:
            return
            
        dx = self.sel_x.value() - self._sel_base_centroid[0]
        dy = self.sel_y.value() - self._sel_base_centroid[1]
        dz = self.sel_z.value() - self._sel_base_centroid[2]
        
        drx = self.sel_rx.value() - self._sel_base_rot[0]
        dry = self.sel_ry.value() - self._sel_base_rot[1]
        drz = self.sel_rz.value() - self._sel_base_rot[2]
        if abs(dx) < 1e-5 and abs(dy) < 1e-5 and abs(dz) < 1e-5 and abs(drx) < 1e-5 and abs(dry) < 1e-5 and abs(drz) < 1e-5:
            return
        
        # 蹂??留ㅽ듃占?占쏙옙 ?占쎌꽦
        t = vtk.vtkTransform()
        t.Translate(self._sel_base_centroid[0] + dx, self._sel_base_centroid[1] + dy, self._sel_base_centroid[2] + dz)
        t.RotateX(drx)
        t.RotateY(dry)
        t.RotateZ(drz)
        t.Translate(-self._sel_base_centroid[0], -self._sel_base_centroid[1], -self._sel_base_centroid[2])
        
        delta_matrix = t.GetMatrix()
        
        point_moved = False
        for act in self.selected_actors:
            new_mat = vtk.vtkMatrix4x4()
            vtk.vtkMatrix4x4.Multiply4x4(delta_matrix, act._initial_matrix, new_mat)
            act.SetUserMatrix(new_mat)
            
            # 而⑦듃占??占쎌씤?占쎌씤 寃쎌슦 ?占쏙옙? ?占쎌씠???占쎄린??            
            for pt in self.control_points:
                if pt["actor"] == act:
                    c = act.center
                    pt["x"], pt["y"], pt["z"] = c[0], c[1], c[2]
                    point_moved = True
                    
        # 湲곗쫰紐 쐞移 뾽뜲씠듃
        if hasattr(self, 'gizmo_actors') and self.gizmo_actors:
            t2 = vtk.vtkTransform()
            t2.Translate(dx, dy, dz)
            for act in self.gizmo_actors.values():
                act.SetUserMatrix(t2.GetMatrix())
            
        if point_moved and self.auto_calc_cb.isChecked():
            if not getattr(self, '_sim_pending', False):
                self._sim_pending = True
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._deferred_simulate)
        else:
            self.plotter.render()
            
    def _deferred_simulate(self):
        self._sim_pending = False
        if hasattr(self, 'simulate_colors'):
            self.simulate_colors()
    def on_gizmo_interaction(self, caller, event):
        if not self.selected_actors: return
        t = vtk.vtkTransform()
        self.gizmo_rep.GetTransform(t)
        delta_pos = t.GetPosition()
        
        pos = [
            self._sel_base_centroid[0] + delta_pos[0],
            self._sel_base_centroid[1] + delta_pos[1],
            self._sel_base_centroid[2] + delta_pos[2]
        ]
        
        self._is_gizmo_dragging = True
        self.sel_x.setValue(pos[0])
        self.sel_y.setValue(pos[1])
        self.sel_z.setValue(pos[2])
        self._is_gizmo_dragging = False
        
    def process_selection(self, start_pos, end_pos, modifiers):
        scale = self.plotter.interactor.devicePixelRatioF()
        x0 = int(round(start_pos.x() * scale))
        y0 = int(round(start_pos.y() * scale))
        x1 = int(round(end_pos.x() * scale))
        y1 = int(round(end_pos.y() * scale))
        
        vtk_y0 = self.plotter.window_size[1] - y0 - 1
        vtk_y1 = self.plotter.window_size[1] - y1 - 1
        
        dx = abs(x1 - x0)
        dy = abs(vtk_y1 - vtk_y0)
        
        cp_actors = self.get_control_point_actors()
        picked_props = []
        renderer = self.plotter.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
        
        
        if dx < 5 and dy < 5:
            prop_picker = vtk.vtkPropPicker()
            prop_picker.Pick(x0, vtk_y0, 0, renderer)
            prop = prop_picker.GetViewProp()
            pv_act = self.get_pyvista_actor(prop)
            if pv_act is not None:
                picked_props.append(pv_act)
        else:
            xmin, xmax = min(x0, x1), max(x0, x1)
            ymin, ymax = min(vtk_y0, vtk_y1), max(vtk_y0, vtk_y1)
            self.area_picker.AreaPick(xmin, ymin, xmax, ymax, renderer)
            
            props = self.area_picker.GetProp3Ds()
            props.InitTraversal()
            prop = props.GetNextProp3D()
            while prop:
                pv_act = self.get_pyvista_actor(prop)
                if pv_act is not None:
                    picked_props.append(pv_act)
                prop = props.GetNextProp3D()
        is_ctrl = bool(int(modifiers) & int(Qt.KeyboardModifier.ControlModifier)) if hasattr(modifiers, "__int__") else bool(modifiers & Qt.KeyboardModifier.ControlModifier.value) if type(modifiers) == int else bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        
        if not is_ctrl:
            for act in self.selected_actors:
                if hasattr(act, '_original_color'):
                    act.prop.color = act._original_color
                act.prop.opacity = getattr(act, '_original_opacity', 1.0)
            self.selected_actors.clear()
            
        for prop in picked_props:
            if is_ctrl and prop in self.selected_actors:
                self.selected_actors.remove(prop)
                if hasattr(prop, '_original_color'):
                    prop.prop.color = prop._original_color
                prop.prop.opacity = getattr(prop, '_original_opacity', 1.0)
            else:
                if prop not in self.selected_actors:
                    if not hasattr(prop, '_original_opacity'):
                        prop._original_opacity = prop.prop.opacity
                    self.selected_actors.append(prop)
                    prop.prop.color = "pink"
                    prop.prop.opacity = 0.4
        self.update_gizmo()
        self.update_ui_from_selection()
        self.plotter.render()
    def update_ui_from_selection(self):
        """doc"""
        self._is_updating_ui = True
        # 1. Reset UI to defaults
        self.prop_sensor_cb.setEnabled(False)
        self.prop_radius_spin.setEnabled(False)
        self.prop_type_lbl.setText("-")
        
        # 2. Check selection
        if not self.selected_actors:
            for act in getattr(self, 'gizmo_actors', {}).values():
                act.SetVisibility(False)
            self.sel_x.setValue(0); self.sel_y.setValue(0); self.sel_z.setValue(0)
            self.sel_rx.setValue(0); self.sel_ry.setValue(0); self.sel_rz.setValue(0)
            self._is_updating_ui = False
            return
        # 3. Analyze selection types
        has_sensor = any(a in self.transducer_actors for a in self.selected_actors)
        cp_actor = None
        has_cp = False
        for a in self.selected_actors:
            if any(pt["actor"] == a for pt in self.control_points):
                has_cp = True
                cp_actor = a
                break
                
        if has_sensor and not has_cp:
            self.prop_type_lbl.setText("珥덉쓬뙆 꽱꽌")
            self.prop_sensor_cb.setEnabled(True)
        elif has_cp and not has_sensor:
            self.prop_type_lbl.setText("점(Control Point)")
            self.prop_radius_spin.setEnabled(True)
            for pt in self.control_points:
                if pt["actor"] == cp_actor:
                    self.prop_radius_spin.setValue(pt.get("radius", 5.0))
                    break
        elif has_sensor and has_cp:
            self.prop_type_lbl.setText("떎以 꽑깮 (샎빀)")
            self._sel_base_centroid = [0.0, 0.0, 0.0]
            self._sel_base_rot = [0.0, 0.0, 0.0]
            self._is_updating_ui = False
            return
        # 4. Calculate centroid for Gizmo
        import vtk
        cx, cy, cz = 0.0, 0.0, 0.0
        for act in self.selected_actors:
            c = act.center
            cx += c[0]; cy += c[1]; cz += c[2]
            
            # Update initial_matrix to current matrix so new transforms are relative to here
            current_mat = act.GetUserMatrix()
            if current_mat:
                new_init = vtk.vtkMatrix4x4()
                new_init.DeepCopy(current_mat)
                act._initial_matrix = new_init
                
        n = len(self.selected_actors)
        cx /= n; cy /= n; cz /= n
        
        self._sel_base_centroid = [cx, cy, cz]
        self._sel_base_rot = [0.0, 0.0, 0.0]
        
        self.sel_x.setValue(cx); self.sel_y.setValue(cy); self.sel_z.setValue(cz)
        self.sel_rx.setValue(0); self.sel_ry.setValue(0); self.sel_rz.setValue(0)
        # 5. Update Gizmo
        if not getattr(self, '_is_gizmo_dragging', False):
            if not getattr(self, 'selected_actors', []):
                for act in getattr(self, 'gizmo_actors', {}).values():
                    act.SetVisibility(False)
                # Reset all opacity
                for act in getattr(self, 'transducer_actors', []) + [p["actor"] for p in getattr(self, 'control_points', [])]:
                    if hasattr(act, 'prop'):
                        act.prop.opacity = 1.0
            else:
                # Reset all actors opacity
                for act in self.transducer_actors + [p["actor"] for p in self.control_points]:
                    if hasattr(act, 'prop'):
                        act.prop.opacity = 1.0
                # Set selected actors opacity
                for act in self.selected_actors:
                    if hasattr(act, 'prop'):
                        act.prop.opacity = 0.5
                        
                min_x, max_x, min_y, max_y, min_z, max_z = float('inf'), float('-inf'), float('inf'), float('-inf'), float('inf'), float('-inf')
                for act in self.selected_actors:
                    b = act.bounds
                    if b[0] < min_x: min_x = b[0]
                    if b[1] > max_x: max_x = b[1]
                    if b[2] < min_y: min_y = b[2]
                    if b[3] > max_y: max_y = b[3]
                    if b[4] < min_z: min_z = b[4]
                    if b[5] > max_z: max_z = b[5]
                    
                dx_b = (max_x - min_x)
                dy_b = (max_y - min_y)
                dz_b = (max_z - min_z)
                
                d = 10.0 # Make it smaller and constant
                
                import pyvista as pv
                import vtk
                for axis, dir_vec in [('x', (1,0,0)), ('y', (0,1,0)), ('z', (0,0,1))]:
                    mesh = pv.Cylinder(center=(cx + d/2*dir_vec[0], cy + d/2*dir_vec[1], cz + d/2*dir_vec[2]), direction=dir_vec, radius=d*0.02, height=d).merge(
                           pv.Sphere(center=(cx + d*dir_vec[0], cy + d*dir_vec[1], cz + d*dir_vec[2]), radius=d*0.08))
                    if axis in getattr(self, 'gizmo_actors', {}):
                        self.gizmo_actors[axis].mapper.dataset = mesh
                        self.gizmo_actors[axis].SetVisibility(True)
                        self.gizmo_actors[axis].prop.color = {'x':'red','y':'green','z':'blue'}[axis]
                        self.gizmo_actors[axis].SetUserMatrix(vtk.vtkMatrix4x4())
                        
                        # Render on top
                        mapper = self.gizmo_actors[axis].GetMapper()
                        mapper.SetResolveCoincidentTopologyToPolygonOffset()
                        mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(-10, -10)
                        mapper.SetRelativeCoincidentTopologyLineOffsetParameters(-10, -10)
                        
                if 'center' in getattr(self, 'gizmo_actors', {}):
                    c_mesh = pv.Sphere(center=(cx, cy, cz), radius=d*0.12)
                    self.gizmo_actors['center'].mapper.dataset = c_mesh
                    self.gizmo_actors['center'].SetVisibility(True)
                    self.gizmo_actors['center'].prop.color = 'white'
                    self.gizmo_actors['center'].SetUserMatrix(vtk.vtkMatrix4x4())
                    
                    mapper = self.gizmo_actors['center'].GetMapper()
                    mapper.SetResolveCoincidentTopologyToPolygonOffset()
                    mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(-10, -10)
                    mapper.SetRelativeCoincidentTopologyLineOffsetParameters(-10, -10)
            
        self._is_updating_ui = False
    
    def on_prop_sensor_changed(self, idx):
        if getattr(self, '_is_updating_ui', False) or not self.selected_actors: return
        sensor_type = self.prop_sensor_cb.currentText()
        if "10mm" in sensor_type:
            height, color, amplitude = 4.0, "lightblue", 1.0
            mesh = self.make_truncated_cone(5.0, 3.5, height)
        elif "16mm" in sensor_type:
            height, color, amplitude = 6.0, "orange", 2.0
            mesh = self.make_truncated_cone(8.0, 5.0, height)
        else: # Langevin
            height, color, amplitude = 40.0, "silver", 20.0
            mesh = getattr(self, 'make_langevin_mesh', lambda h: self.make_truncated_cone(25.0, 15.0, h))(height)
            
        new_actors = []
        for act in self.selected_actors:
            if act in self.transducer_actors:
                mat = act.GetUserMatrix() or getattr(act, '_initial_matrix', None)
                self.plotter.remove_actor(act)
                self.transducer_actors.remove(act)
                
                new_act = self.plotter.add_mesh(mesh.copy(), color=color, show_edges=True)
                new_act._amplitude = amplitude
                if mat:
                    new_act.SetUserMatrix(mat)
                    new_act._initial_matrix = mat
                new_act._original_color = color
                new_act._original_opacity = getattr(act, '_original_opacity', 1.0)
                new_act.prop.color = "pink"
                new_act.prop.opacity = 0.4
                self.transducer_actors.append(new_act)
                new_actors.append(new_act)
            else:
                new_actors.append(act)
        self.selected_actors = new_actors
        self.plotter.render()
        
    def on_prop_radius_changed(self, val):
        if getattr(self, '_is_updating_ui', False) or not self.selected_actors: return
        new_actors = []
        for act in self.selected_actors:
            is_cp = False
            for pt in self.control_points:
                if pt["actor"] == act:
                    is_cp = True
                    x, y, z = pt["x"], pt["y"], pt["z"]
                    pt["radius"] = val
                    self.plotter.remove_actor(act)
                    import pyvista as pv
                    import vtk
                    sphere = pv.Sphere(radius=val, center=(x, y, z))
                    new_act = self.plotter.add_mesh(sphere, color="green", show_edges=False)
                    new_act._original_color = "green"
                    new_act._original_opacity = getattr(act, '_original_opacity', 1.0)
                    new_act.prop.color = "pink"
                    new_act.prop.opacity = 0.4
                    pt["actor"] = new_act
                    
                    mat = act.GetUserMatrix()
                    if mat: new_act.SetUserMatrix(mat)
                    new_act._initial_matrix = getattr(act, '_initial_matrix', vtk.vtkMatrix4x4())
                    new_actors.append(new_act)
                    break
            if not is_cp:
                new_actors.append(act)
        self.selected_actors = new_actors
        self.plotter.render()
    def delete_selected_objects(self):
        if not self.selected_actors:
            return
            
        for actor in self.selected_actors:
            if actor in self.transducer_actors:
                self.transducer_actors.remove(actor)
                self.plotter.remove_actor(actor)
            else:
                # Check if it's a control point
                for i, cp in enumerate(self.control_points):
                    if cp["actor"] == actor:
                        self.plotter.remove_actor(actor)
                        del self.control_points[i]
                        self.points_list.takeItem(i)
                        break
                        
        self.selected_actors.clear()
        self.update_transform_ui()
        self.plotter.render()
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.delete_selected_objects()
        super().keyPressEvent(event)
    def has_unsaved_changes(self):
        current = self.get_state()
        saved = getattr(self, '_last_saved_state', getattr(self, '_initial_state', None))
        return current != saved
    def closeEvent(self, event):
        if self.has_unsaved_changes():
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(self, '앱 종료', '프로젝트가 수정되었습니다. 저장하시겠습니까?', QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if reply == QMessageBox.Save:
                self.save_project()
                event.accept()
            elif reply == QMessageBox.Cancel:
                event.ignore()
            else:
                event.accept()
        else:
            event.accept()
    def update_gizmo(self):
        if hasattr(self, 'gizmo') and self.gizmo is not None:
            self.gizmo.Off()
            self.gizmo = None
            
        if not self.selected_actors:
            return
            
        # [?占쎌떆 鍮꾪솢?占쏀솕] vtkVectorText ?占쎈윭 臾몄젣占??占쏀빐 ?占쎈㈃?占쎌쓽 3D ?占쎌궡??湲곗쫰紐⑤뒗 ?占쎌떆 爰쇰몼?占쎈떎.
        # ?占쎌튂 ?占쎈룞?占 ?占쎌륫 ?占쎈꼸??'1. Selected Object Transform' ?占쏙옙?諛뺤뒪占??占쏀빐 ?占쎈꼍??議곗옉 媛?占쏀빀?占쎈떎.
        pass
        for act in self.selected_actors:
            mat = vtk.vtkMatrix4x4()
            if act.GetUserMatrix():
                mat.DeepCopy(act.GetUserMatrix())
            else:
                mat.Identity()
            act._initial_matrix = mat
    def _hooked_add_control_point(self):
        self.add_control_point()
        self.push_state()
        
    def _hooked_del_control_point(self):
        self.delete_control_point()
        self.push_state()
        
    def _hooked_clear_view(self):
        self.clear_view()
        self.push_state()
        
    def _hooked_generate_array(self):
        self.generate_array()
        self.push_state()
    def add_control_point(self):
        idx = len(self.control_points)
        name = f"Point {idx+1}"
        x, y, z = 0.0, 0.0, 50.0 + (idx * 20)
        
        radius = getattr(self, 'point_size_spin', None)
        r = radius.value() if radius else 5.0
        sphere = pv.Sphere(radius=r, center=(x, y, z))
        actor = self.plotter.add_mesh(sphere, color="green", show_edges=False)
        actor._original_color = "green"
        self.control_points.append({"name": name, "actor": actor, "x": x, "y": y, "z": z, "radius": r})
        
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self.points_list.addItem(item)
        self.points_list.setCurrentRow(idx)
    def delete_control_point(self):
        idx = self.points_list.currentRow()
        if idx >= 0 and idx < len(self.control_points):
            actor = self.control_points[idx]["actor"]
            if actor in self.selected_actors:
                self.selected_actors.remove(actor)
                self.update_gizmo()
            self.plotter.remove_actor(actor)
            del self.control_points[idx]
            self.points_list.takeItem(idx)
            self.plotter.render()
    def on_point_selected(self, idx):
        self.selected_point_index = idx
        if idx >= 0 and idx < len(self.control_points):
            pt = self.control_points[idx]
            # ?占쎌씤??由ъ뒪???占쎈┃ ???占쎈떦 ?占쎌씤?占쏙옙? ?占쎈룆 ?占쏀깮 ?占쏀깭占?留뚮벀
            if not (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier):
                for act in self.selected_actors:
                    if hasattr(act, '_original_color'):
                        act.prop.color = act._original_color
                self.selected_actors.clear()
            
            if pt["actor"] not in self.selected_actors:
                self.selected_actors.append(pt["actor"])
                pt["actor"].prop.color = "pink"
                
            self.update_gizmo()
            self.update_ui_from_selection()
            self.plotter.render()
    def get_state(self):
        data = {}
        # Array UI Params
        data['transducer_type'] = self.transducer_type_cb.currentText() if hasattr(self, 'transducer_type_cb') else ""
        data['array_type'] = self.array_type_cb.currentText() if hasattr(self, 'array_type_cb') else ""
        data['spacing'] = self.spacing_spin.value() if hasattr(self, 'spacing_spin') else 10.5
        
        # Field UI Params
        data['trap_type'] = self.trap_type_cb.currentText() if hasattr(self, 'trap_type_cb') else ""
        data['grid_x'] = self.grid_x_spin.value() if hasattr(self, 'grid_x_spin') else 16
        data['grid_y'] = self.grid_y_spin.value() if hasattr(self, 'grid_y_spin') else 16
        data['point_size'] = self.point_size_spin.value() if hasattr(self, 'point_size_spin') else 5.0
        data['prop_radius'] = self.prop_radius_spin.value() if hasattr(self, 'prop_radius_spin') else 5.0
        
        # Field Slice Visualization Params
        data['show_field'] = self.show_field_btn.isChecked() if hasattr(self, 'show_field_btn') else False
        data['field_mode'] = self.field_mode_combo.currentText() if hasattr(self, 'field_mode_combo') else ""
        data['xz_check'] = self.xz_check.isChecked() if hasattr(self, 'xz_check') else False
        data['xz_slider'] = self.xz_slider.value() if hasattr(self, 'xz_slider') else 0
        data['yz_check'] = self.yz_check.isChecked() if hasattr(self, 'yz_check') else False
        data['yz_slider'] = self.yz_slider.value() if hasattr(self, 'yz_slider') else 0
        data['xy_check'] = self.xy_check.isChecked() if hasattr(self, 'xy_check') else False
        data['xy_slider'] = self.xy_slider.value() if hasattr(self, 'xy_slider') else 0
        
        # Targets (Save true updated world position)
        data['control_points'] = []
        for pt in getattr(self, 'control_points', []):
            try:
                center = self._get_actor_world_center(pt['actor'])
            except:
                center = pt['actor'].center
            data['control_points'].append({
                'name': pt['name'], 'x': float(center[0]), 'y': float(center[1]), 'z': float(center[2]), 'radius': pt['radius']
            })
            
        # Transducers Matrices
        data['transducers'] = []
        for actor in getattr(self, 'transducer_actors', []):
            mat = actor.GetUserMatrix()
            matrix_vals = []
            if mat:
                for r in range(4):
                    for c in range(4):
                        matrix_vals.append(mat.GetElement(r, c))
            data['transducers'].append({'matrix': matrix_vals})
        return data
    def set_state(self, data):
        import pyvista as pv
        import vtk
        # Array UI Params
        if 'transducer_type' in data and hasattr(self, 'transducer_type_cb'):
            idx = self.transducer_type_cb.findText(data['transducer_type'])
            if idx >= 0: self.transducer_type_cb.setCurrentIndex(idx)
        if 'array_type' in data and hasattr(self, 'array_type_cb'):
            idx = self.array_type_cb.findText(data['array_type'])
            if idx >= 0: self.array_type_cb.setCurrentIndex(idx)
        if 'spacing' in data and hasattr(self, 'spacing_spin'): self.spacing_spin.setValue(data['spacing'])
        # Restore parameters
        if 'trap_type' in data:
            idx = self.trap_type_cb.findText(data['trap_type'])
            if idx >= 0: self.trap_type_cb.setCurrentIndex(idx)
        if 'grid_x' in data: self.grid_x_spin.setValue(data['grid_x'])
        if 'grid_y' in data: self.grid_y_spin.setValue(data['grid_y'])
        if 'point_size' in data: self.point_size_spin.setValue(data['point_size'])
        if 'prop_radius' in data: self.prop_radius_spin.setValue(data['prop_radius'])
        
        # Field Slice Visualization Params
        if hasattr(self, 'xz_check'):
            self.xz_check.blockSignals(True); self.xz_slider.blockSignals(True)
            self.yz_check.blockSignals(True); self.yz_slider.blockSignals(True)
            self.xy_check.blockSignals(True); self.xy_slider.blockSignals(True)
            if hasattr(self, 'show_field_btn'): self.show_field_btn.blockSignals(True)
            if hasattr(self, 'field_mode_combo'): self.field_mode_combo.blockSignals(True)
            
            if 'xz_check' in data: self.xz_check.setChecked(data['xz_check'])
            if 'xz_slider' in data: 
                self.xz_slider.setValue(data['xz_slider'])
                if hasattr(self, 'xz_spin'): self.xz_spin.blockSignals(True); self.xz_spin.setValue(data['xz_slider']); self.xz_spin.blockSignals(False)
            if 'yz_check' in data: self.yz_check.setChecked(data['yz_check'])
            if 'yz_slider' in data: 
                self.yz_slider.setValue(data['yz_slider'])
                if hasattr(self, 'yz_spin'): self.yz_spin.blockSignals(True); self.yz_spin.setValue(data['yz_slider']); self.yz_spin.blockSignals(False)
            if 'xy_check' in data: self.xy_check.setChecked(data['xy_check'])
            if 'xy_slider' in data: 
                self.xy_slider.setValue(data['xy_slider'])
                if hasattr(self, 'xy_spin'): self.xy_spin.blockSignals(True); self.xy_spin.setValue(data['xy_slider']); self.xy_spin.blockSignals(False)
            
            if 'show_field' in data and hasattr(self, 'show_field_btn'):
                self.show_field_btn.setChecked(data['show_field'])
                
            if 'field_mode' in data and hasattr(self, 'field_mode_combo'):
                idx = self.field_mode_combo.findText(data['field_mode'])
                if idx >= 0: self.field_mode_combo.setCurrentIndex(idx)
                
            self.xz_check.blockSignals(False); self.xz_slider.blockSignals(False)
            self.yz_check.blockSignals(False); self.yz_slider.blockSignals(False)
            self.xy_check.blockSignals(False); self.xy_slider.blockSignals(False)
            if hasattr(self, 'show_field_btn'): self.show_field_btn.blockSignals(False)
            if hasattr(self, 'field_mode_combo'): self.field_mode_combo.blockSignals(False)
            
            if hasattr(self, 'toggle_field_slice'):
                self.toggle_field_slice()
        # Optimize Transducer update
        tx_data = data.get('transducers', [])
        if tx_data:
            needs_rebuild = len(tx_data) != len(self.transducer_actors)
            
            if needs_rebuild:
                from PySide6.QtWidgets import QApplication
                for i, actor in enumerate(self.transducer_actors):
                    if actor in self.selected_actors: self.selected_actors.remove(actor)
                    self.plotter.remove_actor(actor)
                    if i % 20 == 0: QApplication.processEvents()
                self.transducer_actors.clear()
                
                sensor_type = data.get('transducer_type', self.transducer_type_cb.currentText() if hasattr(self, 'transducer_type_cb') else '')
                if "10mm" in sensor_type:
                    r_wide, r_narrow, height = 5.0, 3.5, 4.0
                    color = "lightblue"
                    base_mesh = self.make_truncated_cone(r_wide, r_narrow, height)
                    self._current_amplitude = 1.0
                elif "16mm" in sensor_type:
                    r_wide, r_narrow, height = 8.0, 5.0, 6.0
                    color = "orange"
                    base_mesh = self.make_truncated_cone(r_wide, r_narrow, height)
                    self._current_amplitude = 2.0
                else: # Langevin
                    r_wide, r_narrow, height = 25.0, 15.0, 40.0
                    color = "silver"
                    base_mesh = self.make_langevin_mesh(height)
                    self._current_amplitude = 20.0
                    
                for i, tx in enumerate(tx_data):
                    matrix_vals = tx.get('matrix')
                    if matrix_vals:
                        mat = vtk.vtkMatrix4x4()
                        for r in range(4):
                            for c in range(4):
                                mat.SetElement(r, c, matrix_vals[r*4 + c])
                        actor = self.plotter.add_mesh(base_mesh, color=color, show_edges=False)
                        actor.SetUserMatrix(mat)
                        actor._initial_matrix = mat
                        actor._original_color = color
                        actor._amplitude = self._current_amplitude
                        self.transducer_actors.append(actor)
                        if i % 20 == 0: QApplication.processEvents()
            else:
                # Optimized fast path! Just update matrices!
                for i, tx in enumerate(tx_data):
                    matrix_vals = tx.get('matrix')
                    if matrix_vals:
                        mat = vtk.vtkMatrix4x4()
                        for r in range(4):
                            for c in range(4):
                                mat.SetElement(r, c, matrix_vals[r*4 + c])
                        self.transducer_actors[i].SetUserMatrix(mat)
        # Optimize Control Points update
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidgetItem
        pt_data = data.get('control_points', [])
        
        needs_pt_rebuild = len(pt_data) != len(self.control_points)
        if needs_pt_rebuild:
            for p in self.control_points:
                if p["actor"] in self.selected_actors: self.selected_actors.remove(p["actor"])
                self.plotter.remove_actor(p["actor"])
            self.control_points.clear()
            self.points_list.clear()
            
            for pt in pt_data:
                idx = len(self.control_points)
                name = pt.get('name', f"Point {idx+1}")
                x, y, z = pt.get('x',0), pt.get('y',0), pt.get('z',50)
                r = pt.get('radius', 5.0)
                sphere = pv.Sphere(radius=r, center=(0, 0, 0)) # Base at origin
                actor = self.plotter.add_mesh(sphere, color="green", show_edges=False)
                # Translate it to x,y,z using matrix so Gizmo works properly
                mat = vtk.vtkMatrix4x4()
                mat.Identity()
                mat.SetElement(0, 3, x)
                mat.SetElement(1, 3, y)
                mat.SetElement(2, 3, z)
                actor.SetUserMatrix(mat)
                
                actor._original_color = "green"
                self.control_points.append({"name": name, "actor": actor, "x": x, "y": y, "z": z, "radius": r})
                
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.points_list.addItem(item)
        else:
            # Optimized fast path!
            for i, pt in enumerate(pt_data):
                x, y, z = pt.get('x',0), pt.get('y',0), pt.get('z',50)
                actor = self.control_points[i]['actor']
                mat = vtk.vtkMatrix4x4()
                mat.Identity()
                mat.SetElement(0, 3, x)
                mat.SetElement(1, 3, y)
                mat.SetElement(2, 3, z)
                actor.SetUserMatrix(mat)
                
        # Update UI state correctly after state restore
        if hasattr(self, 'update_gizmo'):
            self.update_gizmo()
        if hasattr(self, 'update_ui_from_selection'):
            self.update_ui_from_selection()
            
        # self.plotter.reset_camera() # Do not reset camera on undo, it's annoying!
        self.simulate_colors()
    def save_project(self):
        import json
        if not getattr(self, 'current_project_file', None):
            self.save_project_as()
            return
            
        data = self.get_state()
        with open(self.current_project_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        self.setWindowTitle(f"Acoustic Control Studio - {self.current_project_file}")
        self._last_saved_state = data
    def save_project_as(self):
        from PySide6.QtWidgets import QFileDialog
        import json
        filename, _ = QFileDialog.getSaveFileName(self, "떎瑜 씠由꾩쑝濡 봽濡쒖젥듃 옣", "", "Acoustic Project (*.json)")
        if not filename: return
        self.current_project_file = filename
        self.save_project()
    def load_project(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import json
        filename, _ = QFileDialog.getOpenFileName(self, "봽濡쒖젥듃 遺덈윭삤湲", "", "Acoustic Project (*.json)")
        if not filename: return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"작업 중 오류가 발생했습니다: {str(e)}")
            return
            
        self.current_project_file = filename
        self.set_state(data)
        self.push_state()
        self.setWindowTitle(f"Acoustic Control Studio - {self.current_project_file}")
        self._last_saved_state = data
    def push_state(self):
        if not hasattr(self, 'undo_stack'):
            self.undo_stack = []
            self.redo_stack = []
            
        state = self.get_state()
        # Only push if different from last state
        if not self.undo_stack or self.undo_stack[-1] != state:
            self.undo_stack.append(state)
            self.redo_stack.clear()
            
            # limit stack size to 20
            if len(self.undo_stack) > 20:
                self.undo_stack.pop(0)
    def undo(self):
        if not hasattr(self, 'undo_stack') or len(self.undo_stack) < 1:
            return
        current_actual_state = self.get_state()
        if self.undo_stack[-1] != current_actual_state:
            self.undo_stack.append(current_actual_state)
            self.redo_stack.clear()
        if len(self.undo_stack) > 1:
            current_state = self.undo_stack.pop()
            self.redo_stack.append(current_state)
            previous_state = self.undo_stack[-1]
            self.set_state(previous_state)
    def redo(self):
        if hasattr(self, 'redo_stack') and self.redo_stack:
            next_state = self.redo_stack.pop()
            self.undo_stack.append(next_state)
            self.set_state(next_state)
    def clear_view(self):
        for actor in self.transducer_actors:
            if actor in self.selected_actors:
                self.selected_actors.remove(actor)
            self.plotter.remove_actor(actor)
        self.transducer_actors.clear()
        
        for p in self.control_points:
            if p["actor"] in self.selected_actors:
                self.selected_actors.remove(p["actor"])
            self.plotter.remove_actor(p["actor"])
        self.control_points.clear()
        self.points_list.clear()
        
        self.update_gizmo()
        self.update_ui_from_selection()
        self.plotter.render()
    def make_truncated_cone(self, radius_wide, radius_narrow, height, resolution=36):
        angles = np.linspace(0, 2*np.pi, resolution, endpoint=False)
        pts = []
        for a in angles:
            pts.append([radius_wide * np.cos(a), radius_wide * np.sin(a), height / 2.0])
        for a in angles:
            pts.append([radius_narrow * np.cos(a), radius_narrow * np.sin(a), -height / 2.0])
        
        faces = []
        for i in range(resolution):
            nxt = (i + 1) % resolution
            faces.extend([4, i, nxt, resolution + nxt, resolution + i])
            
        # ?占쎈떒占?(Z ?占쎈갑?占쎌씠誘占?諛섏떆怨꾨갑??CCW)
        top_c = len(pts)
        pts.append([0, 0, height / 2.0])
        for i in range(resolution):
            nxt = (i + 1) % resolution
            faces.extend([3, top_c, i, nxt])
            
        # ?占쎈떒占?(Z ??占쏙옙?占쎌씠誘占??占쎄퀎諛⑺뼢 CW)
        bot_c = len(pts)
        pts.append([0, 0, -height / 2.0])
        for i in range(resolution):
            nxt = (i + 1) % resolution
            faces.extend([3, bot_c, resolution + nxt, resolution + i])
            
        mesh = pv.PolyData(np.array(pts), np.array(faces))
        # CAD ?占쎈줈洹몃옩泥섎읆 ?占쎌뭅濡쒖슫 紐⑥꽌占?媛?占쎌옄占????占쎌쁺??源⑤걮?占쎄쾶 ?占쎈┝
        mesh = mesh.compute_normals(split_vertices=True, feature_angle=60)
        return mesh
    def make_langevin_mesh(self, height=40.0):
        import pyvista as pv
        horn = pv.Cylinder(center=(0, 0, height*0.25), direction=(0, 0, 1), radius=25, height=height*0.5)
        piezo = pv.Cylinder(center=(0, 0, -height*0.125), direction=(0, 0, 1), radius=15, height=height*0.25)
        backing = pv.Cylinder(center=(0, 0, -height*0.375), direction=(0, 0, 1), radius=20, height=height*0.25)
        mesh = horn.merge(piezo).merge(backing)
        return mesh
    def generate_array(self):
        sensor_type = self.transducer_type_cb.currentText()
        array_type = self.array_type_cb.currentText()
        x_count = self.grid_x_spin.value()
        y_count = self.grid_y_spin.value()
        
        spacing = self.spacing_spin.value()
        
        if "10mm" in sensor_type:
            r_wide, r_narrow, height = 5.0, 3.5, 4.0
            color = "lightblue"
            base_mesh = self.make_truncated_cone(r_wide, r_narrow, height)
            self._current_amplitude = 1.0
        elif "16mm" in sensor_type:
            r_wide, r_narrow, height = 8.0, 5.0, 6.0
            color = "orange"
            base_mesh = self.make_truncated_cone(r_wide, r_narrow, height)
            self._current_amplitude = 2.0
        else: # Langevin
            r_wide, r_narrow, height = 25.0, 15.0, 40.0
            color = "silver"
            base_mesh = self.make_langevin_mesh(height)
            self._current_amplitude = 20.0
        transforms_to_add = []
        if "Matrix" in array_type or "평면" in array_type:
            start_x = -(x_count - 1) * spacing / 2.0
            start_y = -(y_count - 1) * spacing / 2.0
            for i in range(x_count):
                for j in range(y_count):
                    px_m = start_x + i * spacing
                    py_m = start_y + j * spacing
                    pz_m = -height / 2.0
                    transforms_to_add.append([("translate", (px_m, py_m, pz_m))])
                    
        elif "4" in array_type or "다면체" in array_type:
            tunnel_radius = (spacing * x_count) / 2.0
            start_u = -(x_count - 1) * spacing / 2.0
            start_v = -(y_count - 1) * spacing / 2.0
            for i in range(x_count):
                for j in range(y_count):
                    u = start_u + i * spacing
                    v = start_v + j * spacing
                    
                    transforms_to_add.append([("translate", (u, v, -tunnel_radius - height/2))])
                    transforms_to_add.append([("rotate_y", 180), ("translate", (u, v, tunnel_radius + height/2))])
                    transforms_to_add.append([("rotate_y", 90), ("translate", (-tunnel_radius - height/2, u, v))])
                    transforms_to_add.append([("rotate_y", -90), ("translate", (tunnel_radius + height/2, u, v))])
                    
        elif "2" in array_type or "대향형" in array_type:
            distance = max(100.0, spacing * max(x_count, y_count))
            start_x = -(x_count - 1) * spacing / 2.0
            start_y = -(y_count - 1) * spacing / 2.0
            for i in range(x_count):
                for j in range(y_count):
                    px_m = start_x + i * spacing
                    py_m = start_y + j * spacing
                    
                    transforms_to_add.append([("translate", (px_m, py_m, -distance/2 - height/2))])
                    transforms_to_add.append([("rotate_x", 180), ("translate", (px_m, py_m, distance/2 + height/2))])
                    
        elif "Tube" in array_type or "튜브" in array_type:
            import math
            columns = x_count
            rows = y_count
            if columns < 3: columns = 3
            
            angleInc = 2.0 * math.pi / columns
            radious = (spacing / 2.0) / math.tan(angleInc / 2.0)
            
            SQRT3_2 = math.sqrt(3.0) / 2.0
            spaceOdd = spacing * SQRT3_2
            
            tubeLength = spaceOdd * (rows - 1)
            start_x = -tubeLength / 2.0
            
            x_pos = start_x
            for row in range(rows):
                oddRow = (row % 2 == 0)
                angle = 0.0
                for col in range(columns):
                    cAngle = angle if oddRow else angle + angleInc / 2.0
                    dist = radious + height / 2.0
                    y_pos = math.sin(cAngle) * dist
                    z_pos = math.cos(cAngle) * dist
                    
                    cAngle_deg = cAngle * 180.0 / math.pi
                    transforms_to_add.append([("rotate_x", 180.0 - cAngle_deg), ("translate", (x_pos, y_pos, z_pos))])
                    angle += angleInc
                x_pos += spaceOdd
        elif "Hemisphere" in array_type or "반구형" in array_type:
            N = x_count * y_count
            R = max(100.0, r_wide * np.sqrt(N * 0.8))
            phi_golden = np.pi * (3.0 - np.sqrt(5.0))
            
            import vtk
            for i in range(N):
                z = -1.0 + (i / float(N))
                radius_at_z = np.sqrt(1.0 - z*z)
                theta = phi_golden * i
                
                px_m = np.cos(theta) * radius_at_z * R
                py_m = np.sin(theta) * radius_at_z * R
                pz_m = z * R
                
                v_dir = np.array([-px_m, -py_m, -pz_m])
                v_dir = v_dir / np.linalg.norm(v_dir)
                Z_axis = np.array([0, 0, 1])
                v_cross = np.cross(Z_axis, v_dir)
                s = np.linalg.norm(v_cross)
                c = np.dot(Z_axis, v_dir)
                
                mat = np.eye(4)
                if s < 1e-6:
                    if c < 0:
                        mat[0,0] = -1; mat[1,1] = -1; mat[2,2] = -1
                else:
                    vx = np.array([[0, -v_cross[2], v_cross[1]], 
                                   [v_cross[2], 0, -v_cross[0]], 
                                   [-v_cross[1], v_cross[0], 0]])
                    R_mat = np.eye(3) + vx + (vx @ vx) * ((1 - c)/(s**2))
                    mat[:3, :3] = R_mat
                
                mat[:3, 3] = [px_m, py_m, pz_m]
                vtk_mat = vtk.vtkMatrix4x4()
                for r in range(4):
                    for c_idx in range(4):
                        vtk_mat.SetElement(r, c_idx, mat[r, c_idx])
                        
                transforms_to_add.append([("transform", vtk_mat)])
        rx, ry, rz = self.gen_rot_x.value(), self.gen_rot_y.value(), self.gen_rot_z.value()
        px, py, pz = self.gen_pos_x.value(), self.gen_pos_y.value(), self.gen_pos_z.value()
        
        import vtk
        from PySide6.QtWidgets import QApplication
        
        qapp = QApplication.instance()
        for idx, ops in enumerate(transforms_to_add):
            transform = vtk.vtkTransform()
            transform.PostMultiply()
            for op, val in ops:
                if op == "translate": transform.Translate(val)
                elif op == "rotate_x": transform.RotateX(val)
                elif op == "rotate_y": transform.RotateY(val)
                elif op == "rotate_z": transform.RotateZ(val)
                elif op == "transform": transform.Concatenate(val)
                
            transform.RotateX(rx)
            transform.RotateY(ry)
            transform.RotateZ(rz)
            transform.Translate(px, py, pz)
            
            actor = self.plotter.add_mesh(base_mesh, color=color, show_edges=False)
            actor.SetUserMatrix(transform.GetMatrix())
            actor._initial_matrix = transform.GetMatrix()
            actor._original_color = color
            actor._amplitude = getattr(self, '_current_amplitude', 1.0)
            self.transducer_actors.append(actor)
            
            # Keep UI responsive for large array generation
            if idx % 10 == 0 and qapp:
                qapp.processEvents()
                
        self.plotter.reset_camera()
    def simulate_colors(self):
        import time
        if hasattr(self, 'run_btn') and self.run_btn.isCheckable() and not self.run_btn.isChecked():
            return
        current_time = time.time()
        if hasattr(self, '_last_sim_time') and (current_time - self._last_sim_time) < 0.016:
            if not hasattr(self, '_sim_timer'):
                from PySide6.QtCore import QTimer
                self._sim_timer = QTimer()
                self._sim_timer.setSingleShot(True)
                self._sim_timer.timeout.connect(self.simulate_colors)
            if not self._sim_timer.isActive():
                self._sim_timer.start(16)
            return
        self._last_sim_time = current_time
        if hasattr(self, '_sim_timer'):
            self._sim_timer.stop()
            
        if not self.transducer_actors:
            return
        if not self.control_points:
            print("알림: 점(Control Point)을 1개 이상 추가해야 위상을 시뮬레이션할 수 있습니다.")
            return
            
        algorithm = self.trap_type_cb.currentText()
        
        # 珥덉쓬??臾쇰━ ?占쎌닔
        c = 343000.0 # ?占쎌냽 (mm/s)
        f = 40000.0 # 二쇳뙆??(Hz)
        k = 2.0 * np.pi / (c / f) # ?닔 (Wavenumber)
        
        import matplotlib.cm as cm
        cmap = cm.get_cmap('hsv') # 0~360룄瑜 臾댁媛쒖깋쑝濡 留ㅽ븨
        
        active_pts = []
        for idx, pt in enumerate(self.control_points):
            item = self.points_list.item(idx)
            if item and item.checkState() == Qt.Checked:
                active_pts.append(pt)
                
        centers = np.array([actor.center for actor in self.transducer_actors])
        self._last_packet = None
        
        if active_pts:
            from acousticstudio.sonic_wrapper import calculate_phases_sonic
            cx = centers[:, 0]
            cy = centers[:, 1]
            cz = centers[:, 2]
            tx_arr = np.array([pt["x"] for pt in active_pts])
            ty_arr = np.array([pt["y"] for pt in active_pts])
            tz_arr = np.array([pt["z"] for pt in active_pts])
            tx_amplitudes = np.array([getattr(a, '_amplitude', 1.0) for a in self.transducer_actors])
            
            mode_idx = self.compute_mode_cb.currentIndex()
            cpp_phases, cpp_packet = None, None
            
            if mode_idx == 3 and getattr(self, 'has_pytorch', False):
                from acousticstudio.sonic_wrapper import calculate_phases_gpu
                cpp_phases, cpp_packet = calculate_phases_gpu(cx, cy, cz, tx_arr, ty_arr, tz_arr, tx_amplitudes, algorithm, k)
            elif mode_idx == 2 and getattr(self, 'has_taichi', False):
                from acousticstudio.sonic_wrapper import calculate_phases_taichi
                cpp_phases, cpp_packet = calculate_phases_taichi(cx, cy, cz, tx_arr, ty_arr, tz_arr, tx_amplitudes, algorithm, k)
            elif mode_idx == 1:
                from acousticstudio.sonic_wrapper import calculate_phases_sonic
                cpp_phases, cpp_packet = calculate_phases_sonic(cx, cy, cz, tx_arr, ty_arr, tz_arr, tx_amplitudes, algorithm, k)
            
            if cpp_phases is not None:
                total_phases = cpp_phases
                self._last_packet = cpp_packet
            else:
                # Fallback to NumPy
                complex_p = np.zeros(len(centers), dtype=np.complex128)
                for pt in active_pts:
                    tx, ty, tz = pt["x"], pt["y"], pt["z"]
                    dx = cx - tx
                    dy = cy - ty
                    dz = cz - tz
                    
                    d = np.sqrt(dx**2 + dy**2 + dz**2)
                    phase_focal = -d * k
                    
                    if "Twin Trap" in algorithm:
                        signature = np.where(dx > 0, np.pi, 0.0)
                    elif "Vortex Trap" in algorithm:
                        signature = np.arctan2(dy, dx)
                    else:
                        signature = np.zeros_like(dx)
                        
                    pt_phase = phase_focal + signature
                    complex_p += tx_amplitudes * np.exp(1j * pt_phase)
                    
                total_phases = np.angle(complex_p) % (2.0 * np.pi)
                total_phases[total_phases < 0] += 2.0 * np.pi
        else:
            total_phases = np.zeros(len(centers), dtype=np.float64)
        
        color_vals = total_phases / (2.0 * np.pi)
        rgbas = cmap(color_vals)
        
        for i, actor in enumerate(self.transducer_actors):
            actor._original_color = rgbas[i, :3]
            prop = actor.GetProperty()
            if hasattr(self, 'selected_actors') and actor in self.selected_actors:
                prop.SetColor(1.0, 0.75, 0.8) # approximate pink
                prop.SetOpacity(0.4)
            else:
                prop.SetColor(float(rgbas[i, 0]), float(rgbas[i, 1]), float(rgbas[i, 2]))
                prop.SetOpacity(float(getattr(actor, '_original_opacity', 1.0)))
            actor._phase = total_phases[i]
            
        if self.show_field_btn.isChecked():
            self.update_field_slice()
        else:
            self.plotter.render()
            
        
        
        # Real-time hardware transmission
        if hasattr(self, 'serial_port') and self.serial_port is not None:
            self.send_phase_data()
    def toggle_field_slice(self):
        if self.show_field_btn.isChecked():
            self.show_field_btn.setText("음압 단면 숨기기")
            self.update_field_slice()
        else:
            self.show_field_btn.setText("음압 단면 시각화")
            for a in self.field_actors:
                self.plotter.remove_actor(a)
            self.field_actors.clear()
            self.plotter.render()
    def draw_ghost_plane(self, axis_name, offset):
        if not self.show_field_btn.isChecked() or not self.transducer_actors: return
        import numpy as np
        import pyvista as pv
        
        tx_centers = np.array([a.center for a in self.transducer_actors])
        min_x, max_x = np.min(tx_centers[:, 0]), np.max(tx_centers[:, 0])
        min_y, max_y = np.min(tx_centers[:, 1]), np.max(tx_centers[:, 1])
        min_z, max_z = np.min(tx_centers[:, 2]), np.max(tx_centers[:, 2])
        
        pad = 30.0
        bx_min, bx_max = min_x - pad, max_x + pad
        by_min, by_max = min_y - pad, max_y + pad
        bz_min, bz_max = min_z - pad, max_z + pad
        if bx_max - bx_min < 50: bx_min -= 25; bx_max += 25
        if by_max - by_min < 50: by_min -= 25; by_max += 25
        if bz_max - bz_min < 50: bz_min -= 25; bz_max += 25
        
        cx, cy, cz = (bx_min+bx_max)/2, (by_min+by_max)/2, (bz_min+bz_max)/2
        wx, wy, wz = bx_max-bx_min, by_max-by_min, bz_max-bz_min
        
        if axis_name == 'xz': center, d, i, j = (cx, offset, cz), (0,1,0), wx, wz
        elif axis_name == 'yz': center, d, i, j = (offset, cy, cz), (1,0,0), wy, wz
        else: center, d, i, j = (cx, cy, offset), (0,0,1), wx, wy
            
        plane = pv.Plane(center=center, direction=d, i_size=i, j_size=j)
        
        if not hasattr(self, '_ghost_actors'):
            self._ghost_actors = {}
            
        if axis_name not in self._ghost_actors:
            plane = pv.Plane(center=(0,0,0), direction=d, i_size=i, j_size=j)
            act = self.plotter.add_mesh(plane, color='white', opacity=0.4, show_edges=True, name=f'ghost_{axis_name}')
            self._ghost_actors[axis_name] = act
        else:
            plane = pv.Plane(center=center, direction=d, i_size=i, j_size=j)
            act = self.plotter.add_mesh(plane, color='white', opacity=0.4, show_edges=True, name=f'ghost_{axis_name}')
            self._ghost_actors[axis_name] = act
            
        # Hide ONLY the active plane being moved
        axis_idx_map = {'xz': '0', 'yz': '1', 'xy': '2'}
        moving_key = axis_idx_map[axis_name]
        
        if hasattr(self, '_cached_field_grids') and moving_key in self._cached_field_grids:
            _, act = self._cached_field_grids[moving_key]
            act.SetVisibility(False)
            
        self.plotter.render()
    def update_field_slice(self, *args):
        if hasattr(self, '_ghost_actors'):
            for act in self._ghost_actors.values():
                act.SetVisibility(False)
            
        if not hasattr(self, '_cached_field_grids'):
            self._cached_field_grids = {}
        if not self.show_field_btn.isChecked() or not self.transducer_actors:
            for a in self.field_actors:
                a.SetVisibility(False)
            self.plotter.render()
            return
        c = 343000.0
        f = 40000.0
        k = 2.0 * np.pi / (c / f)
        
        tx_centers = np.array([a.center for a in self.transducer_actors])
        tx_phases = np.array([getattr(a, '_phase', 0.0) for a in self.transducer_actors])
        tx_amplitudes = np.array([getattr(a, '_amplitude', 1.0) for a in self.transducer_actors])
        
        min_x, max_x = np.min(tx_centers[:, 0]), np.max(tx_centers[:, 0])
        min_y, max_y = np.min(tx_centers[:, 1]), np.max(tx_centers[:, 1])
        min_z, max_z = np.min(tx_centers[:, 2]), np.max(tx_centers[:, 2])
        
        pad = 30.0
        bx_min, bx_max = min_x - pad, max_x + pad
        by_min, by_max = min_y - pad, max_y + pad
        bz_min, bz_max = min_z - pad, max_z + pad
        
        if bx_max - bx_min < 50: bx_min -= 25; bx_max += 25
        if by_max - by_min < 50: by_min -= 25; by_max += 25
        if bz_max - bz_min < 50: bz_min -= 25; bz_max += 25
        
        res = 120
        x_vals = np.linspace(bx_min, bx_max, res)
        y_vals = np.linspace(by_min, by_max, res)
        z_vals = np.linspace(bz_min, bz_max, res)
        
        planes_to_draw = []
        if self.xz_check.isChecked(): planes_to_draw.append((0, self.xz_slider.value()))
        if self.yz_check.isChecked(): planes_to_draw.append((1, self.yz_slider.value()))
        if self.xy_check.isChecked(): planes_to_draw.append((2, self.xy_slider.value()))
        # Keep track of active planes to hide unused ones
        active_plane_keys = set()
        
        for plane_idx, offset in planes_to_draw:
            cache_key = str(plane_idx)
            active_plane_keys.add(cache_key)
            
            if plane_idx == 0:
                X, Z = np.meshgrid(x_vals, z_vals)
                pts = np.c_[X.ravel(), np.full(res*res, offset), Z.ravel()]
            elif plane_idx == 1:
                Y, Z = np.meshgrid(y_vals, z_vals)
                pts = np.c_[np.full(res*res, offset), Y.ravel(), Z.ravel()]
            else:
                X, Y = np.meshgrid(x_vals, y_vals)
                pts = np.c_[X.ravel(), Y.ravel(), np.full(res*res, offset)]
                
            from acousticstudio.sonic_wrapper import calculate_field_slice_sonic
            pts_x = np.ascontiguousarray(pts[:, 0], dtype=np.float64)
            pts_y = np.ascontiguousarray(pts[:, 1], dtype=np.float64)
            pts_z = np.ascontiguousarray(pts[:, 2], dtype=np.float64)
            tx_x = np.ascontiguousarray(tx_centers[:, 0], dtype=np.float64)
            tx_y = np.ascontiguousarray(tx_centers[:, 1], dtype=np.float64)
            tx_z = np.ascontiguousarray(tx_centers[:, 2], dtype=np.float64)
            
            is_phase_mode = hasattr(self, 'field_mode_combo') and self.field_mode_combo.currentIndex() == 1
            mode_idx = self.compute_mode_cb.currentIndex()
            
            calc_res = None
            if mode_idx == 3 and getattr(self, 'has_pytorch', False):
                from acousticstudio.sonic_wrapper import calculate_field_slice_gpu
                calc_res = calculate_field_slice_gpu(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k)
            elif mode_idx == 2 and getattr(self, 'has_taichi', False):
                from acousticstudio.sonic_wrapper import calculate_field_slice_taichi
                calc_res = calculate_field_slice_taichi(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k)
                
            if calc_res is not None:
                real_p, imag_p = calc_res
            else:
                real_p, imag_p = calculate_field_slice_numba(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k)
            if is_phase_mode:
                scalar_data = np.arctan2(imag_p, real_p)
                p_min, p_max = -np.pi, np.pi
                cmap = 'hsv'
            else:
                scalar_data = np.sqrt(real_p**2 + imag_p**2)
                p_min, p_max = 0, np.percentile(scalar_data, 99.5)
                cmap = 'hot'
            import pyvista as pv
            if cache_key in self._cached_field_grids:
                grid, actor = self._cached_field_grids[cache_key]
                grid.points = pts
                grid.point_data['Pressure'][:] = scalar_data
                actor = self.plotter.add_mesh(
                    grid, scalars='Pressure', cmap=cmap, opacity=1.0,
                    show_scalar_bar=False, clim=[p_min, p_max],
                    reset_camera=False, name=f'field_{cache_key}'
                )
                actor.SetVisibility(True)
                self._cached_field_grids[cache_key] = (grid, actor)
            else:
                grid = pv.StructuredGrid()
                grid.points = pts
                grid.dimensions = [res, res, 1]
                grid.point_data['Pressure'] = scalar_data
                actor = self.plotter.add_mesh(
                    grid, scalars='Pressure', cmap=cmap, opacity=1.0,
                    show_scalar_bar=False, clim=[p_min, p_max],
                    reset_camera=False, name=f'field_{cache_key}'
                )
                self.field_actors.append(actor)
                self._cached_field_grids[cache_key] = (grid, actor)
        # Hide actors for planes no longer active
        for key, (grid, actor) in self._cached_field_grids.items():
            if key not in active_plane_keys:
                actor.SetVisibility(False)
                
        self.plotter.render()
    def update_compute_mode_styles(self):
        from PySide6.QtGui import QColor, QBrush
        if not hasattr(self, 'compute_mode_cb'): return
        model = self.compute_mode_cb.model()
        if not model: return
        
        if getattr(self, 'has_taichi', False):
            self.compute_mode_cb.setItemText(2, "GPU: 범용 그래픽 (매우 빠름) (Taichi 가속)")
            model.item(2).setForeground(QBrush(QColor(0,0,0)))
        else:
            self.compute_mode_cb.setItemText(2, "GPU: 범용 그래픽 (미설치 - 클릭 시 설치)")
            model.item(2).setForeground(QBrush(QColor(150, 150, 150)))
            
        if getattr(self, 'has_pytorch', False):
            gpu_name = "GPU"
            try:
                from acousticstudio.sonic_wrapper import get_gpu_name
                gpu_name = get_gpu_name()
            except: pass
            self.compute_mode_cb.setItemText(3, f"GPU: {gpu_name} (가장 빠름) (PyTorch/CUDA 가속)")
            model.item(3).setForeground(QBrush(QColor(0,0,0)))
        else:
            self.compute_mode_cb.setItemText(3, "GPU: CUDA 전용 (미설치 - 클릭 시 설치)")
            model.item(3).setForeground(QBrush(QColor(150, 150, 150)))
            
    def on_compute_mode_changed(self, index):
        if index == 2 and not getattr(self, 'has_taichi', False):
            self._prompt_install_from_cb("taichi")
        elif index == 3 and not getattr(self, 'has_pytorch', False):
            self._prompt_install_from_cb("torch")
        else:
            if hasattr(self, 'simulate_colors'):
                self.simulate_colors()
            if hasattr(self, 'update_field_slice'):
                self.update_field_slice()
                
    def _prompt_install_from_cb(self, pkg):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "라이브러리 설치 필요", f"해당 기능을 사용하려면 '{pkg}' 라이브러리가 필요합니다.\n지금 다운로드 및 설치하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            from acousticstudio.installer_ui import LiveInstallerDialog
            dlg = LiveInstallerDialog([pkg], self)
            dlg.exec()
            import importlib.util
            if pkg == "taichi":
                self.has_taichi = importlib.util.find_spec("taichi") is not None
            elif pkg == "torch":
                self.has_pytorch = importlib.util.find_spec("torch") is not None
            self.update_compute_mode_styles()
            
            if (pkg == "taichi" and self.has_taichi) or (pkg == "torch" and self.has_pytorch):
                if hasattr(self, 'simulate_colors'):
                    self.simulate_colors()
            else:
                self.compute_mode_cb.blockSignals(True)
                self.compute_mode_cb.setCurrentIndex(0)
                self.compute_mode_cb.blockSignals(False)
        else:
            self.compute_mode_cb.blockSignals(True)
            self.compute_mode_cb.setCurrentIndex(0)
            self.compute_mode_cb.blockSignals(False)
            
    def open_library_manager(self):
        from acousticstudio.installer_ui import LibraryManagerDialog
        dlg = LibraryManagerDialog(self)
        dlg.exec()
        import importlib.util
        self.has_taichi = importlib.util.find_spec("taichi") is not None
        self.has_pytorch = importlib.util.find_spec("torch") is not None
        if hasattr(self, 'update_compute_mode_styles'):
            self.update_compute_mode_styles()
