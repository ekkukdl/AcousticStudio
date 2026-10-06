# -*- coding: utf-8 -*-
import sys
import os
os.environ["QT_API"] = "pyside6"
import numpy as np
import pyvista as pv
import vtk
vtk.vtkObject.GlobalWarningDisplayOff()
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import (QApplication, QSplitter, QMainWindow, QWidget, QVBoxLayout, 
                                     QHBoxLayout, QPushButton, QLabel, 
                                     QDoubleSpinBox, QSpinBox, QComboBox, QGroupBox, 
                                     QListWidget, QAbstractItemView, QSlider, QCheckBox,
                                     QScrollArea, QFormLayout, QListWidgetItem, QMessageBox, QFrame, QTabWidget)
from PySide6.QtCore import Qt, QObject, QEvent, QRect, QThread, Signal
import time

# --- 분리된 모듈 import ---
from acousticstudio.widgets import ResourceMonitorThread, MouseEventFilter, WheelBlocker, KeepOpenMenu
from acousticstudio.phase_engine import PhaseEngine, calculate_field_slice_numba
from acousticstudio.hardware import BOARD_PROFILES, HardwareController
from acousticstudio.state_manager import StateManager
from acousticstudio import file_io


class AcousticStudioMain(QMainWindow):
    def show_silent_msg(self, title, message, is_question=False, cancel_btn=False):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QStyle
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QIcon
        import os
        
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dlg.setMinimumWidth(420)
        
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'app_icon.jpg'))
        if os.path.exists(icon_path):
            dlg.setWindowIcon(QIcon(icon_path))
            
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(15)
        
        msg_layout = QHBoxLayout()
        msg_layout.setSpacing(15)
        
        icon_label = QLabel()
        if is_question:
            icon_pixmap = self.style().standardIcon(QStyle.SP_MessageBoxQuestion).pixmap(40, 40)
        elif "오류" in title or "실패" in title or "끊김" in title:
            icon_pixmap = self.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(40, 40)
        else:
            icon_pixmap = self.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(40, 40)
            
        icon_label.setPixmap(icon_pixmap)
        msg_layout.addWidget(icon_label, 0, Qt.AlignTop)
        
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 13px; line-height: 140%;")
        msg_layout.addWidget(lbl, 1, Qt.AlignVCenter)
        
        layout.addLayout(msg_layout)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        if is_question:
            btn_yes = QPushButton("예 (Yes)")
            btn_no = QPushButton("아니오 (No)")
            btn_yes.setMinimumWidth(75)
            btn_no.setMinimumWidth(75)
            btn_yes.clicked.connect(lambda: dlg.done(1))
            btn_no.clicked.connect(lambda: dlg.done(0))
            btn_layout.addWidget(btn_yes)
            btn_layout.addWidget(btn_no)
            if cancel_btn:
                btn_c = QPushButton("취소 (Cancel)")
                btn_c.setMinimumWidth(85)
                btn_c.clicked.connect(lambda: dlg.done(-1))
                btn_layout.addWidget(btn_c)
        else:
            btn_ok = QPushButton("확인")
            btn_ok.setMinimumWidth(80)
            btn_ok.clicked.connect(lambda: dlg.done(1))
            btn_layout.addWidget(btn_ok)
            
        layout.addLayout(btn_layout)
        
        from PySide6.QtWidgets import QApplication
        QApplication.beep()
        
        return dlg.exec()

    def __init__(self):
        super().__init__()
        
        # --- 분리된 모듈 인스턴스 초기화 ---
        self.phase_engine = PhaseEngine()
        self.hw_controller = HardwareController(self)
        self.state_mgr = StateManager(max_undo=20)
        
        from PySide6.QtGui import QIcon
        import os
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'app_icon.jpg'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.setWindowTitle("Acoustic Control Studio - PyVista 3D Viewer")
        self.resize(1400, 950)
        self.setMinimumSize(1120, 720)
        self.setStyleSheet("""
            QMainWindow { background: #f3f5f8; color: #1f2937; font-family: "Malgun Gothic"; font-size: 12px; }
            QMenuBar { background: #ffffff; color: #475569; padding: 4px 12px; border-bottom: 1px solid #e2e8f0; }
            QMenuBar::item { padding: 6px 9px; border-radius: 5px; }
            QMenuBar::item:selected, QMenu::item:selected { background: #edf2f6; color: #4f708d; }
            QMenu { background: #ffffff; color: #334155; border: 1px solid #dbe3ee; }
            QTabWidget::pane { border: 1px solid #dbe3ee; background: #f8fafc; border-radius: 8px; }
            QTabBar::tab { background: #f1f5f9; color: #64748b; padding: 10px 12px; margin: 0;
                            border: 1px solid #dbe3ee; border-bottom: none; font-weight: 600; }
            QTabBar::tab:first { border-top-left-radius: 8px; }
            QTabBar::tab:last { border-top-right-radius: 8px; }
            QTabBar::tab:selected { background: #6f8ea9; color: #ffffff; border-color: #6f8ea9; }
            QGroupBox { background: #ffffff; border: 1px solid #dbe3ee; border-radius: 9px;
                        margin-top: 14px; padding: 12px 9px 8px 9px; color: #334155; font-weight: 700; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #5e7f9d; }
            QLabel { color: #475569; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QListWidget { background: #ffffff;
                        color: #1e293b; border: 1px solid #cbd5e1; border-radius: 6px; min-height: 25px; padding: 1px 6px; }
            QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus { border-color: #8ca7bd; }
            QComboBox { background: #edf3f7; color: #27445d; border: 1px solid #9eb3c4;
                        border-radius: 6px; min-height: 25px; padding: 1px 30px 1px 7px; font-weight: 600; }
            QComboBox:hover, QComboBox:focus { background: #e4edf3; border-color: #7897af; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 25px;
                                   background: #dbe6ee; border-left: 1px solid #b5c6d3;
                                   border-top-right-radius: 5px; border-bottom-right-radius: 5px; }
            QComboBox::down-arrow { image: url(assets/chevron_down.svg); width: 12px; height: 8px; margin-right: 7px; }
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { width: 0px; border: none; }
            QComboBox QAbstractItemView { background: #ffffff; color: #1e293b; selection-background-color: #e6eef5; selection-color: #3f5f7b; border: 1px solid #cbd5e1; }
            QListWidget::item { padding: 5px; border-radius: 4px; }
            QListWidget::item:selected { background: #e6eef5; color: #3f5f7b; }
            QPushButton { background: #ffffff; color: #334155; border: 1px solid #cbd5e1; border-radius: 6px;
                          padding: 6px 10px; font-weight: 600; }
            QPushButton:hover { background: #edf2f6; color: #4f708d; border-color: #9fb4c6; }
            QPushButton:disabled { background: #f1f5f9; color: #94a3b8; border-color: #e2e8f0; }
            QCheckBox { color: #475569; spacing: 6px; }
            QStatusBar { background: #ffffff; color: #64748b; border-top: 1px solid #dbe3ee; }
            QScrollArea { background: transparent; }
            QScrollArea::viewport, QWidget#settingsPage { background: #f8fafc; }
        """)
        # File Menu
        from PySide6.QtGui import QAction
        from PySide6.QtCore import Qt
        menubar = self.menuBar()
        file_menu = menubar.addMenu("파일")
        
        new_action = QAction("새로 만들기 (New)", self)
        new_action.setShortcut("Ctrl+N")
        new_action.setShortcutContext(Qt.ApplicationShortcut)
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()
        
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
        
        edit_menu = menubar.addMenu("편집")
        
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
        tools_menu = self.menuBar().addMenu("도구")
        lib_mgr_action = tools_menu.addAction("라이브러리 관리자 (Library Manager)")
        lib_mgr_action.triggered.connect(self.open_library_manager)
        kwave_sim_action = tools_menu.addAction("k-Wave 기구물 음향 시뮬레이션 (Reflector/Tunnel)...")
        kwave_sim_action.triggered.connect(self.open_kwave_simulation)

        view_menu = self.menuBar().addMenu("보기")

        self.board_menu = self.menuBar().addMenu("보드")
        
        from PySide6.QtCore import QSettings
        self.settings = QSettings("AcousticStudioTeam", "AcousticStudio")
        
        self.show_cpu = self.settings.value("show_cpu", False, type=bool)
        self.show_gpu = self.settings.value("show_gpu", False, type=bool)
        
        display_settings_menu = KeepOpenMenu("화면 설정 (Display Settings)", self)
        view_menu.addMenu(display_settings_menu)
        
        self.action_show_cpu = QAction("CPU 사용량 표시", self)
        self.action_show_cpu.setCheckable(True)
        self.action_show_cpu.setChecked(self.show_cpu)
        self.action_show_cpu.triggered.connect(self.toggle_cpu_monitoring)
        display_settings_menu.addAction(self.action_show_cpu)
        
        self.action_show_gpu = QAction("GPU 사용량 표시", self)
        self.action_show_gpu.setCheckable(True)
        self.action_show_gpu.setChecked(self.show_gpu)
        self.action_show_gpu.triggered.connect(self.toggle_gpu_monitoring)
        display_settings_menu.addAction(self.action_show_gpu)

        
        # Initialize undo stack
        self.push_state()
        self._initial_state = self.get_state()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 10, 16, 12)
        main_layout.setSpacing(10)

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
        def create_settings_scroll():
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setStyleSheet("""
                QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px; }
                QScrollBar::handle:vertical { background: #94a3b8; border-radius: 4px; min-height: 28px; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            """)
            page = QWidget()
            page.setObjectName("settingsPage")
            scroll.setWidget(page)
            return scroll, page

        workspace_tabs = QTabWidget()
        workspace_tabs.setDocumentMode(True)
        workspace_tabs.setMinimumWidth(400)
        design_scroll, design_page = create_settings_scroll()
        field_scroll, field_page = create_settings_scroll()
        motion_scroll, motion_page = create_settings_scroll()
        design_layout, field_tab_layout, motion_layout = QVBoxLayout(design_page), QVBoxLayout(field_page), QVBoxLayout(motion_page)
        for page_layout in (design_layout, field_tab_layout, motion_layout):
            page_layout.setAlignment(Qt.AlignTop)
            page_layout.setContentsMargins(10, 8, 10, 10)
            page_layout.setSpacing(9)
        workspace_tabs.addTab(design_scroll, "구성")
        workspace_tabs.addTab(field_scroll, "음장")
        workspace_tabs.addTab(motion_scroll, "궤적")
        workspace_tabs.tabBar().setExpanding(True)
        
        from PySide6.QtWidgets import QSplitter
        from PySide6.QtCore import Qt
        
        # --- Create Left Panel for 3D Viewer & Hardware Control ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Hardware Control (Top Bar)
        hw_top_bar = QWidget()
        hw_top_bar.setFixedHeight(54)
        hw_top_bar.setObjectName("hardwareBar")
        hw_top_bar.setStyleSheet("QWidget#hardwareBar { background: #ffffff; border: 1px solid #dbe3ee; border-radius: 8px; }")
        hw_layout = QHBoxLayout(hw_top_bar)
        hw_layout.setContentsMargins(10, 5, 10, 5)
        
        import serial.tools.list_ports
        self.serial_port_cb = QComboBox()
        self.serial_port_cb.setMinimumWidth(80) # Fix narrow COM port combobox
        from PySide6.QtWidgets import QStyle
        self.btn_refresh_ports = QPushButton()
        self.btn_refresh_ports.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.btn_refresh_ports.setFixedSize(32, 30)
        self.btn_refresh_ports.setToolTip("사용 가능한 포트 새로고침")
        self.btn_refresh_ports.clicked.connect(self.refresh_ports)
        
        self.serial_baud_cb = QComboBox()
        baud_rates = ["9600", "19200", "38400", "57600", "115200", "230400", "250000", "500000", "1000000"]
        self.serial_baud_cb.addItems(baud_rates)
        self.serial_baud_cb.setCurrentText("115200")

        self.board_profile_cb = QComboBox()
        for profile in BOARD_PROFILES.values():
            self.board_profile_cb.addItem(profile.label, userData=profile.key)
        self.board_profile_cb.setToolTip(
            "선택한 펌웨어의 채널 수·프레임·권장 보레이트를 적용합니다. "
            "실물 보드 연결 전에는 Legacy 프로파일을 사용하세요."
        )
        self.board_profile_cb.currentIndexChanged.connect(self.change_board_profile)
        from PySide6.QtGui import QActionGroup
        self.board_profile_actions = {}
        board_profile_group = QActionGroup(self)
        board_profile_group.setExclusive(True)
        for profile in BOARD_PROFILES.values():
            action = QAction(profile.label, self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, key=profile.key: self.select_board_profile(key)
            )
            board_profile_group.addAction(action)
            self.board_menu.addAction(action)
            self.board_profile_actions[profile.key] = action
        self.board_profile_cb.currentIndexChanged.connect(self.sync_board_profile_menu)
        self.sync_board_profile_menu()

        self.btn_connect_hw = QPushButton("연결")
        self.btn_send_phase = QPushButton("위상 전송")
        self.btn_send_phase.setEnabled(False)
        self.btn_connect_hw.clicked.connect(self.connect_hw)
        self.btn_send_phase.clicked.connect(self.send_phase_data)
        
        from PySide6.QtCore import QTimer
        # HardwareController 시그널 연결 (UI 업데이트용)
        self.hw_controller.disconnected.connect(self.handle_hw_disconnect)
        self.hw_controller.send_failed.connect(lambda msg: self.show_silent_msg("하드웨어 연결 실패", msg))
        
        self.refresh_ports()
        
        self.chk_realtime_send = QCheckBox("실시간 전송")
        self.chk_realtime_send.setEnabled(False)
        self.chk_realtime_send.setToolTip("활성화 시, 화면에서 점을 움직이면 연결된 보드로 즉시 위상 데이터가 전송됩니다.")
        
        hw_layout.addWidget(QLabel("하드웨어 제어 (USB Port):"))
        hw_layout.addWidget(self.serial_port_cb)
        hw_layout.addWidget(self.btn_refresh_ports)
        hw_layout.addWidget(QLabel("Baud Rate:"))
        hw_layout.addWidget(self.serial_baud_cb)
        hw_layout.addWidget(self.btn_connect_hw)
        hw_layout.addWidget(self.btn_send_phase)
        hw_layout.addWidget(self.chk_realtime_send)
        hw_layout.addStretch()
        
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
        self.compute_mode_cb.addItem("GPU: 범용 그래픽 (매우 빠름) (Taichi 가속)")
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
        self.splitter.addWidget(workspace_tabs)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([1180, 520])
        
        main_layout.addWidget(self.splitter)
        
        # [1. Transform Properties (?占쏀깮??媛앹껜 ?占쎈룞/?占쎌쟾)] - ?占쎈줈 異뷂옙???
        transform_group = QGroupBox("선택 객체")
        
        
        self.sel_x = QDoubleSpinBox(); self.sel_x.setRange(-2000, 2000)
        self.sel_y = QDoubleSpinBox(); self.sel_y.setRange(-2000, 2000)
        self.sel_z = QDoubleSpinBox(); self.sel_z.setRange(-2000, 2000)
        self.sel_rx = QDoubleSpinBox(); self.sel_rx.setRange(-360, 360)
        self.sel_ry = QDoubleSpinBox(); self.sel_ry.setRange(-360, 360)
        self.sel_rz = QDoubleSpinBox(); self.sel_rz.setRange(-360, 360)
        
        from PySide6.QtWidgets import QGridLayout
        t_layout = QFormLayout()
        transform_pos = QHBoxLayout()
        for name, spin in (("X", self.sel_x), ("Y", self.sel_y), ("Z", self.sel_z)):
            transform_pos.addWidget(QLabel(name))
            transform_pos.addWidget(spin)
        transform_rot = QHBoxLayout()
        for name, spin in (("X", self.sel_rx), ("Y", self.sel_ry), ("Z", self.sel_rz)):
            transform_rot.addWidget(QLabel(name))
            transform_rot.addWidget(spin)
        t_layout.addRow("이동 (mm)", transform_pos)
        t_layout.addRow("회전 (°)", transform_rot)
        transform_group.setLayout(t_layout)
        design_layout.addWidget(transform_group)
        # Properties Group
        self.prop_group = QGroupBox("선택 항목")
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
        design_layout.addWidget(self.prop_group)
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
        array_group = QGroupBox("배열 구성")
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
        gen_grid = QFormLayout()
        array_pos = QHBoxLayout()
        for name, spin in (("X", self.gen_pos_x), ("Y", self.gen_pos_y), ("Z", self.gen_pos_z)):
            array_pos.addWidget(QLabel(name))
            array_pos.addWidget(spin)
        array_rot = QHBoxLayout()
        for name, spin in (("X", self.gen_rot_x), ("Y", self.gen_rot_y), ("Z", self.gen_rot_z)):
            array_rot.addWidget(QLabel(name))
            array_rot.addWidget(spin)
        gen_grid.addRow("위치 (mm)", array_pos)
        gen_grid.addRow("회전 (°)", array_rot)
        array_layout.addLayout(gen_grid)
        
        self.add_array_btn = QPushButton("배열 3D 렌더링 생성")
        self.add_array_btn.clicked.connect(self._hooked_generate_array)
        self.clear_btn = QPushButton("전체 초기화")
        self.clear_btn.clicked.connect(self._hooked_clear_view)
        
        array_layout.addWidget(self.add_array_btn)
        array_layout.addWidget(self.clear_btn)
        array_group.setLayout(array_layout)
        design_layout.addWidget(array_group)
        
        # [3. 而⑦듃占??占쎌씤??(?占쏙옙? 洹몃９]
        points_group = QGroupBox("제어점")
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
        self.points_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.points_list.itemSelectionChanged.connect(self.on_point_selected)
        points_layout.addWidget(self.points_list)
        
        btn_layout = QHBoxLayout()
        self.add_pt_btn = QPushButton("제어점 추가")
        self.add_pt_btn.clicked.connect(self._hooked_add_control_point)
        self.del_pt_btn = QPushButton("제어점 삭제")
        self.del_pt_btn.clicked.connect(self._hooked_del_control_point)
        btn_layout.addWidget(self.add_pt_btn)
        btn_layout.addWidget(self.del_pt_btn)
        points_layout.addLayout(btn_layout)
        
        self.auto_calc_cb = QCheckBox("제어점 이동 시 실시간 위상 업데이트")
        self.auto_calc_cb.setChecked(True) # 湲곕낯쟻쑝濡 耳쒕몺
        points_layout.addWidget(self.auto_calc_cb)
        
        points_group.setLayout(points_layout)
        design_layout.addWidget(points_group)
        
        # [4. ?占쎈옪 占??占쏙옙??占쎌씠??洹몃９]
        field_group = QGroupBox("위상 계산")
        field_layout = QFormLayout()
        self.trap_type_cb = QComboBox()
        self.trap_type_cb.addItems(["Twin Trap", "Vortex Trap"])
        field_layout.addRow("트랩 종류:", self.trap_type_cb)
        
        self.run_btn = QPushButton("Calculate Phase (위상 계산 및 시각화)")
        self.run_btn.setStyleSheet("background-color: #6f8ea9; color: white; height: 30px; font-weight: bold;")
        self.run_btn.clicked.connect(self.simulate_colors)
        field_layout.addRow(self.run_btn)
        field_group.setLayout(field_layout)
        field_tab_layout.addWidget(field_group)
        
        # [5. ?占쎌븬 ?占쎄컖??洹몃９]
        visual_group = QGroupBox("음장 분석")
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
        self.show_field_btn.setStyleSheet("background-color: #6f8ea9; color: white; height: 30px; font-weight: bold;")
        self.show_field_btn.setCheckable(True)
        self.show_field_btn.clicked.connect(self.toggle_field_slice)
        show_field_lyt = QHBoxLayout()
        show_field_lyt.addWidget(self.show_field_btn)
        self.field_mode_combo = QComboBox()
        self.field_mode_combo.addItems(["음압 분포 (Pressure Magnitude)", "위상 분포 (Phase Angle)", "순간 파면 (Instantaneous Wavefront)"])
        self.field_mode_combo.currentIndexChanged.connect(self.update_field_slice)
        show_field_lyt.addWidget(self.field_mode_combo)
        visual_layout.addLayout(show_field_lyt)
        
        self.btn_kwave_sim = QPushButton("k-Wave 기구물 음향 시뮬레이션 (Reflector/Tunnel)")
        self.btn_kwave_sim.setStyleSheet("background-color: #ffffff; color: #5e7f9d; height: 30px; font-weight: bold; border: 1px solid #b8c9d7; border-radius: 6px;")
        self.btn_kwave_sim.setToolTip("상단 반사판, 좌우 터널, 챔버 및 다양한 재질(아크릴, 알루미늄, SUS 등)에 따른 k-Wave FDTD 음향 전파 해석")
        self.btn_kwave_sim.clicked.connect(self.open_kwave_simulation)
        visual_layout.addWidget(self.btn_kwave_sim)
        
        visual_group.setLayout(visual_layout)
        field_tab_layout.addWidget(visual_group)
        
        # [6. Trajectory Generation (고급 궤적 생성)]
        trajectory_group = QGroupBox("궤적")
        trajectory_layout = QVBoxLayout()
        
        from PySide6.QtWidgets import QGridLayout
        
        # Trajectory Type
        type_lyt = QHBoxLayout()
        type_lyt.addWidget(QLabel("궤적 종류:"))
        self.traj_type_cb = QComboBox()
        self.traj_type_cb.addItems(["선형 (Linear)", "원형 (Circular)", "8자형 (Figure-8)"])
        type_lyt.addWidget(self.traj_type_cb)
        
        self.traj_param_label = QLabel("반경/크기 (mm):")
        self.traj_param_spin = QDoubleSpinBox()
        self.traj_param_spin.setRange(1.0, 1000.0)
        self.traj_param_spin.setValue(20.0)
        
        self.traj_param_label.hide()
        self.traj_param_spin.hide()
        
        type_lyt.addWidget(self.traj_param_label)
        type_lyt.addWidget(self.traj_param_spin)
        type_lyt.addStretch()
        trajectory_layout.addLayout(type_lyt)
        
        def on_traj_type_changed(idx):
            if idx == 0:
                self.traj_param_label.hide()
                self.traj_param_spin.hide()
                self.traj_end_label_1.show(); self.traj_end_label_x.show(); self.traj_end_label_y.show(); self.traj_end_label_z.show()
                self.traj_end_x.show(); self.traj_end_y.show(); self.traj_end_z.show()
                self.btn_set_end.show()
            else:
                self.traj_param_label.show()
                self.traj_param_spin.show()
                self.traj_end_label_1.hide(); self.traj_end_label_x.hide(); self.traj_end_label_y.hide(); self.traj_end_label_z.hide()
                self.traj_end_x.hide(); self.traj_end_y.hide(); self.traj_end_z.hide()
                self.btn_set_end.hide()
            self.update_traj_preview()
                
        self.traj_type_cb.currentIndexChanged.connect(on_traj_type_changed)
        
        t_grid = QGridLayout()
        self.traj_start_x = QDoubleSpinBox(); self.traj_start_x.setRange(-2000, 2000)
        self.traj_start_y = QDoubleSpinBox(); self.traj_start_y.setRange(-2000, 2000)
        self.traj_start_z = QDoubleSpinBox(); self.traj_start_z.setRange(-2000, 2000)
        
        self.traj_end_x = QDoubleSpinBox(); self.traj_end_x.setRange(-2000, 2000)
        self.traj_end_y = QDoubleSpinBox(); self.traj_end_y.setRange(-2000, 2000)
        self.traj_end_z = QDoubleSpinBox(); self.traj_end_z.setRange(-2000, 2000)

        self.traj_param_spin.valueChanged.connect(self.update_traj_preview)
        self.traj_start_x.valueChanged.connect(self.update_traj_preview)
        self.traj_start_y.valueChanged.connect(self.update_traj_preview)
        self.traj_start_z.valueChanged.connect(self.update_traj_preview)
        self.traj_end_x.valueChanged.connect(self.update_traj_preview)
        self.traj_end_y.valueChanged.connect(self.update_traj_preview)
        self.traj_end_z.valueChanged.connect(self.update_traj_preview)

        self.btn_set_start = QPushButton("선택 객체를 시작(중심)점으로")
        self.btn_set_start.clicked.connect(self.set_traj_start_from_selected)
        self.btn_set_end = QPushButton("선택 객체를 목표점으로 설정")
        self.btn_set_end.clicked.connect(self.set_traj_end_from_selected)

        t_grid.addWidget(QLabel("시작/중심:"), 0, 0)
        t_grid.addWidget(QLabel("X:"), 0, 1); t_grid.addWidget(self.traj_start_x, 0, 2)
        t_grid.addWidget(QLabel("Y:"), 0, 3); t_grid.addWidget(self.traj_start_y, 0, 4)
        t_grid.addWidget(QLabel("Z:"), 0, 5); t_grid.addWidget(self.traj_start_z, 0, 6)
        t_grid.addWidget(self.btn_set_start, 1, 0, 1, 7)

        self.traj_end_label_1 = QLabel("목표점:")
        self.traj_end_label_x = QLabel("X:")
        self.traj_end_label_y = QLabel("Y:")
        self.traj_end_label_z = QLabel("Z:")
        
        t_grid.addWidget(self.traj_end_label_1, 2, 0)
        t_grid.addWidget(self.traj_end_label_x, 2, 1); t_grid.addWidget(self.traj_end_x, 2, 2)
        t_grid.addWidget(self.traj_end_label_y, 2, 3); t_grid.addWidget(self.traj_end_y, 2, 4)
        t_grid.addWidget(self.traj_end_label_z, 2, 5); t_grid.addWidget(self.traj_end_z, 2, 6)
        t_grid.addWidget(self.btn_set_end, 3, 0, 1, 7)
        
        trajectory_layout.addLayout(t_grid)

        res_lyt = QHBoxLayout()
        res_lyt.addWidget(QLabel("궤적 해상도:"))
        self.traj_steps = QSpinBox()
        self.traj_steps.setRange(2, 500)
        self.traj_steps.setValue(20)
        res_lyt.addWidget(self.traj_steps)

        res_lyt.addWidget(QLabel("간격 (ms):"))
        self.traj_delay = QSpinBox()
        self.traj_delay.setRange(0, 5000)
        self.traj_delay.setValue(50)
        res_lyt.addWidget(self.traj_delay)

        self.traj_steps.valueChanged.connect(self.update_traj_preview)
        self.traj_delay.valueChanged.connect(self.update_traj_preview)

        res_lyt.addStretch()
        trajectory_layout.addLayout(res_lyt)

        chk_lyt = QHBoxLayout()
        self.chk_show_traj = QCheckBox("궤적 보이기")
        self.chk_show_traj.setChecked(True)
        self.chk_show_traj.stateChanged.connect(self.toggle_trajectory_visibility)
        chk_lyt.addWidget(self.chk_show_traj)

        trajectory_layout.addLayout(chk_lyt)
        
        self.chk_optim_traj = QCheckBox("물리 연산 기반 궤적 최적화 (levitate)")
        self.chk_optim_traj.setToolTip("포획력(Stiffness)을 계산하여 트랩이 약한 구간은 속도를 늦추어 물체의 추락을 방지합니다.")
        self.chk_optim_traj.stateChanged.connect(self.update_traj_preview)
        trajectory_layout.addWidget(self.chk_optim_traj)

        # Trajectory Real-time Preview Clean Single Label
        self.lbl_traj_preview_inline = QLabel("예상 소요 시간: 1.00초")
        self.lbl_traj_preview_inline.setStyleSheet("color: #5e7f9d; font-weight: bold; font-size: 11px; margin-top: 4px; margin-bottom: 2px;")
        self.lbl_traj_preview_inline.setAlignment(Qt.AlignCenter)
        trajectory_layout.addWidget(self.lbl_traj_preview_inline)

        self.btn_gen_traj = QPushButton("새로운 궤적 생성")
        self.btn_gen_traj.setStyleSheet("background-color: #6f8ea9; color: white; font-weight: bold; height: 32px; border-radius: 6px; margin-bottom: 5px;")
        self.btn_gen_traj.clicked.connect(self.generate_trajectory)
        trajectory_layout.addWidget(self.btn_gen_traj)
        
        # Trajectory List Moved Here
        list_lbl = QLabel("생성된 궤적 목록:")
        list_lbl.setStyleSheet("font-weight: bold; margin-top: 5px;")
        trajectory_layout.addWidget(list_lbl)
        
        self.traj_list = QListWidget()
        self.traj_list.setMinimumHeight(100)
        self.traj_list.setMaximumHeight(150)
        self.traj_list.setStyleSheet("border: 1px solid #ccc; border-radius: 4px;")
        trajectory_layout.addWidget(self.traj_list)
        self.traj_list.itemClicked.connect(self.on_traj_item_clicked)
        
        # Clear Buttons Moved Here
        self.btn_clear_sel_traj = QPushButton("선택 궤적 삭제")
        self.btn_clear_sel_traj.setStyleSheet("height: 28px; border-radius: 6px; background-color: #fff5f5; color: #dc2626; border: 1px solid #fecaca;")
        self.btn_clear_sel_traj.clicked.connect(self.clear_selected_trajectory)
        
        self.btn_clear_all_traj = QPushButton("모든 궤적 삭제")
        self.btn_clear_all_traj.setStyleSheet("height: 28px; border-radius: 6px; background-color: #fff5f5; color: #dc2626; border: 1px solid #fecaca;")
        self.btn_clear_all_traj.clicked.connect(self.clear_all_trajectories)

        btn_lyt = QHBoxLayout()
        btn_lyt.setSpacing(5)
        btn_lyt.addWidget(self.btn_clear_sel_traj)
        btn_lyt.addWidget(self.btn_clear_all_traj)
        trajectory_layout.addLayout(btn_lyt)

        self.btn_export_traj = QPushButton("선택 궤적 데이터 내보내기")
        self.btn_export_traj.setStyleSheet("height: 28px; border-radius: 6px; background-color: #6f8ea9; color: white; font-weight: bold; margin-top: 2px;")
        self.btn_export_traj.setToolTip("선택한 궤적의 위상 데이터를 C헤더(.h), CSV(.csv), 또는 하드웨어 바이너리(.bin) 파일로 내보냅니다.")
        self.btn_export_traj.clicked.connect(self.export_selected_trajectory)
        trajectory_layout.addWidget(self.btn_export_traj)

        # Trajectory Physical Diagnosis Summary Card
        self.traj_diag_frame = QFrame()
        self.traj_diag_frame.setStyleSheet("QFrame { background-color: #f7f9fa; border: 1px solid #d0d7de; border-radius: 5px; padding: 4px; margin-top: 6px; }")
        diag_lyt = QVBoxLayout(self.traj_diag_frame)
        diag_lyt.setContentsMargins(6, 4, 6, 4)
        diag_lyt.setSpacing(2)

        self.lbl_diag_title = QLabel("물리 안정성 진단: 선택된 궤적 없음")
        self.lbl_diag_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #24292f;")
        diag_lyt.addWidget(self.lbl_diag_title)

        self.lbl_diag_desc = QLabel("안내: 궤적을 선택하거나 새로 생성하면 상세 진단이 표시됩니다.")
        self.lbl_diag_desc.setStyleSheet("color: #57606a; font-size: 10px;")
        self.lbl_diag_desc.setWordWrap(True)
        diag_lyt.addWidget(self.lbl_diag_desc)

        trajectory_layout.addWidget(self.traj_diag_frame)

        # Media Player Buttons UI Improved
        media_header_lyt = QHBoxLayout()
        media_label = QLabel("시뮬레이션 재생 컨트롤:")
        media_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        media_header_lyt.addWidget(media_label)
        
        self.lbl_traj_time = QLabel("예상 시간: 3.00초 (+렌더링)")
        self.lbl_traj_time.setStyleSheet("color: #5e7f9d; font-weight: bold; margin-top: 10px;")
        self.lbl_traj_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        media_header_lyt.addStretch()
        media_header_lyt.addWidget(self.lbl_traj_time)
        
        trajectory_layout.addLayout(media_header_lyt)
        
        media_lyt = QHBoxLayout()
        media_lyt.setSpacing(5)
        
        from PySide6.QtWidgets import QStyle
        
        self.btn_traj_reset = QPushButton()
        self.btn_traj_reset.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.btn_traj_reset.setToolTip("원래 위치로 정지")
        self.btn_traj_reset.setFixedHeight(30)
        self.btn_traj_reset.clicked.connect(self.reset_traj_playback)
        media_lyt.addWidget(self.btn_traj_reset)
        
        self.btn_traj_bw = QPushButton()
        self.btn_traj_bw.setIcon(self.style().standardIcon(QStyle.SP_MediaSeekBackward))
        self.btn_traj_bw.setToolTip("뒤로 재생")
        self.btn_traj_bw.setFixedHeight(30)
        self.btn_traj_bw.clicked.connect(lambda: self.start_traj_playback(-1))
        media_lyt.addWidget(self.btn_traj_bw)
        
        self.btn_traj_play = QPushButton()
        self.btn_traj_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_traj_play.setToolTip("재생")
        self.btn_traj_play.setFixedHeight(30)
        self.btn_traj_play.clicked.connect(lambda: self.start_traj_playback(1))
        media_lyt.addWidget(self.btn_traj_play)
        
        self.btn_traj_pause = QPushButton()
        self.btn_traj_pause.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.btn_traj_pause.setToolTip("일시정지")
        self.btn_traj_pause.setFixedHeight(30)
        self.btn_traj_pause.clicked.connect(self.pause_traj_playback)
        media_lyt.addWidget(self.btn_traj_pause)
        
        trajectory_layout.addLayout(media_lyt)

        trajectory_group.setLayout(trajectory_layout)
        motion_layout.addWidget(trajectory_group)

        design_layout.addStretch(1)
        field_tab_layout.addStretch(1)
        motion_layout.addStretch(1)
        # Hardware UI moved to top bar
        
        self.field_actors = [] # ?占쎌쨷 ?占쎈씪?占쎌뒪 ?占쏀꽣占?愿由ы븯占??占쏀븳 由ъ뒪??        
        
        self._is_updating_ui = False
        self._sel_base_centroid = [0.0, 0.0, 0.0]
        self._sel_base_rot = [0.0, 0.0, 0.0]
        # Apply wheel blocker AFTER all widgets are created
        self.wheel_blocker = WheelBlocker(design_scroll, self)
        def sync_active_scroll(index):
            self.wheel_blocker.scroll_area = (design_scroll, field_scroll, motion_scroll)[index]
        workspace_tabs.currentChanged.connect(sync_active_scroll)
        widgets = self.findChildren(QDoubleSpinBox) + self.findChildren(QSpinBox) + self.findChildren(QComboBox) + self.findChildren(QSlider)
        for widget in widgets:
            widget.installEventFilter(self.wheel_blocker)
            
        self._last_saved_state = self.get_state(for_file=True)
        self.update_traj_preview()
        
        self.statusBar().showMessage("준비 완료")
        self.resource_label = QLabel("")
        self.resource_label.setStyleSheet("color: #555; font-weight: bold; padding-right: 10px;")
        self.statusBar().addPermanentWidget(self.resource_label)
        
        self.resource_monitor = ResourceMonitorThread(self)
        self.resource_monitor.show_cpu = self.show_cpu
        self.resource_monitor.show_gpu = self.show_gpu
        self.resource_monitor.updated.connect(self.on_resource_updated)
        self.resource_monitor.start()
    
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
    def select_board_profile(self, profile_key):
        """Apply the board profile selected from the top-level board menu."""
        index = self.board_profile_cb.findData(profile_key)
        if index >= 0:
            self.board_profile_cb.setCurrentIndex(index)

    def sync_board_profile_menu(self, *_):
        """Keep the checked board-menu item aligned with the active profile."""
        if not hasattr(self, "board_profile_actions"):
            return
        active_key = self.board_profile_cb.currentData()
        action = self.board_profile_actions.get(active_key)
        if action:
            action.setChecked(True)

    def refresh_ports(self):
        self.serial_port_cb.clear()
        ports = self.hw_controller.refresh_ports()
        for p in ports:
            self.serial_port_cb.addItem(p, userData=p)
        if not ports:
            self.serial_port_cb.addItem("No Ports Found")
    def change_board_profile(self):
        profile_key = self.board_profile_cb.currentData()
        if not profile_key:
            return
        try:
            profile = self.hw_controller.set_board_profile(profile_key)
            self.serial_baud_cb.setCurrentText(str(profile.baud_rate))
        except RuntimeError as e:
            self.show_silent_msg("보드 프로파일", str(e))
            self.board_profile_cb.blockSignals(True)
            current_index = self.board_profile_cb.findData(self.hw_controller.board_profile.key)
            self.board_profile_cb.setCurrentIndex(current_index)
            self.board_profile_cb.blockSignals(False)
    def connect_hw(self):
        if not self.hw_controller.is_connected():
            port = self.serial_port_cb.currentText()
            if port == "No Ports Found" or not port:
                self.show_silent_msg("Error", "No valid COM port selected.")
                return
            try:
                baud = int(self.serial_baud_cb.currentText())
            except ValueError:
                self.show_silent_msg("Error", "Invalid Baud Rate.")
                return
            if self.hw_controller.connect(port, baud):
                self.btn_connect_hw.setText("연결 해제")
                self.btn_send_phase.setEnabled(True)
                if hasattr(self, 'chk_realtime_send'):
                    self.chk_realtime_send.setEnabled(True)
            else:
                pass  # hw_controller emits send_failed signal
        else:
            self.hw_controller.disconnect()
            self.btn_connect_hw.setText("연결")
            self.btn_send_phase.setEnabled(False)
            if hasattr(self, 'chk_realtime_send'):
                self.chk_realtime_send.setEnabled(False)
    def send_phase_data(self):
        if not self.hw_controller.is_connected():
            return
        try:
            phases = [getattr(act, '_phase', 0.0) for act in self.transducer_actors]
            if not phases:
                return
            self.hw_controller.send_phases(phases)
        except ValueError as e:
            self.show_silent_msg("위상 전송", str(e))
        except Exception as e:
            print(f"HW Send Error: {e}")
    def handle_hw_disconnect(self, reason=""):
        """UI 업데이트 — HardwareController.disconnected 시그널에 연결"""
        self.btn_connect_hw.setText("연결")
        self.btn_send_phase.setEnabled(False)
        if hasattr(self, 'chk_realtime_send'):
            self.chk_realtime_send.setEnabled(False)
        if reason:
            self.show_silent_msg("하드웨어 연결 끊김", reason)
    def check_hw_health(self):
        # Health check is now handled by HardwareController's internal timer
        pass
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
            self.prop_type_lbl.setText("제어점")
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
                self.plotter.remove_actor(act, render=False)
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
                    self.plotter.remove_actor(act, render=False)
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
                self.plotter.remove_actor(actor, render=False)
            else:
                # Check if it's a control point
                for i, cp in enumerate(self.control_points):
                    if cp["actor"] == actor:
                        self.plotter.remove_actor(actor, render=False)
                        del self.control_points[i]
                        self.points_list.takeItem(i)
                        break
                        
        self.selected_actors.clear()
        self.update_ui_from_selection()
        self.update_gizmo()
        self.plotter.render()
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.delete_selected_objects()
        super().keyPressEvent(event)
    def closeEvent(self, event):
        if self.check_unsaved_changes():
            if hasattr(self, 'resource_monitor'):
                self.resource_monitor.stop()
            event.accept()
        else:
            event.ignore()
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
        name = f"제어점 {idx+1}"
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
        items = self.points_list.selectedItems()
        if not items: return
        
        # Sort rows in descending order to avoid shifting issues when deleting
        rows = sorted([self.points_list.row(item) for item in items], reverse=True)
        
        for idx in rows:
            if idx >= 0 and idx < len(self.control_points):
                actor = self.control_points[idx]["actor"]
                if actor in self.selected_actors:
                    self.selected_actors.remove(actor)
                self.plotter.remove_actor(actor, render=False)
                del self.control_points[idx]
                self.points_list.takeItem(idx)
        
        self.update_gizmo()
        self.plotter.render()
    def on_point_selected(self):
        for act in self.selected_actors:
            if hasattr(act, '_original_color'):
                act.prop.color = act._original_color
        self.selected_actors.clear()
        
        for item in self.points_list.selectedItems():
            idx = self.points_list.row(item)
            if 0 <= idx < len(self.control_points):
                act = self.control_points[idx]["actor"]
                if act not in self.selected_actors:
                    self.selected_actors.append(act)
                    act.prop.color = "pink"
                    
        self.update_gizmo()
        self.update_ui_from_selection()
        self.plotter.render()
    def get_state(self, for_file=False):
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
        if for_file and hasattr(self, 'board_profile_cb'):
            data['board_profile'] = self.board_profile_cb.currentData()
        
        if for_file:
            # Save field slices ONLY for file save (so they don't break Undo/Redo)
            data['show_field'] = self.show_field_btn.isChecked() if hasattr(self, 'show_field_btn') else False
            data['field_mode'] = self.field_mode_combo.currentText() if hasattr(self, 'field_mode_combo') else ""
            data['xz_check'] = self.xz_check.isChecked() if hasattr(self, 'xz_check') else False
            data['xz_slider'] = self.xz_slider.value() if hasattr(self, 'xz_slider') else 0
            data['yz_check'] = self.yz_check.isChecked() if hasattr(self, 'yz_check') else False
            data['yz_slider'] = self.yz_slider.value() if hasattr(self, 'yz_slider') else 0
            data['xy_check'] = self.xy_check.isChecked() if hasattr(self, 'xy_check') else False
            data['xy_slider'] = self.xy_slider.value() if hasattr(self, 'xy_slider') else 0
            
            # Save generated trajectory waypoints if they exist
            if hasattr(self, 'traj_points_data'):
                data['traj_points_data'] = [pt.tolist() for pt in self.traj_points_data] if type(self.traj_points_data).__name__ == 'ndarray' else self.traj_points_data
        
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
            
        # Trajectory
        if hasattr(self, 'traj_start_x'):
            data['traj_start'] = [self.traj_start_x.value(), self.traj_start_y.value(), self.traj_start_z.value()]
            data['traj_end'] = [self.traj_end_x.value(), self.traj_end_y.value(), self.traj_end_z.value()]
            data['traj_steps'] = self.traj_steps.value()
            data['traj_delay'] = self.traj_delay.value()
            data['traj_optim'] = self.chk_optim_traj.isChecked()
            data['traj_show'] = self.chk_show_traj.isChecked()
        
        return data
    def set_state(self, data):
        import pyvista as pv
        import vtk

        # A board profile describes a physical protocol and is persisted with a
        # project, but never changed while a live board is connected.
        profile_key = data.get('board_profile')
        if profile_key in BOARD_PROFILES and not self.hw_controller.is_connected():
            profile_index = self.board_profile_cb.findData(profile_key)
            if profile_index >= 0:
                self.board_profile_cb.setCurrentIndex(profile_index)
        
        # Block signals to prevent UI triggers (e.g. generate_array) while loading state
        ui_elements = [
            getattr(self, 'transducer_type_cb', None), getattr(self, 'array_type_cb', None), 
            getattr(self, 'spacing_spin', None), getattr(self, 'trap_type_cb', None), 
            getattr(self, 'grid_x_spin', None), getattr(self, 'grid_y_spin', None), 
            getattr(self, 'point_size_spin', None), getattr(self, 'prop_radius_spin', None)
        ]
        for ui in ui_elements:
            if ui: ui.blockSignals(True)
            
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
        
        for ui in ui_elements:
            if ui: ui.blockSignals(False)
        
        # Field Slice Visualization Params are excluded from state tracking to prevent Undo/Redo zombie actors
        # Optimize Transducer update
        tx_data = data.get('transducers', [])
        needs_rebuild = len(tx_data) != len(self.transducer_actors)
        
        if needs_rebuild:
            from PySide6.QtWidgets import QApplication
            for i, actor in enumerate(self.transducer_actors):
                if actor in self.selected_actors: self.selected_actors.remove(actor)
                self.plotter.remove_actor(actor, render=False)
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
                
            shared_mapper = pv.DataSetMapper(base_mesh)
            rgb_color = pv.Color(color).float_rgb
            
            for i, tx in enumerate(tx_data):
                matrix_vals = tx.get('matrix')
                if matrix_vals:
                    mat = vtk.vtkMatrix4x4()
                    for r in range(4):
                        for c in range(4):
                            mat.SetElement(r, c, matrix_vals[r*4 + c])
                    actor = pv.Actor(mapper=shared_mapper)
                    actor.GetProperty().SetColor(rgb_color)
                    actor.SetUserMatrix(mat)
                    actor._initial_matrix = mat
                    actor._original_color = rgb_color
                    actor._amplitude = self._current_amplitude
                    self.plotter.renderer.AddActor(actor)
                    self.transducer_actors.append(actor)
                    if i % 100 == 0: QApplication.processEvents()
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
                self.plotter.remove_actor(p["actor"], render=False)
            self.control_points.clear()
            self.points_list.clear()
            
            for pt in pt_data:
                idx = len(self.control_points)
                name = pt.get('name', f"제어점 {idx+1}")
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
                
        # Trajectory
        if 'traj_start' in data:
            self.traj_start_x.setValue(data['traj_start'][0])
            self.traj_start_y.setValue(data['traj_start'][1])
            self.traj_start_z.setValue(data['traj_start'][2])
        if 'traj_end' in data:
            self.traj_end_x.setValue(data['traj_end'][0])
            self.traj_end_y.setValue(data['traj_end'][1])
            self.traj_end_z.setValue(data['traj_end'][2])
        if 'traj_steps' in data: self.traj_steps.setValue(data['traj_steps'])
        if 'traj_delay' in data: self.traj_delay.setValue(data['traj_delay'])
        if 'traj_optim' in data: self.chk_optim_traj.setChecked(data['traj_optim'])
        if 'traj_show' in data and hasattr(self, 'chk_show_traj'):
            self.chk_show_traj.setChecked(data['traj_show'])
            if hasattr(self, 'toggle_trajectory_visibility'):
                self.toggle_trajectory_visibility()
                
        if 'traj_points_data' in data:
            if hasattr(self, 'generate_trajectory'):
                self.generate_trajectory()
                
        # Field Slice Recovery (only when loaded from file)
        if 'show_field' in data and hasattr(self, 'xz_check'):
            self.xz_check.blockSignals(True); self.xz_slider.blockSignals(True)
            self.yz_check.blockSignals(True); self.yz_slider.blockSignals(True)
            self.xy_check.blockSignals(True); self.xy_slider.blockSignals(True)
            if hasattr(self, 'show_field_btn'): self.show_field_btn.blockSignals(True)
            if hasattr(self, 'field_mode_combo'): self.field_mode_combo.blockSignals(True)
            
            self.xz_check.setChecked(data.get('xz_check', False))
            if 'xz_slider' in data: self.xz_slider.setValue(data['xz_slider'])
            self.yz_check.setChecked(data.get('yz_check', False))
            if 'yz_slider' in data: self.yz_slider.setValue(data['yz_slider'])
            self.xy_check.setChecked(data.get('xy_check', False))
            if 'xy_slider' in data: self.xy_slider.setValue(data['xy_slider'])
            
            if hasattr(self, 'show_field_btn'): self.show_field_btn.setChecked(data.get('show_field', False))
            if hasattr(self, 'field_mode_combo') and 'field_mode' in data:
                idx = self.field_mode_combo.findText(data['field_mode'])
                if idx >= 0: self.field_mode_combo.setCurrentIndex(idx)
                
            self.xz_check.blockSignals(False); self.xz_slider.blockSignals(False)
            self.yz_check.blockSignals(False); self.yz_slider.blockSignals(False)
            self.xy_check.blockSignals(False); self.xy_slider.blockSignals(False)
            if hasattr(self, 'show_field_btn'): self.show_field_btn.blockSignals(False)
            if hasattr(self, 'field_mode_combo'): self.field_mode_combo.blockSignals(False)
            
            if hasattr(self, 'toggle_field_slice'):
                self.toggle_field_slice()
                
        # Update UI state correctly after state restore
        if hasattr(self, 'update_gizmo'):
            self.update_gizmo()
        if hasattr(self, 'update_ui_from_selection'):
            self.update_ui_from_selection()
            
        # self.plotter.reset_camera() # Do not reset camera on undo, it's annoying!
        self.simulate_colors()

    def check_unsaved_changes(self):
        """
        Checks if there are unsaved changes. Prompts the user to save if so.
        Returns True if it is safe to proceed (saved, discarded, or no changes).
        Returns False if the user cancelled the action.
        """
        current_state = self.get_state(for_file=True)
        
        is_dirty = False
        if hasattr(self, '_last_saved_state'):
            # Compare states. Because dicts can contain floats, it might be tricky, 
            # but get_state outputs basic types, so == is usually sufficient.
            is_dirty = (self._last_saved_state != current_state)
        else:
            # If there's no last_saved_state, it's dirty if they made ANY points or trajectories
            is_dirty = len(self.control_points) > 0 or hasattr(self, 'trajectories_list') and len(self.trajectories_list) > 0
            
        if is_dirty:
            from PySide6.QtWidgets import QMessageBox
            reply = self.show_silent_msg("저장되지 않은 변경사항", "현재 프로젝트에 저장되지 않은 변경사항이 있습니다.\n종료하기 전에 변경사항을 저장하시겠습니까?", is_question=True, cancel_btn=True)
            if reply == -1:
                return False
            elif reply == 1:
                if getattr(self, 'current_project_file', None):
                    self.save_project()
                else:
                    self.save_project_as()
                    if not getattr(self, 'current_project_file', None):
                        return False # Cancelled save as dialog
        return True
    def save_project(self):
        if not getattr(self, 'current_project_file', None):
            self.save_project_as()
            return
        data = self.get_state(for_file=True)
        file_io.save_project(self.current_project_file, data)
        self.setWindowTitle(f"Acoustic Control Studio - {self.current_project_file}")
        self._last_saved_state = data
    def save_project_as(self):
        from PySide6.QtWidgets import QFileDialog
        import json
        filename, _ = QFileDialog.getSaveFileName(self, "다른 이름으로 프로젝트 저장", "", "Acoustic Project (*.json)")
        if not filename: return
        self.current_project_file = filename
        self.save_project()
        
    def new_project(self):
        if not self.check_unsaved_changes():
            return
            
        # Clear transducers
        for actor in self.transducer_actors:
            self.plotter.remove_actor(actor, render=False)
        self.transducer_actors.clear()
        
        # Clear control points
        for p in self.control_points:
            if p["actor"] in self.selected_actors: self.selected_actors.remove(p["actor"])
            self.plotter.remove_actor(p["actor"], render=False)
        self.control_points.clear()
        self.points_list.clear()
        self.selected_actors.clear()
        
        # Clear trajectory if active
        if hasattr(self, 'clear_all_trajectories'):
            self.clear_all_trajectories()
            
        # Reset UI blocks to default state
        if hasattr(self, 'xz_check'):
            self.xz_check.setChecked(False)
            self.yz_check.setChecked(False)
            self.xy_check.setChecked(False)
            if hasattr(self, 'show_field_btn'): self.show_field_btn.setChecked(False)
        if hasattr(self, 'toggle_field_slice'):
            self.toggle_field_slice()
        
        # Reset to default UI params
        if hasattr(self, 'transducer_type_cb'): self.transducer_type_cb.setCurrentIndex(0)
        if hasattr(self, 'array_type_cb'): self.array_type_cb.setCurrentIndex(0)
        if hasattr(self, 'spacing_spin'): self.spacing_spin.setValue(10.5)
        if hasattr(self, 'trap_type_cb'): self.trap_type_cb.setCurrentIndex(0)
        
        # Reset array setup UI
        if hasattr(self, 'gen_pos_x'):
            self.gen_pos_x.setValue(0.0)
            self.gen_pos_y.setValue(0.0)
            self.gen_pos_z.setValue(0.0)
            self.gen_rot_x.setValue(0.0)
            self.gen_rot_y.setValue(0.0)
            self.gen_rot_z.setValue(0.0)
            
        # Reset trajectory UI
        if hasattr(self, 'traj_type_cb'): self.traj_type_cb.setCurrentIndex(0)
        if hasattr(self, 'traj_start_x'):
            self.traj_start_x.setValue(0.0)
            self.traj_start_y.setValue(0.0)
            self.traj_start_z.setValue(0.0)
            self.traj_end_x.setValue(0.0)
            self.traj_end_y.setValue(0.0)
            self.traj_end_z.setValue(0.0)
        if hasattr(self, 'traj_steps'): self.traj_steps.setValue(100)
        if hasattr(self, 'traj_delay'): self.traj_delay.setValue(30)
        if hasattr(self, 'chk_optim_traj'): self.chk_optim_traj.setChecked(False)
        if hasattr(self, 'chk_show_traj'): self.chk_show_traj.setChecked(True)
        if hasattr(self, 'traj_param_spin'): self.traj_param_spin.setValue(20.0)
        
        self.current_project_file = None
        self.setWindowTitle("Acoustic Control Studio - 새 프로젝트")
        self.plotter.render()
        
        # Must be called after UI is fully rebuilt
        self._last_saved_state = self.get_state(for_file=True)
        self.state_mgr.clear()
            
        self.push_state()
    def load_project(self):
        if not self.check_unsaved_changes():
            return
        from PySide6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getOpenFileName(self, "프로젝트 불러오기", "", "Acoustic Project (*.json)")
        if not filename: return
        try:
            data = file_io.load_project(filename)
        except Exception as e:
            self.show_silent_msg("오류", f"작업 중 오류가 발생했습니다: {str(e)}")
            return
        self.current_project_file = filename
        self.set_state(data)
        self.push_state()
        self.setWindowTitle(f"Acoustic Control Studio - {self.current_project_file}")
        self._last_saved_state = self.get_state(for_file=True)
    def push_state(self):
        state = self.get_state()
        self.state_mgr.push(state)
    def undo(self):
        current_state = self.get_state()
        prev = self.state_mgr.undo(current_state)
        if prev is not None:
            self.set_state(prev)
    def redo(self):
        next_state = self.state_mgr.redo()
        if next_state is not None:
            self.set_state(next_state)
    def clear_view(self):
        for actor in self.transducer_actors:
            if actor in self.selected_actors:
                self.selected_actors.remove(actor)
            self.plotter.remove_actor(actor, render=False)
        self.transducer_actors.clear()
        
        for p in self.control_points:
            if p["actor"] in self.selected_actors:
                self.selected_actors.remove(p["actor"])
            self.plotter.remove_actor(p["actor"], render=False)
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
        import pyvista as pv
        from PySide6.QtWidgets import QApplication
        
        qapp = QApplication.instance()
        shared_mapper = pv.DataSetMapper(base_mesh)
        rgb_color = pv.Color(color).float_rgb
        
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
            
            actor = pv.Actor(mapper=shared_mapper)
            actor.GetProperty().SetColor(rgb_color)
            actor.SetUserMatrix(transform.GetMatrix())
            actor._initial_matrix = transform.GetMatrix()
            actor._original_color = rgb_color
            actor._amplitude = getattr(self, '_current_amplitude', 1.0)
            
            self.plotter.renderer.AddActor(actor)
            self.transducer_actors.append(actor)
            
            # Keep UI responsive for large array generation
            if idx % 100 == 0 and qapp:
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
        
        import matplotlib.cm as cm
        cmap = cm.get_cmap('hsv')
        
        active_pts = []
        for idx, pt in enumerate(self.control_points):
            item = self.points_list.item(idx)
            if item and item.checkState() == Qt.Checked:
                active_pts.append(pt)
                
        centers = np.array([actor.center for actor in self.transducer_actors])
        self._last_packet = None
        
        tx_amplitudes = np.array([getattr(a, '_amplitude', 1.0) for a in self.transducer_actors])
        mode_idx = self.compute_mode_cb.currentIndex()
        
        if active_pts:
            total_phases, packet = self.phase_engine.calculate_phases(
                centers, active_pts, tx_amplitudes, algorithm, mode_idx,
                has_taichi=getattr(self, 'has_taichi', False),
                has_pytorch=getattr(self, 'has_pytorch', False)
            )
            self._last_packet = packet
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
        if hasattr(self, 'chk_realtime_send') and self.chk_realtime_send.isChecked():
            if self.hw_controller.is_connected():
                self.send_phase_data()
    def toggle_field_slice(self):
        if self.show_field_btn.isChecked():
            self.show_field_btn.setText("음압 단면 숨기기")
            self.update_field_slice()
        else:
            self.show_field_btn.setText("음압 단면 시각화")
            for a in self.field_actors:
                try: self.plotter.remove_actor(a, render=False)
                except: pass
            self.field_actors.clear()
            
            if hasattr(self, '_cached_field_grids'):
                for key, (grid, actor) in self._cached_field_grids.items():
                    try: self.plotter.remove_actor(actor, render=False)
                    except: pass
                self._cached_field_grids.clear()
                
            self.plotter.render()
    def _get_field_bounds(self, pad=35.0):
        coords = []
        if self.transducer_actors:
            coords.extend([a.center for a in self.transducer_actors])
        if hasattr(self, 'control_points') and self.control_points:
            coords.extend([[pt.get("x", 0.0), pt.get("y", 0.0), pt.get("z", 0.0)] for pt in self.control_points])
            
        if not coords:
            return (-50.0, 50.0), (-50.0, 50.0), (-50.0, 50.0)
            
        arr = np.array(coords)
        min_x, max_x = np.min(arr[:, 0]), np.max(arr[:, 0])
        min_y, max_y = np.min(arr[:, 1]), np.max(arr[:, 1])
        min_z, max_z = np.min(arr[:, 2]), np.max(arr[:, 2])
        
        bx_min, bx_max = float(min_x - pad), float(max_x + pad)
        by_min, by_max = float(min_y - pad), float(max_y + pad)
        bz_min, bz_max = float(min_z - pad), float(max_z + pad)
        
        if bx_max - bx_min < 60.0:
            mid_x = (bx_min + bx_max) / 2.0
            bx_min, bx_max = mid_x - 30.0, mid_x + 30.0
        if by_max - by_min < 60.0:
            mid_y = (by_min + by_max) / 2.0
            by_min, by_max = mid_y - 30.0, mid_y + 30.0
        if bz_max - bz_min < 60.0:
            mid_z = (bz_min + bz_max) / 2.0
            bz_min, bz_max = mid_z - 30.0, mid_z + 30.0
            
        return (bx_min, bx_max), (by_min, by_max), (bz_min, bz_max)

    def draw_ghost_plane(self, axis_name, offset):
        if not self.show_field_btn.isChecked() or not self.transducer_actors: return
        import numpy as np
        import pyvista as pv
        
        (bx_min, bx_max), (by_min, by_max), (bz_min, bz_max) = self._get_field_bounds()
        
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
            if hasattr(self, '_cached_field_grids'):
                for key, (grid, actor) in self._cached_field_grids.items():
                    actor.SetVisibility(False)
            self.plotter.render()
            return
        
        tx_centers = np.array([a.center for a in self.transducer_actors])
        tx_phases = np.array([getattr(a, '_phase', 0.0) for a in self.transducer_actors])
        tx_amplitudes = np.array([getattr(a, '_amplitude', 1.0) for a in self.transducer_actors])
        
        (bx_min, bx_max), (by_min, by_max), (bz_min, bz_max) = self._get_field_bounds()
        
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
                
            field_mode_idx = self.field_mode_combo.currentIndex() if hasattr(self, 'field_mode_combo') else 0
            mode_idx = self.compute_mode_cb.currentIndex()
            
            real_p, imag_p = self.phase_engine.calculate_field_slice(
                pts, tx_centers, tx_phases, tx_amplitudes, mode_idx,
                has_taichi=getattr(self, 'has_taichi', False),
                has_pytorch=getattr(self, 'has_pytorch', False)
            )
            if field_mode_idx == 1:
                # 위상 분포 (Phase Angle)
                scalar_data = np.arctan2(imag_p, real_p)
                p_min, p_max = -np.pi, np.pi
                cmap = 'hsv'
                opacity_arr = np.ones_like(real_p)
                opacity_spec = 1.0
            elif field_mode_idx == 2:
                # 순간 파면 (Instantaneous Wavefront, Re(P)) - k-Wave 없는 초고속 해석적 점음원 모델
                scalar_data = real_p
                max_abs = float(np.percentile(np.abs(scalar_data), 99.5))
                if max_abs < 1e-4: max_abs = 1.0
                p_min, p_max = -max_abs, max_abs
                cmap = 'RdBu_r'
                opacity_arr = np.ones_like(real_p)
                opacity_spec = 1.0
            else:
                # 음압 분포 (Pressure Magnitude)
                scalar_data = np.sqrt(real_p**2 + imag_p**2)
                p_min, p_max = 0, np.percentile(scalar_data, 99.5)
                cmap = 'hot'
                opacity_arr = np.ones_like(real_p)
                opacity_spec = 1.0

            import pyvista as pv
            if cache_key in self._cached_field_grids:
                grid, actor = self._cached_field_grids[cache_key]
                grid.points = pts
                grid.point_data['Pressure'][:] = scalar_data
                grid.point_data['Opacity'][:] = opacity_arr
                actor = self.plotter.add_mesh(
                    grid, scalars='Pressure', cmap=cmap, opacity=opacity_spec,
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
                grid.point_data['Opacity'] = opacity_arr
                actor = self.plotter.add_mesh(
                    grid, scalars='Pressure', cmap=cmap, opacity=opacity_spec,
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
        reply = self.show_silent_msg("라이브러리 설치 필요", f"해당 기능을 사용하려면 '{pkg}' 라이브러리가 필요합니다.\n지금 다운로드 및 설치하시겠습니까?", is_question=True)
        if reply == 1:
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

    def set_traj_start_from_selected(self):
        if not getattr(self, 'selected_actors', []):
            from PySide6.QtWidgets import QMessageBox
            self.show_silent_msg("경고", "위치를 가져올 객체(제어점 등)를 먼저 선택해주세요.")
            return
        self.traj_start_x.setValue(self.sel_x.value())
        self.traj_start_y.setValue(self.sel_y.value())
        self.traj_start_z.setValue(self.sel_z.value())

    def set_traj_end_from_selected(self):
        if not getattr(self, 'selected_actors', []):
            from PySide6.QtWidgets import QMessageBox
            self.show_silent_msg("경고", "위치를 가져올 객체(제어점 등)를 먼저 선택해주세요.")
            return
        self.traj_end_x.setValue(self.sel_x.value())
        self.traj_end_y.setValue(self.sel_y.value())
        self.traj_end_z.setValue(self.sel_z.value())

    def generate_trajectory(self):
        traj_type = self.traj_type_cb.currentIndex()
        sx, sy, sz = self.traj_start_x.value(), self.traj_start_y.value(), self.traj_start_z.value()
        ex, ey, ez = self.traj_end_x.value(), self.traj_end_y.value(), self.traj_end_z.value()
        param = self.traj_param_spin.value()
        steps = self.traj_steps.value()
        
        if steps < 2: return
        
        import numpy as np
        points = np.zeros((steps, 3))
        delays = np.ones(steps) * self.traj_delay.value()
        
        for i in range(steps):
            t = i / (steps - 1)
            if traj_type == 0: # Linear
                points[i] = [sx + (ex - sx) * t, sy + (ey - sy) * t, sz + (ez - sz) * t]
            elif traj_type == 1: # Circular
                theta = t * 2.0 * np.pi
                points[i] = [sx + param * np.cos(theta), sy + param * np.sin(theta), sz]
            elif traj_type == 2: # Figure-8
                theta = t * 2.0 * np.pi
                # Figure-8 (Lissajous)
                points[i] = [sx + param * np.sin(theta), sy + param * np.sin(theta) * np.cos(theta), sz]
            
        optim_metrics = None
        if hasattr(self, 'chk_optim_traj') and self.chk_optim_traj.isChecked():
            tx_centers = np.array([a.center for a in self.transducer_actors]) if hasattr(self, 'transducer_actors') else np.empty((0, 3))
            algo = self.trap_type_cb.currentText() if hasattr(self, 'trap_type_cb') else "Twin Trap"
            delays, optim_metrics = self.phase_engine.optimize_trajectory_physical(
                tx_centers=tx_centers,
                points=points,
                base_delay=self.traj_delay.value(),
                algorithm=algo,
                smooth_accel=True
            )
            if hasattr(self, 'statusBar') and self.statusBar():
                self.statusBar().showMessage(
                    f"물리 연산 기반 궤적 최적화 완료 (평균 안정도: {optim_metrics['avg_stability']:.1f}%, 최소: {optim_metrics['min_stability']:.1f}%)",
                    5000
                )

        if not hasattr(self, 'trajectories_list'):
            self.trajectories_list = []

        type_str = self.traj_type_cb.currentText()
        if traj_type == 0:
            traj_name = f"궤적 {len(self.trajectories_list)+1} [{type_str}]: ({sx:.1f}, {sy:.1f}, {sz:.1f}) ➜ ({ex:.1f}, {ey:.1f}, {ez:.1f})"
        else:
            traj_name = f"궤적 {len(self.trajectories_list)+1} [{type_str}]: 중심({sx:.1f}, {sy:.1f}, {sz:.1f}), 반경/크기({param:.1f}mm)"

        if optim_metrics is not None:
            grade = optim_metrics.get('grade', '안정')
            avg_val = optim_metrics.get('avg_stability', 0.0)
            traj_name += f" [{grade} {avg_val:.0f}%]"
        else:
            traj_name += " [일반 등속]"

        traj_dict = {'name': traj_name, 'points': points, 'steps': steps, 'delays': delays, 'metrics': optim_metrics}
        self.trajectories_list.append(traj_dict)
        
        if hasattr(self, 'traj_list'):
            self.traj_list.addItem(traj_name)
            self.traj_list.setCurrentRow(len(self.trajectories_list) - 1)
            self.load_selected_trajectory(len(self.trajectories_list) - 1)

    def load_selected_trajectory(self, idx):
        if not hasattr(self, 'trajectories_list') or idx < 0 or idx >= len(self.trajectories_list):
            return
            
        # Remove old actors
        if hasattr(self, 'traj_actors'):
            for act in self.traj_actors:
                try: self.plotter.remove_actor(act, render=False)
                except: pass
        self.traj_actors = []
        
        traj = self.trajectories_list[idx]
        metrics = traj.get('metrics', None)
        self.update_trajectory_diagnosis_ui(metrics)

        points = traj['points']
        import numpy as np
        self.traj_points_data = points
        self.traj_delays_data = traj.get('delays', np.ones(len(points)) * self.traj_delay.value())
        self.traj_steps.blockSignals(True)
        self.traj_steps.setValue(traj['steps'])
        self.traj_steps.blockSignals(False)
        
        actual_time = np.sum(self.traj_delays_data) / 1000.0
        self.lbl_traj_time.setText(f"예상 시간: {actual_time:.2f}초 (+렌더링)")
        
        import pyvista as pv
        # Draw Line
        steps = len(points)
        lines = np.hstack([[steps], np.arange(steps)])
        poly = pv.PolyData(points)
        poly.lines = lines
        self.traj_line_actor = self.plotter.add_mesh(poly, color='magenta', line_width=3, render=False)
        
        # Draw Points
        self.traj_points_actor = self.plotter.add_mesh(pv.PolyData(points), color='cyan', point_size=6, render=False)
        
        self.traj_actors.extend([self.traj_line_actor, self.traj_points_actor])
        
        if hasattr(self, 'toggle_trajectory_visibility'):
            self.toggle_trajectory_visibility()
            
        self.plotter.render()
        
    def clear_selected_trajectory(self):
        if hasattr(self, 'traj_list') and hasattr(self, 'trajectories_list'):
            row = self.traj_list.currentRow()
            if row < 0 or row >= len(self.trajectories_list):
                return
            del self.trajectories_list[row]
            self.traj_list.takeItem(row)
            
            # Remove old actors if any
            if hasattr(self, 'traj_actors'):
                for act in self.traj_actors:
                    try: self.plotter.remove_actor(act, render=False)
                    except: pass
                self.traj_actors = []
            
            # Select another one if available
            if self.trajectories_list:
                new_row = min(row, len(self.trajectories_list) - 1)
                self.traj_list.setCurrentRow(new_row)
                self.load_selected_trajectory(new_row)
            else:
                self.update_trajectory_diagnosis_ui('empty')
                self.plotter.render()

    def clear_all_trajectories(self):
        if hasattr(self, 'traj_actors'):
            for act in self.traj_actors:
                try: self.plotter.remove_actor(act, render=False)
                except: pass
            self.traj_actors = []
            self.plotter.render()
        if hasattr(self, 'trajectories_list'):
            self.trajectories_list.clear()
        if hasattr(self, 'traj_list'):
            self.traj_list.clear()
        self.update_trajectory_diagnosis_ui('empty')

    def on_traj_item_clicked(self, item):
        idx = self.traj_list.row(item)
        self.load_selected_trajectory(idx)

    def start_traj_playback(self, direction=1):
        if not hasattr(self, 'traj_actors') or not self.traj_actors:
            from PySide6.QtWidgets import QMessageBox
            self.show_silent_msg("경고", "먼저 궤적을 생성하거나 선택해주세요.")
            return
        if not getattr(self, 'selected_actors', []):
            from PySide6.QtWidgets import QMessageBox
            self.show_silent_msg("경고", "궤적을 따라 이동시킬 제어점을 선택해주세요.")
            return
            
        self.traj_play_direction = direction
        if not hasattr(self, 'traj_timer'):
            from PySide6.QtCore import QTimer
            self.traj_timer = QTimer(self)
            self.traj_timer.timeout.connect(self._on_traj_timer_step)
            self.traj_current_step = 0
            
        if not hasattr(self, 'traj_current_step'):
            self.traj_current_step = 0
            
        # If playing forward and already at the end, restart from beginning
        if direction == 1 and hasattr(self, 'traj_points_data') and self.traj_current_step >= len(self.traj_points_data) - 1:
            self.traj_current_step = -1
        # If playing backward and already at the beginning, restart from end
        elif direction == -1 and hasattr(self, 'traj_points_data') and self.traj_current_step <= 0:
            self.traj_current_step = len(self.traj_points_data)
            
        # Restore auto calc to original state if we stopped completely
        if not self.traj_timer.isActive():
            self._prev_auto_calc = self.auto_calc_cb.isChecked()
            self.auto_calc_cb.setChecked(False)
            
        delay_ms = self.traj_delay.value()
        self.traj_timer.start(delay_ms if delay_ms > 0 else 10)
        self.btn_traj_play.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; font-size: 16px;")

    def pause_traj_playback(self):
        if hasattr(self, 'traj_timer') and self.traj_timer.isActive():
            self.traj_timer.stop()
            self.btn_traj_play.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            self.auto_calc_cb.setChecked(getattr(self, '_prev_auto_calc', False))
            if hasattr(self, 'push_state'): self.push_state()

    def reset_traj_playback(self):
        self.pause_traj_playback()
        self.traj_current_step = 0
        if hasattr(self, 'traj_points_data') and len(self.traj_points_data) > 0:
            pt = self.traj_points_data[0]
            if getattr(self, 'selected_actors', []):
                self.sel_x.setValue(pt[0])
                self.sel_y.setValue(pt[1])
                self.sel_z.setValue(pt[2])
                if hasattr(self, 'simulate_colors'): self.simulate_colors()
                if hasattr(self, 'update_field_slice'): self.update_field_slice()
                self.plotter.render()
        if hasattr(self, 'traj_list'):
            self.traj_list.setCurrentRow(0)

    def _on_traj_timer_step(self):
        if not hasattr(self, 'traj_points_data') or len(self.traj_points_data) == 0:
            self.pause_traj_playback()
            return
            
        pts = self.traj_points_data
        self.traj_current_step += self.traj_play_direction
        
        if self.traj_current_step < 0:
            self.traj_current_step = 0
            self.pause_traj_playback()
        elif self.traj_current_step >= len(pts):
            self.traj_current_step = len(pts) - 1
            self.pause_traj_playback()
            
        pt = pts[self.traj_current_step]
        self.sel_x.setValue(pt[0])
        self.sel_y.setValue(pt[1])
        self.sel_z.setValue(pt[2])
        
        if hasattr(self, 'traj_delays_data') and self.traj_current_step < len(self.traj_delays_data):
            dynamic_delay = int(self.traj_delays_data[self.traj_current_step])
            if dynamic_delay > 0 and self.traj_timer.interval() != dynamic_delay:
                self.traj_timer.setInterval(dynamic_delay)
                
        if hasattr(self, 'traj_list'):
            self.traj_list.setCurrentRow(self.traj_current_step)
        
        if hasattr(self, 'simulate_colors'):
            self.simulate_colors()
            
        if hasattr(self, 'update_field_slice'):
            self.update_field_slice()
            
        self.plotter.render()

    def update_traj_preview(self, *args):
        if not hasattr(self, 'traj_steps') or not hasattr(self, 'traj_delay'):
            return
        
        steps = self.traj_steps.value()
        delay_ms = self.traj_delay.value()
        base_seconds = (steps * delay_ms) / 1000.0

        # 1. 3D 이동 거리 계산 (Distance, mm)
        traj_type_idx = self.traj_type_cb.currentIndex() if hasattr(self, 'traj_type_cb') else 0
        dist_mm = 0.0
        
        if traj_type_idx == 0:  # 선형 (Linear)
            if hasattr(self, 'traj_start_x') and hasattr(self, 'traj_end_x'):
                sx, sy, sz = self.traj_start_x.value(), self.traj_start_y.value(), self.traj_start_z.value()
                ex, ey, ez = self.traj_end_x.value(), self.traj_end_y.value(), self.traj_end_z.value()
                dist_mm = float(np.sqrt((ex - sx)**2 + (ey - sy)**2 + (ez - sz)**2))
        elif traj_type_idx == 1:  # 원형 (Circular)
            radius = self.traj_param_spin.value() if hasattr(self, 'traj_param_spin') else 20.0
            dist_mm = float(2.0 * np.pi * radius)
        else:  # 8자형 (Figure-8)
            radius = self.traj_param_spin.value() if hasattr(self, 'traj_param_spin') else 20.0
            dist_mm = float(8.5 * radius)

        # 2. 평균 이송 속도 계산 (mm/s)
        avg_speed = (dist_mm / base_seconds) if base_seconds > 0 else 0.0

        # 3. 물리 최적화 여부
        is_optim = self.chk_optim_traj.isChecked() if hasattr(self, 'chk_optim_traj') else False

        # 4. 실시간 인라인 단일 라벨 갱신 (테두리 없는 깔끔한 1줄)
        if hasattr(self, 'lbl_traj_preview_inline'):
            if is_optim:
                t_min = base_seconds * 1.15
                if dist_mm > 0.1:
                    self.lbl_traj_preview_inline.setText(
                        f"예상 소요 시간: 약 {t_min:.2f}초 (물리 가감속 반영 · 거리 {dist_mm:.1f}mm)"
                    )
                else:
                    self.lbl_traj_preview_inline.setText(
                        f"예상 소요 시간: 약 {t_min:.2f}초 (물리 가감속 반영)"
                    )
                self.lbl_traj_preview_inline.setStyleSheet(
                    "color: #8E24AA; font-weight: bold; font-size: 11px; margin-top: 4px; margin-bottom: 2px;"
                )
            else:
                if dist_mm > 0.1:
                    self.lbl_traj_preview_inline.setText(
                        f"예상 소요 시간: {base_seconds:.2f}초 (거리 {dist_mm:.1f}mm · 평균 {avg_speed:.1f}mm/s)"
                    )
                else:
                    self.lbl_traj_preview_inline.setText(
                        f"예상 소요 시간: {base_seconds:.2f}초"
                    )
                self.lbl_traj_preview_inline.setStyleSheet(
                    "color: #E65100; font-weight: bold; font-size: 11px; margin-top: 4px; margin-bottom: 2px;"
                )

        # 하단 미디어 컨트롤러 시간 라벨도 동기화
        if hasattr(self, 'lbl_traj_time'):
            if is_optim:
                self.lbl_traj_time.setText(f"예상 시간: ~{base_seconds * 1.15:.2f}초 (+가감속)")
            else:
                self.lbl_traj_time.setText(f"예상 시간: {base_seconds:.2f}초 (+렌더링)")

    def update_traj_time(self):
        self.update_traj_preview()

    def toggle_trajectory_visibility(self):
        if not hasattr(self, 'traj_actors') or not hasattr(self, 'chk_show_traj'):
            return
        visible = self.chk_show_traj.isChecked()
        for act in self.traj_actors:
            try:
                act.SetVisibility(visible)
            except: pass
        self.plotter.render()

    def toggle_cpu_monitoring(self):
        self.settings.setValue("show_cpu", self.action_show_cpu.isChecked())
        if self.action_show_cpu.isChecked():
            try:
                import psutil
            except ImportError:
                self.action_show_cpu.setChecked(False)
                self.settings.setValue("show_cpu", False)
                self._prompt_install_from_cb("psutil")
                return
        if hasattr(self, 'resource_monitor'):
            self.show_cpu = self.action_show_cpu.isChecked()
            self.resource_monitor.show_cpu = self.show_cpu
            
    def toggle_gpu_monitoring(self):
        self.settings.setValue("show_gpu", self.action_show_gpu.isChecked())
        if self.action_show_gpu.isChecked():
            try:
                import GPUtil
            except ImportError:
                self.action_show_gpu.setChecked(False)
                self.settings.setValue("show_gpu", False)
                self._prompt_install_from_cb("GPUtil")
                return
        if hasattr(self, 'resource_monitor'):
            self.show_gpu = self.action_show_gpu.isChecked()
            self.resource_monitor.show_gpu = self.show_gpu
            
    def on_resource_updated(self, data):
        msg = "준비 완료"
        parts = []
        if self.show_cpu:
            if 'cpu' in data:
                parts.append(f"CPU: {data['cpu']:.1f}%")
            elif 'cpu_err' in data:
                parts.append(f"CPU: {data['cpu_err']}")
        if self.show_gpu:
            if 'gpu' in data:
                parts.append(f"GPU: {data['gpu']:.1f}%")
            elif 'gpu_err' in data:
                parts.append(f"GPU: {data['gpu_err']}")
                
        if parts:
            if hasattr(self, 'resource_label'):
                self.resource_label.setText(" | ".join(parts))
        else:
            if hasattr(self, 'resource_label'):
                self.resource_label.setText("")

    def update_trajectory_diagnosis_ui(self, metrics=None):
        """우측 패널의 물리 안정성 진단 미니 요약 카드 텍스트/스타일 갱신"""
        if not hasattr(self, 'lbl_diag_title') or not hasattr(self, 'lbl_diag_desc'):
            return

        if metrics == 'empty' or (hasattr(self, 'trajectories_list') and not self.trajectories_list):
            self.lbl_diag_title.setText("물리 안정성 진단: 선택된 궤적 없음")
            self.lbl_diag_desc.setText("안내: 궤적을 선택하거나 새로 생성하면 상세 진단이 표시됩니다.")
            return

        if isinstance(metrics, dict):
            grade = metrics.get('grade', '안정')
            avg = metrics.get('avg_stability', 0.0)
            min_val = metrics.get('min_stability', 0.0)
            guide = metrics.get('guide_msg', '안정적인 이송 구간입니다.')
            color = metrics.get('color', '#1565C0')
            self.lbl_diag_title.setText(f"물리 안정성 진단: <span style='color: {color}; font-weight: bold;'>{grade}</span> (평균 {avg:.1f}% / 최저 {min_val:.1f}%)")
            self.lbl_diag_desc.setText(f"안내: {guide}")
        else:
            self.lbl_diag_title.setText("물리 안정성 진단: <span style='color: #555555; font-weight: bold;'>일반 등속</span>")
            self.lbl_diag_desc.setText("안내: 물리 최적화가 적용되지 않은 일반 기하학 등속 궤적입니다.")

    def export_selected_trajectory(self):
        """선택된 궤적의 위상 데이터를 C헤더(.h), CSV(.csv), 또는 하드웨어 바이너리(.bin) 파일로 내보내기"""
        if not hasattr(self, 'trajectories_list') or not hasattr(self, 'traj_list'):
            self.show_silent_msg("알림", "내보낼 궤적이 없습니다.")
            return

        row = self.traj_list.currentRow()
        if row < 0 or row >= len(self.trajectories_list):
            self.show_silent_msg("알림", "목록에서 내보낼 궤적을 먼저 선택해주세요.")
            return

        traj = self.trajectories_list[row]
        points = traj.get('points', [])
        delays = traj.get('delays', [])
        steps = len(points)
        if steps == 0:
            self.show_silent_msg("오류", "선택된 궤적에 유효한 좌표 데이터가 없습니다.")
            return

        from PySide6.QtWidgets import QFileDialog
        filters = "C/C++ Header (*.h);;CSV Data (*.csv);;Hardware Binary Packet (*.bin);;All Files (*.*)"
        file_path, selected_filter = QFileDialog.getSaveFileName(self, "궤적 데이터 내보내기", "", filters)
        if not file_path:
            return

        tx_centers = np.array([a.center for a in self.transducer_actors]) if hasattr(self, 'transducer_actors') else np.empty((0, 3))
        num_tx = len(tx_centers)
        k = getattr(self.phase_engine, 'k', 2.0 * np.pi * 40000.0 / 343000.0)
        algo = self.trap_type_cb.currentText() if hasattr(self, 'trap_type_cb') else "Twin Trap"

        from acousticstudio.sonic_wrapper import calculate_phases_sonic
        all_discretized = []
        all_phases_rad = []

        for i in range(steps):
            pt = points[i]
            if num_tx > 0:
                phases, _ = calculate_phases_sonic(
                    np.array([pt[0]]), np.array([pt[1]]), np.array([pt[2]]),
                    tx_centers[:, 0], tx_centers[:, 1], tx_centers[:, 2],
                    np.ones(num_tx), algo, k
                )
                disc = np.round((phases % (2.0 * np.pi)) / (2.0 * np.pi) * 32.0).astype(int) % 32
            else:
                phases = np.zeros(num_tx)
                disc = np.zeros(num_tx, dtype=int)
            all_phases_rad.append(phases)
            all_discretized.append(disc)

        try:
            if file_path.endswith('.h') or "Header" in selected_filter:
                if not file_path.endswith('.h'): file_path += '.h'
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("// =========================================================\n")
                    f.write("// AcousticStudio Trajectory Phase Data Header\n")
                    f.write(f"// Trajectory: {traj.get('name', 'Trajectory')}\n")
                    f.write(f"// Total Steps: {steps}, Transducers: {num_tx}\n")
                    f.write("// =========================================================\n\n")
                    f.write("#ifndef ACOUSTIC_TRAJECTORY_DATA_H\n")
                    f.write("#define ACOUSTIC_TRAJECTORY_DATA_H\n\n")
                    f.write("#include <stdint.h>\n\n")
                    f.write(f"#define TRAJ_TOTAL_STEPS {steps}\n")
                    f.write(f"#define TRAJ_NUM_TRANSDUCERS {num_tx}\n\n")

                    f.write("// Step Delays (milliseconds)\n")
                    f.write(f"const uint16_t traj_step_delays_ms[TRAJ_TOTAL_STEPS] = {{\n")
                    for d_idx, d_val in enumerate(delays):
                        end_char = "," if d_idx < steps - 1 else ""
                        f.write(f"    {int(round(d_val))}{end_char}\n")
                    f.write("};\n\n")

                    f.write("// 32-Step Discretized Phases (0 ~ 31, 5-bit HW Packet format)\n")
                    f.write(f"const uint8_t traj_phases[TRAJ_TOTAL_STEPS][TRAJ_NUM_TRANSDUCERS] = {{\n")
                    for s_idx in range(steps):
                        p_str = ", ".join(map(str, all_discretized[s_idx]))
                        end_char = "," if s_idx < steps - 1 else ""
                        f.write(f"    /* Step {s_idx:3d} */ {{ {p_str} }}{end_char}\n")
                    f.write("};\n\n")
                    f.write("#endif // ACOUSTIC_TRAJECTORY_DATA_H\n")

            elif file_path.endswith('.csv') or "CSV" in selected_filter:
                if not file_path.endswith('.csv'): file_path += '.csv'
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    header = ['Step', 'Target_X_mm', 'Target_Y_mm', 'Target_Z_mm', 'Delay_ms']
                    for t_idx in range(num_tx):
                        header.append(f"Tx{t_idx}_Phase32")
                    writer.writerow(header)
                    for s_idx in range(steps):
                        row_data = [
                            s_idx,
                            f"{points[s_idx][0]:.3f}",
                            f"{points[s_idx][1]:.3f}",
                            f"{points[s_idx][2]:.3f}",
                            f"{delays[s_idx]:.1f}"
                        ]
                        row_data.extend(list(all_discretized[s_idx]))
                        writer.writerow(row_data)

            elif file_path.endswith('.bin') or "Binary" in selected_filter:
                if not file_path.endswith('.bin'): file_path += '.bin'
                byte_buffer = bytearray()
                for s_idx in range(steps):
                    byte_buffer.append(0xFA)
                    byte_buffer.extend(all_discretized[s_idx].astype(np.uint8).tobytes())
                    byte_buffer.append(0xFD)
                with open(file_path, 'wb') as f:
                    f.write(byte_buffer)

            if hasattr(self, 'statusBar') and self.statusBar():
                self.statusBar().showMessage(f"궤적 데이터 내보내기 완료: {file_path}", 5000)
            self.show_silent_msg("내보내기 완료", f"궤적 데이터가 성공적으로 저장되었습니다.\n\n경로: {file_path}")

        except Exception as e:
            self.show_silent_msg("내보내기 오류", f"파일 저장 중 오류가 발생했습니다:\n{e}")

    def open_kwave_simulation(self):
        if not self.transducer_actors:
            self.show_silent_msg("알림", "배치된 트랜스듀서가 없습니다. 먼저 트랜스듀서를 배치하세요.")
            return
        try:
            from .kwave_engine import KWaveDialog
            dlg = KWaveDialog(self, self.transducer_actors)
            dlg.exec()
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            self.show_silent_msg("오류", f"k-Wave 시뮬레이션 창을 여는 중 오류가 발생했습니다:\n{str(e)}")


