# -*- coding: utf-8 -*-
"""
widgets.py - Reusable Qt widget and event-filter classes for AcousticStudio.

Extracted from app.py.  Contains:
  - ResourceMonitorThread: background thread for CPU/GPU usage polling
  - MouseEventFilter: 3-D viewport mouse interaction (selection, gizmo drag, orbit)
  - WheelBlocker: prevents scroll-wheel from changing spinbox/combo values
  - KeepOpenMenu: QMenu that stays open when a checkable action is toggled
"""

import time
import numpy as np
import vtk

from PySide6.QtWidgets import (QApplication, QMenu, QRubberBand)
from PySide6.QtCore import Qt, QObject, QEvent, QRect, QThread, Signal


class ResourceMonitorThread(QThread):
    updated = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.show_cpu = False
        self.show_gpu = False
        
    def run(self):
        while self.running:
            data = {}
            if self.show_cpu:
                try:
                    import psutil
                    data['cpu'] = psutil.cpu_percent()
                except ImportError:
                    data['cpu_err'] = "psutil 미설치"
                    
            if self.show_gpu:
                try:
                    import GPUtil
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        data['gpu'] = gpus[0].load * 100
                    else:
                        data['gpu_err'] = "GPU 없음"
                except ImportError:
                    data['gpu_err'] = "GPUtil 미설치"
                except Exception as e:
                    data['gpu_err'] = f"GPU 오류: {str(e)}"
                    
            self.updated.emit(data)
            time.sleep(1.5)
            
    def stop(self):
        self.running = False
        self.wait()

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
            # 스크롤바에 이벤트를 직접 전달하여 스크롤이 되게 함
            QApplication.sendEvent(self.scroll_area.verticalScrollBar(), event)
            return True # SpinBox/ComboBox가 이벤트를 처리하지 못하게 완전 차단
        
        if event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton:
                if getattr(self, 'main', None) and hasattr(self.main, 'push_state'):
                    # To avoid spamming, only push if state changed. push_state already checks this.
                    self.main.push_state()
        return False

class KeepOpenMenu(QMenu):
    def mouseReleaseEvent(self, e):
        action = self.actionAt(e.pos())
        if action and action.isCheckable():
            action.trigger()
            self.update()
            e.accept()
            return
        super().mouseReleaseEvent(e)
