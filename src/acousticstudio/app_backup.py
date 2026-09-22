# -*- coding: utf-8 -*-

import sys

import os

os.environ["QT_API"] = "pyside6"

import numpy as np

import pyvista as pv

import vtk

from pyvistaqt import QtInteractor

from PySide6.QtWidgets import (QApplication, QSplitter, QMainWindow, QWidget, QVBoxLayout, 
                                     QHBoxLayout, QPushButton, QLabel, 
                                     QDoubleSpinBox, QSpinBox, QComboBox, QGroupBox, 
                                     QListWidget, QAbstractItemView, QRubberBand, QSlider, QCheckBox,
                                     QScrollArea, QFormLayout, QListWidgetItem, QMessageBox)

from PySide6.QtCore import Qt, QObject, QEvent, QRect





class MouseEventFilter(QObject):

    """doc"""""

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

                # 1. 기즈�??�살??�?�??�확???�릭?�는지 Hit Test

                picker = vtk.vtkPropPicker()

                picker.Pick(pos.x(), vtk_y, 0, self.main.plotter.renderer)

                prop = picker.GetViewProp()

                

                # 기즈모�? ?�성???�태?�고, ?�릭??객체가 ?�서???��??�인?��? ?�니?�면 기즈모일 ?�률???�음

                if hasattr(self.main, 'gizmo') and self.main.gizmo and self.main.gizmo.GetEnabled():

                    if prop and prop not in self.main.transducer_actors and prop not in self.main.get_control_point_actors():

                        # VTK가 기즈�??�래그�? 처리?�도�??�버?�둠

                        return False 

                

                # 기즈모�? ?�닌 ?�공/객체 ?�릭 ?? ?�택 박스 ?�래�??�작

                self.origin = pos

                self.rubber_band.setGeometry(self.origin.x(), self.origin.y(), 0, 0)

                self.rubber_band.show()

                return True # ?�벤??강제 종료 (VTK�??�어가지 ?�게 ?�여 카메???�전 방�?)

                

            elif event.button() == Qt.RightButton:

                # ?�클�???VTK??기본 카메?�인 TrackballCamera??'좌클�?Orbit)' 기능??강제�??�출

                self.right_dragging = True

                iren = self.main.plotter.interactor

                iren.SetEventPosition(scaled_x if "scaled_x" in locals() else int(round(pos.x() * scale)), vtk_y)

                iren.LeftButtonPressEvent()

                return True

                

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

                # 1. 3D 기즈�??�살?? ?�에 마우?��? ?�라가 ?�는지(Hover) 먼�? ?�인

                if hasattr(self.main, 'gizmo') and self.main.gizmo and self.main.gizmo.GetEnabled():

                    rep = self.main.gizmo.GetRepresentation()

                    if rep.GetInteractionState() != 0:

                        # 기즈�?조작 중이므�??�도??PyQt) ?�택 박스�?그리지 ?�고 VTK???�릭 ?�벤?��? ?��?

                        return False

                        

                # 2. 기즈�?밖을 ?�릭??경우 ?�도???�택 박스(RubberBand) ?�작

                self.origin = pos

                self.rubber_band.setGeometry(self.origin.x(), self.origin.y(), 0, 0)

                self.rubber_band.show()

                return True

                

            elif event.button() == Qt.RightButton:

                self.right_dragging = True

                iren = self.main.plotter.interactor

                iren.SetEventPosition(scaled_x if "scaled_x" in locals() else int(round(pos.x() * scale)), vtk_y)

                # 기즈모�? ?�벤?��? 가로채지 못하?�록 ?�터?�터 ?��??�의 ?�수�?직접 ?�출?�여 ?�수?�게 ?�면�??�전?�킵?�다.

                style = iren.GetInteractorStyle()

                if hasattr(style, 'OnLeftButtonDown'):

                    style.OnLeftButtonDown()

                return True
        elif event.type() == QEvent.MouseMove:
            scale = self.main.plotter.interactor.devicePixelRatioF()
            pos = event.position().toPoint()
            scaled_y = int(round(pos.y() * scale))
            vtk_y = self.main.plotter.window_size[1] - scaled_y - 1


            

            if self.origin is not None:

                self.rubber_band.setGeometry(QRect(self.origin, pos).normalized())

                return True

                

            elif self.right_dragging:

                iren = self.main.plotter.interactor

                iren.SetEventPosition(scaled_x if "scaled_x" in locals() else int(round(pos.x() * scale)), vtk_y)

                style = iren.GetInteractorStyle()

                if hasattr(style, 'OnMouseMove'):

                    style.OnMouseMove()

                return True
        elif event.type() == QEvent.MouseButtonRelease:
            scale = self.main.plotter.interactor.devicePixelRatioF()
            pos = event.position().toPoint()
            scaled_y = int(round(pos.y() * scale))
            vtk_y = self.main.plotter.window_size[1] - scaled_y - 1


            

            if event.button() == Qt.LeftButton and self.origin is not None:

                self.rubber_band.hide()

                end_pos = pos

                start_pos = self.origin

                self.origin = None # �??�수 ?�출 ?�에 None?�로 초기??(?�러 발생 ?�에???�태가 꼬이지 ?�도�?

                try:

                    self.main.process_selection(start_pos, end_pos, event.modifiers())

                except Exception as e:

                    import traceback; traceback.print_exc()

                return True

                

            elif event.button() == Qt.RightButton and self.right_dragging:

                self.right_dragging = False

                iren = self.main.plotter.interactor

                iren.SetEventPosition(scaled_x if "scaled_x" in locals() else int(round(pos.x() * scale)), vtk_y)

                style = iren.GetInteractorStyle()

                if hasattr(style, 'OnLeftButtonUp'):

                    style.OnLeftButtonUp()

                return True

                

        return False





class AcousticStudioMain(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Acoustic Control Studio - PyVista 3D Viewer")

        self.resize(1400, 950)

        

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        main_layout = QHBoxLayout(main_widget)

        

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
        import vtk
        self.gizmo_rep = vtk.vtkAxesTransformRepresentation()
         # Hide coordinate labels to avoid clutter
        self.gizmo_widget = vtk.vtkAxesTransformWidget()
        self.gizmo_widget.SetRepresentation(self.gizmo_rep)
        self.gizmo_widget.SetInteractor(self.plotter.iren.interactor)
        self.gizmo_widget.SetCurrentRenderer(self.plotter.renderer)
        self.gizmo_widget.SetDefaultRenderer(self.plotter.renderer)
        self.gizmo_widget.AddObserver("InteractionEvent", self.on_gizmo_interaction)
        self.gizmo_widget.Off()


        

        # ??�� ??(Del) 바인??        
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
        control_layout.setContentsMargins(5, 10, 15, 10)

        
        
        scroll_area.setWidget(control_panel)
        
        from PySide6.QtWidgets import QSplitter
        from PySide6.QtCore import Qt
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.view_panel)
        self.splitter.addWidget(scroll_area)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([1020, 380])
        
        main_layout.addWidget(self.splitter)



        

        # [1. Transform Properties (?�택??객체 ?�동/?�전)] - ?�로 추�???

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
        t_layout.addWidget(QLabel("위치 (mm):"), 0, 0)
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

        transform_group.setLayout(t_layout)
        control_layout.addWidget(transform_group)


        # Properties Group
        self.prop_group = QGroupBox("Selected Properties (속성 조절)")
        prop_layout = QFormLayout()
        
        self.prop_type_lbl = QLabel("-")
        self.prop_sensor_cb = QComboBox()
        self.prop_sensor_cb.addItems(["소형 초음파센서 (10mm)", "소형 초음파센서 (16mm)", "랑주뱅 진동자 (Langevin)"])
        
        self.prop_radius_spin = QDoubleSpinBox()
        self.prop_radius_spin.setRange(0.1, 100.0)
        self.prop_radius_spin.setSuffix(" mm")
        
        prop_layout.addRow("선택 객체:", self.prop_type_lbl)
        prop_layout.addRow("센서 변경:", self.prop_sensor_cb)
        prop_layout.addRow("반경 조절:", self.prop_radius_spin)
        
        self.prop_group.setLayout(prop_layout)
        control_layout.addWidget(self.prop_group)

        self.prop_sensor_cb.currentIndexChanged.connect(self.on_prop_sensor_changed)
        self.prop_radius_spin.valueChanged.connect(self.on_prop_radius_changed)


        

        # UI 값이 바�???3D 객체??즉시 반영

        self.sel_x.valueChanged.connect(self.apply_ui_transform)

        self.sel_y.valueChanged.connect(self.apply_ui_transform)

        self.sel_z.valueChanged.connect(self.apply_ui_transform)

        self.sel_rx.valueChanged.connect(self.apply_ui_transform)

        self.sel_ry.valueChanged.connect(self.apply_ui_transform)

        self.sel_rz.valueChanged.connect(self.apply_ui_transform)

        

        # [2. 배열 ?�정 그룹]

        array_group = QGroupBox("2. Transducer Array Setup (초음파 배열 설정)")

        array_layout = QFormLayout()

        

        self.transducer_type_cb = QComboBox()

        self.transducer_type_cb.addItems(["소형 초음파센서 (10mm)", "소형 초음파센서 (16mm)", "랑주뱅 진동자 (Langevin)"])

        self.array_type_cb = QComboBox()

        self.array_type_cb.addItems([
            "NxM Matrix (평면형)", 
            "터널형 (상하좌우 4면)", 
            "대향형 (상하 2면)", 
            "반구형 (Hemisphere)"
        ])

        

        self.grid_x_spin = QSpinBox(); self.grid_x_spin.setValue(16); self.grid_x_spin.setRange(1, 100)

        self.grid_y_spin = QSpinBox(); self.grid_y_spin.setValue(16); self.grid_y_spin.setRange(1, 100)

        

        # 배열 ?�성 ???�치/각도 지??        
        self.gen_pos_x = QDoubleSpinBox(); self.gen_pos_x.setRange(-1000, 1000); self.gen_pos_x.setValue(0.0)

        self.gen_pos_y = QDoubleSpinBox(); self.gen_pos_y.setRange(-1000, 1000); self.gen_pos_y.setValue(0.0)

        self.gen_pos_z = QDoubleSpinBox(); self.gen_pos_z.setRange(-1000, 1000); self.gen_pos_z.setValue(0.0)

        

        self.gen_rot_x = QDoubleSpinBox(); self.gen_rot_x.setRange(-360, 360); self.gen_rot_x.setValue(0.0)

        self.gen_rot_y = QDoubleSpinBox(); self.gen_rot_y.setRange(-360, 360); self.gen_rot_y.setValue(0.0)

        self.gen_rot_z = QDoubleSpinBox(); self.gen_rot_z.setRange(-360, 360); self.gen_rot_z.setValue(0.0)

        

        array_layout.addRow("센서 형태:", self.transducer_type_cb)

        array_layout.addRow("배열 방식:", self.array_type_cb)

        

        grid_layout = QHBoxLayout()

        grid_layout.addWidget(self.grid_x_spin)

        grid_layout.addWidget(self.grid_y_spin)

        array_layout.addRow("Grid X, Y:", grid_layout) 

        

        
        gen_grid = QGridLayout()
        gen_grid.addWidget(QLabel("생성 위치 (mm):"), 0, 0)
        gen_grid.addWidget(QLabel("X:"), 0, 1)
        gen_grid.addWidget(self.gen_pos_x, 0, 2)
        gen_grid.addWidget(QLabel("Y:"), 0, 3)
        gen_grid.addWidget(self.gen_pos_y, 0, 4)
        gen_grid.addWidget(QLabel("Z:"), 0, 5)
        gen_grid.addWidget(self.gen_pos_z, 0, 6)

        gen_grid.addWidget(QLabel("생성 각도 (deg):"), 1, 0)
        gen_grid.addWidget(QLabel("Rx:"), 1, 1)
        gen_grid.addWidget(self.gen_rot_x, 1, 2)
        gen_grid.addWidget(QLabel("Ry:"), 1, 3)
        gen_grid.addWidget(self.gen_rot_y, 1, 4)
        gen_grid.addWidget(QLabel("Rz:"), 1, 5)
        gen_grid.addWidget(self.gen_rot_z, 1, 6)

        array_layout.addRow(gen_grid)


        

        self.add_array_btn = QPushButton("배열 3D 뷰어에 생성하기")

        self.add_array_btn.clicked.connect(self.generate_array)

        self.clear_btn = QPushButton("Clear All")

        self.clear_btn.clicked.connect(self.clear_view)

        

        array_layout.addRow(self.add_array_btn)

        array_layout.addRow(self.clear_btn)

        array_group.setLayout(array_layout)

        control_layout.addWidget(array_group)

        

        # [3. 컨트�??�인??(?��? 그룹]

        points_group = QGroupBox("3. Control Points (타겟 설정)")

        points_layout = QVBoxLayout()

        

        
        self.point_size_spin = QDoubleSpinBox()
        self.point_size_spin.setRange(0.1, 50.0)
        self.point_size_spin.setValue(5.0)
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("타겟 반경 (mm):"))
        size_layout.addWidget(self.point_size_spin)
        points_layout.addLayout(size_layout)
        
        self.points_list = QListWidget()


        self.points_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.points_list.currentRowChanged.connect(self.on_point_selected)

        points_layout.addWidget(self.points_list)

        

        btn_layout = QHBoxLayout()

        self.add_pt_btn = QPushButton("Add Point")

        self.add_pt_btn.clicked.connect(self.add_control_point)

        self.del_pt_btn = QPushButton("Delete Point")

        self.del_pt_btn.clicked.connect(self.delete_control_point)

        btn_layout.addWidget(self.add_pt_btn)

        btn_layout.addWidget(self.del_pt_btn)

        points_layout.addLayout(btn_layout)

        

        self.auto_calc_cb = QCheckBox("Point 위치 변동 시 위상/음압 실시간 자동 계산")

        self.auto_calc_cb.setChecked(False) # 기본?�으�?켜둠

        points_layout.addWidget(self.auto_calc_cb)

        

        points_group.setLayout(points_layout)

        control_layout.addWidget(points_group)

        

        # [4. ?�랩 �??��??�이??그룹]

        field_group = QGroupBox("4. Phase Simulation (위상 연산)")

        field_layout = QFormLayout()

        self.trap_type_cb = QComboBox()

        self.trap_type_cb.addItems(["Twin Trap", "Vortex Trap"])

        field_layout.addRow("알고리즘:", self.trap_type_cb)

        

        self.run_btn = QPushButton("Calculate Phase (위상 계산 및 시각화)")

        self.run_btn.setStyleSheet("background-color: #4CAF50; color: white; height: 30px; font-weight: bold;")

        self.run_btn.clicked.connect(self.simulate_colors)

        field_layout.addRow(self.run_btn)

        field_group.setLayout(field_layout)

        control_layout.addWidget(field_group)

        

        # [5. ?�압 ?�각??그룹]

        visual_group = QGroupBox("5. Acoustic Field Visualization (음압 단면 시각화)")

        visual_layout = QVBoxLayout()

        

        # XZ Plane

        xz_lyt = QHBoxLayout()

        self.xz_check = QCheckBox("XZ (측면)")

        self.xz_check.stateChanged.connect(self.update_field_slice)

        self.xz_slider = QSlider(Qt.Horizontal); self.xz_slider.setRange(-500, 500)

        self.xz_slider.valueChanged.connect(self.update_field_slice)

        xz_lyt.addWidget(self.xz_check); xz_lyt.addWidget(self.xz_slider)

        visual_layout.addLayout(xz_lyt)

        

        # YZ Plane

        yz_lyt = QHBoxLayout()

        self.yz_check = QCheckBox("YZ (정면)")

        self.yz_check.stateChanged.connect(self.update_field_slice)

        self.yz_slider = QSlider(Qt.Horizontal); self.yz_slider.setRange(-500, 500)

        self.yz_slider.valueChanged.connect(self.update_field_slice)

        yz_lyt.addWidget(self.yz_check); yz_lyt.addWidget(self.yz_slider)

        visual_layout.addLayout(yz_lyt)

        

        # XY Plane

        xy_lyt = QHBoxLayout()

        self.xy_check = QCheckBox("XY (바닥)")

        self.xy_check.stateChanged.connect(self.update_field_slice)

        self.xy_slider = QSlider(Qt.Horizontal); self.xy_slider.setRange(-500, 500)

        self.xy_slider.valueChanged.connect(self.update_field_slice)

        xy_lyt.addWidget(self.xy_check); xy_lyt.addWidget(self.xy_slider)

        visual_layout.addLayout(xy_lyt)

        

        self.show_field_btn = QPushButton("음압 단면 보기 (ON/OFF)")

        self.show_field_btn.setStyleSheet("background-color: #2196F3; color: white; height: 30px; font-weight: bold;")

        self.show_field_btn.setCheckable(True)

        self.show_field_btn.clicked.connect(self.toggle_field_slice)

        visual_layout.addWidget(self.show_field_btn)

        

        visual_group.setLayout(visual_layout)

        control_layout.addWidget(visual_group)

        

        self.field_actors = [] # ?�중 ?�라?�스 ?�터�?관리하�??�한 리스??        

        
        self._is_updating_ui = False


        self._sel_base_centroid = [0.0, 0.0, 0.0]

        self._sel_base_rot = [0.0, 0.0, 0.0]



    
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

        

        # 변??매트�?�� ?�성

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

            

            # 컨트�??�인?�인 경우 ?��? ?�이???�기??            
            for pt in self.control_points:

                if pt["actor"] == act:

                    c = act.center

                    pt["x"], pt["y"], pt["z"] = c[0], c[1], c[2]

                    point_moved = True

                    

        # 기즈�??�치 ?�데?�트

        if hasattr(self, 'gizmo') and self.gizmo:

            cx, cy, cz = self._sel_base_centroid[0] + dx, self._sel_base_centroid[1] + dy, self._sel_base_centroid[2] + dz

            d = 30.0

            self.gizmo.GetRepresentation().PlaceWidget([cx-d, cx+d, cy-d, cy+d, cz-d, cz+d])

            

        if point_moved and self.auto_calc_cb.isChecked():

            self.simulate_colors()

        else:

            self.plotter.render()

    def on_gizmo_interaction(self, caller, event):
        if not self.selected_actors: return
        pos = self.gizmo_rep.GetOriginWorldPosition()
        
        # Temporarily disconnect spinboxes to avoid double-triggering or loops if needed,
        # but apply_ui_transform is exactly what we need to move the actors.
        # We just set the values and let the spinbox signals do the rest!
        # Wait, if we drag the gizmo, it updates the spinbox.
        # The spinbox triggers apply_ui_transform.
        # apply_ui_transform will move the actors, but it also tries to update the gizmo position...
        # We need to make sure apply_ui_transform doesn't reset the gizmo while we are dragging it!
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

            self.selected_actors.clear()

            

        for prop in picked_props:

            if is_ctrl and prop in self.selected_actors:

                self.selected_actors.remove(prop)

                if hasattr(prop, '_original_color'):

                    prop.prop.color = prop._original_color

            else:

                if prop not in self.selected_actors:

                    self.selected_actors.append(prop)

                    prop.prop.color = "pink"

                    

        self.update_gizmo()

        self.update_ui_from_selection()

        self.plotter.render()



    def update_ui_from_selection(self):

        """doc"""""

        self._is_updating_ui = True

        if not self.selected_actors:

            self.sel_x.setValue(0); self.sel_y.setValue(0); self.sel_z.setValue(0)

            self.sel_rx.setValue(0); self.sel_ry.setValue(0); self.sel_rz.setValue(0)

        self.prop_sensor_cb.setEnabled(False)
        self.prop_radius_spin.setEnabled(False)
        self.prop_type_lbl.setText("-")
        
        has_sensor = any(a in self.transducer_actors for a in self.selected_actors)
        cp_actor = None
        has_cp = False
        for a in self.selected_actors:
            if any(pt["actor"] == a for pt in self.control_points):
                has_cp = True
                cp_actor = a
                break
                
        if has_sensor and not has_cp:
            self.prop_type_lbl.setText("초음파 센서")
            self.prop_sensor_cb.setEnabled(True)
        elif has_cp and not has_sensor:
            self.prop_type_lbl.setText("타겟 (Control Point)")
            self.prop_radius_spin.setEnabled(True)
            for pt in self.control_points:
                if pt["actor"] == cp_actor:
                    self.prop_radius_spin.setValue(pt.get("radius", 5.0))
                    break
        elif has_sensor and has_cp:
            self.prop_type_lbl.setText("다중 선택 (혼합)")


            self._sel_base_centroid = [0.0, 0.0, 0.0]

            self._sel_base_rot = [0.0, 0.0, 0.0]

            
            self.gizmo_widget.Off()
            self._is_updating_ui = False


            return

            

        cx, cy, cz = 0.0, 0.0, 0.0

        for act in self.selected_actors:

            c = act.center

            cx += c[0]; cy += c[1]; cz += c[2]

        n = len(self.selected_actors)

        cx /= n; cy /= n; cz /= n

        

        self._sel_base_centroid = [cx, cy, cz]

        # ?�중 ?�택 ???�전?� 0?�로 기�????�음

        self._sel_base_rot = [0.0, 0.0, 0.0] 

        

        
        self.sel_x.setValue(cx); self.sel_y.setValue(cy); self.sel_z.setValue(cz)
        self.sel_rx.setValue(0); self.sel_ry.setValue(0); self.sel_rz.setValue(0)

        self.prop_sensor_cb.setEnabled(False)
        self.prop_radius_spin.setEnabled(False)
        self.prop_type_lbl.setText("-")
        
        has_sensor = any(a in self.transducer_actors for a in self.selected_actors)
        cp_actor = None
        has_cp = False
        for a in self.selected_actors:
            if any(pt["actor"] == a for pt in self.control_points):
                has_cp = True
                cp_actor = a
                break
                
        if has_sensor and not has_cp:
            self.prop_type_lbl.setText("초음파 센서")
            self.prop_sensor_cb.setEnabled(True)
        elif has_cp and not has_sensor:
            self.prop_type_lbl.setText("타겟 (Control Point)")
            self.prop_radius_spin.setEnabled(True)
            for pt in self.control_points:
                if pt["actor"] == cp_actor:
                    self.prop_radius_spin.setValue(pt.get("radius", 5.0))
                    break
        elif has_sensor and has_cp:
            self.prop_type_lbl.setText("다중 선택 (혼합)")



        
        self._is_updating_ui = False




    
    def on_prop_sensor_changed(self, idx):
        if getattr(self, '_is_updating_ui', False) or not self.selected_actors: return
        sensor_type = self.prop_sensor_cb.currentText()
        if "10mm" in sensor_type:
            r_wide, r_narrow, height, color = 5.0, 3.5, 4.0, "lightblue"
        elif "16mm" in sensor_type:
            r_wide, r_narrow, height, color = 8.0, 5.0, 6.0, "orange"
        else: # Langevin
            r_wide, r_narrow, height, color = 25.0, 15.0, 40.0, "gray"
            
        new_actors = []
        for act in self.selected_actors:
            if act in self.transducer_actors:
                mat = act.GetUserMatrix() or getattr(act, '_initial_matrix', None)
                self.plotter.remove_actor(act)
                self.transducer_actors.remove(act)
                
                pts = self.make_truncated_cone(r_wide, r_narrow, height)
                faces = [[len(pts)] + list(range(len(pts)))]
                import pyvista as pv
                mesh = pv.PolyData(pts, faces)
                
                new_act = self.plotter.add_mesh(mesh, color=color, show_edges=True)
                if mat:
                    new_act.SetUserMatrix(mat)
                    new_act._initial_matrix = mat
                new_act._original_color = color
                new_act.prop.color = "pink"
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
                    new_act.prop.color = "pink"
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



    def update_gizmo(self):

        if hasattr(self, 'gizmo') and self.gizmo is not None:

            self.gizmo.Off()

            self.gizmo = None

            

        if not self.selected_actors:

            return

            

        # [?�시 비활?�화] vtkVectorText ?�러 문제�??�해 ?�면?�의 3D ?�살??기즈모는 ?�시 꺼둡?�다.

        # ?�치 ?�동?� ?�측 ?�널??'1. Selected Object Transform' ?��?박스�??�해 ?�벽??조작 가?�합?�다.

        pass



        for act in self.selected_actors:

            mat = vtk.vtkMatrix4x4()

            if act.GetUserMatrix():

                mat.DeepCopy(act.GetUserMatrix())

            else:

                mat.Identity()

            act._initial_matrix = mat



    def on_gizmo_interaction(self, caller, event):

        transform = vtk.vtkTransform()

        caller.GetRepresentation().GetTransform(transform)

        gizmo_matrix = transform.GetMatrix()

        

        for act in self.selected_actors:

            m_new = vtk.vtkMatrix4x4()

            vtk.vtkMatrix4x4.Multiply4x4(gizmo_matrix, act._initial_matrix, m_new)

            act.SetUserMatrix(m_new)

            

            for pt in self.control_points:

                if pt["actor"] == act:

                    c = act.center 

                    pt["x"], pt["y"], pt["z"] = c[0], c[1], c[2]

        

        # 기즈�??�동 �?UI ?�데?�트

        cx, cy, cz = 0.0, 0.0, 0.0

        for act in self.selected_actors:

            c = act.center

            cx += c[0]; cy += c[1]; cz += c[2]

        n = len(self.selected_actors)

        cx /= n; cy /= n; cz /= n

        

        self._is_updating_ui = True

        self.sel_x.setValue(cx); self.sel_y.setValue(cy); self.sel_z.setValue(cz)

        
        self._is_updating_ui = False


        

        self.plotter.render()

        

    def on_gizmo_interaction_end(self, caller, event):

        """doc"""

        self.update_ui_from_selection()

        for act in self.selected_actors:

            mat = vtk.vtkMatrix4x4()

            if act.GetUserMatrix():

                mat.DeepCopy(act.GetUserMatrix())

            else:

                mat.Identity()

            act._initial_matrix = mat



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

            # ?�인??리스???�릭 ???�당 ?�인?��? ?�독 ?�택 ?�태�?만듦

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

            

        # ?�단�?(Z ?�방?�이므�?반시계방??CCW)

        top_c = len(pts)

        pts.append([0, 0, height / 2.0])

        for i in range(resolution):

            nxt = (i + 1) % resolution

            faces.extend([3, top_c, i, nxt])

            

        # ?�단�?(Z ??��?�이므�??�계방향 CW)

        bot_c = len(pts)

        pts.append([0, 0, -height / 2.0])

        for i in range(resolution):

            nxt = (i + 1) % resolution

            faces.extend([3, bot_c, resolution + nxt, resolution + i])

            

        mesh = pv.PolyData(np.array(pts), np.array(faces))

        # CAD ?�로그램처럼 ?�카로운 모서�?가?�자�????�영??깨끗?�게 ?�림

        mesh = mesh.compute_normals(split_vertices=True, feature_angle=60)

        return mesh



    def generate_array(self):

        sensor_type = self.transducer_type_cb.currentText()

        array_type = self.array_type_cb.currentText()

        x_count = self.grid_x_spin.value()

        y_count = self.grid_y_spin.value()

        

        if "10mm" in sensor_type:

            spacing = 10.5

            r_wide, r_narrow, height = 5.0, 3.5, 4.0

            color = "lightblue"

        elif "16mm" in sensor_type:

            spacing = 16.5

            r_wide, r_narrow, height = 8.0, 5.0, 6.0

            color = "orange"

        else: # Langevin

            spacing = 50.0

            r_wide, r_narrow, height = 25.0, 15.0, 25.0

            color = "white"

            

        base_mesh = self.make_truncated_cone(r_wide, r_narrow, height)

        meshes_to_add = []



        if "Matrix" in array_type:

            start_x = -(x_count - 1) * spacing / 2.0

            start_y = -(y_count - 1) * spacing / 2.0

            for i in range(x_count):

                for j in range(y_count):

                    px = start_x + i * spacing

                    py = start_y + j * spacing

                    pz = -height / 2.0

                    mesh = base_mesh.copy()

                    mesh.translate((px, py, pz), inplace=True)

                    meshes_to_add.append(mesh)

                    

        elif "4" in array_type:

            # 8x8 ??배열???�기가 줄어?�었????멀찍이 ?�어지지 ?�고 ?�사각형 ?�브 ?�브가 ?�벽??맞물리도�?거리 최적??            # 면의 가�?길이(?????�반만큼�?중심?�서 ?�우�?4면이 ??맞게 조립?�니??

            tunnel_radius = (spacing * x_count) / 2.0

            

            start_u = -(x_count - 1) * spacing / 2.0

            start_v = -(y_count - 1) * spacing / 2.0

            for i in range(x_count):

                for j in range(y_count):

                    u = start_u + i * spacing

                    v = start_v + j * spacing

                    

                    mesh_b = base_mesh.copy()

                    mesh_b.translate((u, v, -tunnel_radius - height/2), inplace=True)

                    meshes_to_add.append(mesh_b)

                    

                    mesh_t = base_mesh.copy()

                    mesh_t.rotate_y(180, inplace=True)

                    mesh_t.translate((u, v, tunnel_radius + height/2), inplace=True)

                    meshes_to_add.append(mesh_t)

                    

                    mesh_l = base_mesh.copy()

                    mesh_l.rotate_y(90, inplace=True)

                    mesh_l.translate((-tunnel_radius - height/2, u, v), inplace=True)

                    meshes_to_add.append(mesh_l)

                    

                    mesh_r = base_mesh.copy()

                    mesh_r.rotate_y(-90, inplace=True)

                    mesh_r.translate((tunnel_radius + height/2, u, v), inplace=True)

                    meshes_to_add.append(mesh_r)

                    

        elif "2" in array_type:

            distance = max(100.0, spacing * max(x_count, y_count))

            start_x = -(x_count - 1) * spacing / 2.0

            start_y = -(y_count - 1) * spacing / 2.0

            for i in range(x_count):

                for j in range(y_count):

                    px = start_x + i * spacing

                    py = start_y + j * spacing

                    

                    # Bottom plate (facing up)

                    mesh_b = base_mesh.copy()

                    mesh_b.translate((px, py, -distance/2 - height/2), inplace=True)

                    meshes_to_add.append(mesh_b)

                    

                    # Top plate (facing down)

                    mesh_t = base_mesh.copy()

                    mesh_t.rotate_x(180, inplace=True)

                    mesh_t.translate((px, py, distance/2 + height/2), inplace=True)

                    meshes_to_add.append(mesh_t)

                    

        elif "Hemisphere" in array_type:

            N = x_count * y_count

            R = max(100.0, r_wide * np.sqrt(N * 0.8)) # Radius enough to fit N transducers

            phi_golden = np.pi * (3.0 - np.sqrt(5.0))

            

            for i in range(N):

                # ?�프 ??(?�래�?반구) ?�면 좌표 계산

                z = -1.0 + (i / float(N)) # -1 (bottom) to 0 (equator)

                radius_at_z = np.sqrt(1.0 - z*z)

                theta = phi_golden * i

                

                px = np.cos(theta) * radius_at_z * R

                py = np.sin(theta) * radius_at_z * R

                pz = z * R

                

                # ?�점??바라보는 벡터 방향

                v_dir = np.array([-px, -py, -pz])

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

                

                mat[:3, 3] = [px, py, pz]

                

                mesh = base_mesh.copy()

                mesh.transform(mat, inplace=True)

                meshes_to_add.append(mesh)

        

        rx, ry, rz = self.gen_rot_x.value(), self.gen_rot_y.value(), self.gen_rot_z.value()

        px, py, pz = self.gen_pos_x.value(), self.gen_pos_y.value(), self.gen_pos_z.value()

        

        for mesh in meshes_to_add:

            # 지?�된 초기 각도 �?좌표 ?�용

            mesh.rotate_x(rx, inplace=True)

            mesh.rotate_y(ry, inplace=True)

            mesh.rotate_z(rz, inplace=True)

            mesh.translate((px, py, pz), inplace=True)

            

            actor = self.plotter.add_mesh(mesh, color=color, show_edges=False)

            actor._original_color = color

            self.transducer_actors.append(actor)

            

        self.plotter.reset_camera()



    def simulate_colors(self):

        if not self.transducer_actors:

            return

        if not self.control_points:

            print("에러: 타겟(Control Point)이 1개 이상 존재해야 위상을 계산할 수 있습니다.")

            return

            

        algorithm = self.trap_type_cb.currentText()

        

        # 초음??물리 ?�수

        c = 343000.0 # ?�속 (mm/s)

        f = 40000.0 # 주파??(Hz)

        k = 2.0 * np.pi / (c / f) # ?�수 (Wavenumber)

        

        import matplotlib.cm as cm

        cmap = cm.get_cmap('hsv') # 0~360?��? 무�?개색?�로 매핑

        

        for actor in self.transducer_actors:

            cx, cy, cz = actor.center

            

            # ?�중 ?�겟에 ?�???�로그???�상 중첩(Superposition)

            
            complex_p = 0.0 + 0.0j
            
            # Check which points are active
            active_pts = []
            for idx, pt in enumerate(self.control_points):
                item = self.points_list.item(idx)
                if item and item.checkState() == Qt.Checked:
                    active_pts.append(pt)
            
            for pt in active_pts:


                tx, ty, tz = pt["x"], pt["y"], pt["z"]

                dx, dy, dz = cx - tx, cy - ty, cz - tz

                d = np.sqrt(dx**2 + dy**2 + dz**2)

                

                # 기본 초점 ?�상 (Focal Phase)

                phase_focal = -d * k

                signature = 0.0

                

                # ?�랩 ?�고리즘???�른 ?�명(Signature) ?�상 추�?

                if "Twin Trap" in algorithm:

                    if dx > 0:
                        signature = np.pi

                elif "Vortex Trap" in algorithm:

                    # ?��?Vortex) m=1 ?�성 (각도??비�?)

                    signature = np.arctan2(dy, dx)

                    

                pt_phase = phase_focal + signature

                complex_p += np.exp(1j * pt_phase)

                

            # 최종 ?�성???�상 추출 (0 ~ 2pi)

            total_phase = np.angle(complex_p) % (2.0 * np.pi)

            if total_phase < 0:

                total_phase += 2.0 * np.pi

                

            # ?�상 매핑 (0 ~ 1)

            color_val = total_phase / (2.0 * np.pi)

            rgba = cmap(color_val)

            

            # ?�터 ?�상 ?�데?�트 �??��? ?�상�??�??            
            actor.prop.color = rgba[:3]

            actor._original_color = rgba[:3]

            

            # ?�기??복소 진폭??최종 ?�상???�?�해???�니??

            actor._phase = total_phase

            

        self.plotter.render()

        

        # ?�압 ?�각?��? 켜져?�다�??�동 ?�데?�트

        if self.show_field_btn.isChecked():

            self.update_field_slice()

            

        print("위상 연산 및 시각화 완료!")



    def toggle_field_slice(self):

        if self.show_field_btn.isChecked():

            self.show_field_btn.setText("음압 단면 숨기기")

            self.update_field_slice()

        else:

            self.show_field_btn.setText("음압 단면 보기 (ON/OFF)")

            for a in self.field_actors:

                self.plotter.remove_actor(a)

            self.field_actors.clear()

            self.plotter.render()



    def update_field_slice(self, *args):

        # 1. 기존 ?�더링된 ?�라?�스 모두 ?�거

        for a in self.field_actors:

            self.plotter.remove_actor(a)

        self.field_actors.clear()

        

        if not self.show_field_btn.isChecked() or not self.transducer_actors:

            self.plotter.render()

            return

            

        # 2. ?�수 �??�랜?��????�보 준�?        
        c = 343000.0

        f = 40000.0

        k = 2.0 * np.pi / (c / f)

        

        tx_centers = np.array([a.center for a in self.transducer_actors])

        tx_phases = np.array([getattr(a, '_phase', 0.0) for a in self.transducer_actors])

        

        # ?�적 바운??박스 계산 (배열 ?�기???�백 30mm 추�?)

        min_x, max_x = np.min(tx_centers[:, 0]), np.max(tx_centers[:, 0])

        min_y, max_y = np.min(tx_centers[:, 1]), np.max(tx_centers[:, 1])

        min_z, max_z = np.min(tx_centers[:, 2]), np.max(tx_centers[:, 2])

        

        pad = 30.0

        bx_min, bx_max = min_x - pad, max_x + pad

        by_min, by_max = min_y - pad, max_y + pad

        bz_min, bz_max = min_z - pad, max_z + pad

        

        # 배열???��? ?�면??경우 최소 ?�각???�역(50mm) 보장

        if bx_max - bx_min < 50: bx_min -= 25; bx_max += 25

        if by_max - by_min < 50: by_min -= 25; by_max += 25

        if bz_max - bz_min < 50: bz_min -= 25; bz_max += 25

        

        res = 120

        x_vals = np.linspace(bx_min, bx_max, res)

        y_vals = np.linspace(by_min, by_max, res)

        z_vals = np.linspace(bz_min, bz_max, res)

        

        planes_to_draw = []

        if self.xz_check.isChecked():

            planes_to_draw.append((0, self.xz_slider.value()))

        if self.yz_check.isChecked():

            planes_to_draw.append((1, self.yz_slider.value()))

        if self.xy_check.isChecked():

            planes_to_draw.append((2, self.xy_slider.value()))

            

        for plane_idx, offset in planes_to_draw:

            if plane_idx == 0: # XZ ?�면 (Y=offset)

                X, Z = np.meshgrid(x_vals, z_vals)

                pts = np.c_[X.ravel(), np.full(res*res, offset), Z.ravel()]

            elif plane_idx == 1: # YZ ?�면 (X=offset)

                Y, Z = np.meshgrid(y_vals, z_vals)

                pts = np.c_[np.full(res*res, offset), Y.ravel(), Z.ravel()]

            else: # XY ?�면 (Z=offset)

                X, Y = np.meshgrid(x_vals, y_vals)

                pts = np.c_[X.ravel(), Y.ravel(), np.full(res*res, offset)]

                

            # ?�압 계산 (Broadcasting)

            diff = pts[:, np.newaxis, :] - tx_centers[np.newaxis, :, :]

            dist = np.linalg.norm(diff, axis=-1)

            dist[dist < 1e-3] = 1e-3

            

            complex_p = np.sum((1.0 / dist) * np.exp(1j * (k * dist + tx_phases)), axis=1)

            pressure_mag = np.abs(complex_p)

            

            grid = pv.StructuredGrid()

            grid.points = pts

            grid.dimensions = [res, res, 1]

            grid.point_data["Pressure"] = pressure_mag

            

            # ?�압 ?�각??개선: 

            # ?�랜?��????�면 근처??거리가 0??가까워 ?�력??무한?�(?�이??�?치솟?�니??

            # ???�문???�제 ?��?초점)???�압???��??�으�??�무 ??�� 보여 ?�면???�둡�??�옵?�다.

            # 99.5% 백분?�수�?최�?�?clim)?�로 지?�하??초점 부근이 ?�주 밝게 빛나?�록 ?��?Contrast)�??�???�어?�립?�다.

            p_max = np.percentile(pressure_mag, 99.5)

            

            # 불투명도�?1.0(?�전 불투�??�로 ?�정?�여 ?�본 Ultraino?� ?�일???�렷??�??�공

            actor = self.plotter.add_mesh(

                grid, scalars="Pressure", cmap="hot", opacity=1.0, 

                show_scalar_bar=False, clim=[0, p_max]

            )

            self.field_actors.append(actor)

            

        self.plotter.render()



