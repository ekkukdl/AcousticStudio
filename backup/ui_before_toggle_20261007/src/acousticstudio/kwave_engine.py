"""
kwave_engine.py - k-Wave 2D FDTD 기구물(반사판/터널) 음향 전파 및 정재파 시뮬레이션 모듈

본 모듈은 초음파 부상 장치 주변의 기구물(상단 반사판, 좌우 가이드 터널, 챔버 등)과 
다양한 재질(아크릴, 알루미늄, SUS, 3D 프린팅 수지, 유리, 흡음재 등)에 따른
초음파(40kHz)의 음향 전파, 반사, 간섭 및 정재파(Standing Wave) 트랩 형성을
k-Wave 의사스펙트럼 시간영역(k-space FDTD) 기법으로 시뮬레이션하고 분석합니다.
"""

import sys
import time
import numpy as np
from typing import Dict, List, Tuple, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox, QPushButton,
    QProgressBar, QTextEdit, QFileDialog, QTabWidget, QWidget,
    QFrame, QMessageBox, QSplitter
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.cm as cm
import matplotlib

# 한글 폰트 설정 (Windows 맑은 고딕, 유니코드 마이너스 지원)
if sys.platform.startswith('win'):
    matplotlib.rcParams['font.family'] = ['Malgun Gothic', 'NanumGothic', 'Gulim', 'sans-serif']
elif sys.platform.startswith('darwin'):
    matplotlib.rcParams['font.family'] = ['AppleGothic', 'sans-serif']
else:
    matplotlib.rcParams['font.family'] = ['NanumGothic', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

# k-Wave 라이브러리 임포트
try:
    from kwave.data import Vector
    from kwave.kgrid import kWaveGrid
    from kwave.kmedium import kWaveMedium
    from kwave.ksensor import kSensor
    from kwave.ksource import kSource
    from kwave.kspaceFirstOrder import kspaceFirstOrder
    from kwave.utils.filters import smooth
    KWAVE_AVAILABLE = True
except ImportError:
    KWAVE_AVAILABLE = False


# ============================================================================
# 1. 재질 물성치 사전 (Material Properties Database)
# ============================================================================
# 공기 기준: rho0 = 1.2 kg/m^3, c0 = 343 m/s (Z0 = 411.6 Rayl)
MATERIALS: Dict[str, dict] = {
    "아크릴 (Acrylic / PMMA)": {
        "sound_speed": 2700.0,
        "density": 1180.0,
        "alpha": 0.75,
        "desc": "일반 실험실 챔버 및 투명 반사판으로 널리 사용되는 플라스틱 수지 (반사율 ~99.97%)"
    },
    "알루미늄 (Aluminum)": {
        "sound_speed": 6420.0,
        "density": 2700.0,
        "alpha": 0.05,
        "desc": "경량 고강성 금속, 극도로 높은 음향 임피던스로 초음파 전반사 (반사율 ~99.99%)"
    },
    "스테인리스 스틸 (SUS304)": {
        "sound_speed": 5900.0,
        "density": 7930.0,
        "alpha": 0.02,
        "desc": "고밀도 부식 방지 금속, 완전 강체(Sound-hard) 음향 반사체"
    },
    "3D 프린팅 수지 (PLA/ABS)": {
        "sound_speed": 2200.0,
        "density": 1250.0,
        "alpha": 1.20,
        "desc": "FDM/SLA 3D 프린터로 제작된 커스텀 브라켓 및 덕트 구조물"
    },
    "유리 (Glass)": {
        "sound_speed": 5600.0,
        "density": 2500.0,
        "alpha": 0.10,
        "desc": "고평탄도 광학 관찰창 및 고주파 초음파 반사판"
    },
    "음향 흡음재 (Acoustic Foam)": {
        "sound_speed": 250.0,
        "density": 60.0,
        "alpha": 12.0,
        "desc": "원치 않는 반사 및 에코를 흡수 감쇠시키는 다공성 음향 댐퍼"
    },
    "사용자 정의 (Custom)": {
        "sound_speed": 3000.0,
        "density": 1500.0,
        "alpha": 0.50,
        "desc": "임의의 음속, 밀도, 감쇠계수를 직접 설정하여 FDTD 해석 수행"
    }
}

# 기구물 유형 정의
OBSTACLE_TYPES = [
    "상단 평면 반사판 (Top Reflector)",
    "좌우 가이드 터널 (Guide Tunnel)",
    "밀폐형 챔버 (Enclosed Chamber)",
    "기구물 없음 (Free Field)"
]


# ============================================================================
# 2. k-Wave 2D FDTD 시뮬레이션 백그라운드 워커 스레드
# ============================================================================
class KWaveSimWorker(QThread):
    progress_sig = Signal(int, str)
    finished_sig = Signal(dict)
    error_sig = Signal(str)

    def __init__(self, sim_params: dict):
        super().__init__()
        self.params = sim_params
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        if not KWAVE_AVAILABLE:
            self.error_sig.emit("k-Wave 패키지가 설치되어 있지 않습니다. simulations/k-wave-python 환경을 확인하세요.")
            return

        try:
            self.progress_sig.emit(5, "해석 도메인 및 기하학적 격자(Grid) 구성 중...")
            
            # 파라미터 추출
            plane_type = self.params.get('plane_type', 'xz')  # 'xz' or 'yz'
            slice_pos = self.params.get('slice_pos', 0.0)      # mm
            grid_res_mm = self.params.get('grid_res_mm', 1.0) # mm
            dx = grid_res_mm * 1e-3                           # m
            
            tx_data = self.params.get('transducers', []) # list of dict: x, y, z, phase, amp
            obstacle_type = self.params.get('obstacle_type', OBSTACLE_TYPES[0])
            mat_info = self.params.get('material_info', MATERIALS["아크릴 (Acrylic / PMMA)"])
            c_mat = float(mat_info['sound_speed'])
            rho_mat = float(mat_info['density'])
            alpha_mat = float(mat_info['alpha'])
            
            refl_z = self.params.get('refl_z', 60.0)          # mm (트랜스듀서로부터 상단 거리)
            refl_thick = self.params.get('refl_thick', 8.0)   # mm
            tunnel_w = self.params.get('tunnel_w', 60.0)      # mm
            num_cycles = self.params.get('num_cycles', 10)    # 시뮬레이션 주기 수
            
            c0 = 343.0      # 공기 음속 (m/s)
            rho0 = 1.2      # 공기 밀도 (kg/m^3)
            f0 = 40000.0    # 40 kHz
            wavelength = c0 / f0 # ~8.575 mm

            if not tx_data:
                self.error_sig.emit("배치된 트랜스듀서 데이터가 없습니다.")
                return

            # 슬라이스 평면 근처 트랜스듀서 선별 (단면 두께 오차 +-12 mm)
            active_tx = []
            for tx in tx_data:
                proj_dist = abs(tx['y'] - slice_pos) if plane_type == 'xz' else abs(tx['x'] - slice_pos)
                if proj_dist <= 12.0:
                    u_coord = tx['x'] if plane_type == 'xz' else tx['y']
                    active_tx.append({
                        'u': u_coord,
                        'z': tx['z'],
                        'phase': tx.get('phase', 0.0),
                        'amp': tx.get('amp', 1.0)
                    })

            if not active_tx:
                self.error_sig.emit(f"선택된 {plane_type.upper()} 단면(위치 {slice_pos:.1f} mm) 근처에 트랜스듀서가 없습니다.")
                return

            # 도메인 크기 결정 (U축 가로, Z축 세로)
            u_coords = [t['u'] for t in active_tx]
            z_coords = [t['z'] for t in active_tx]
            
            min_u, max_u = min(u_coords) - 25.0, max(u_coords) + 25.0
            min_z = min(z_coords) - 15.0
            
            # 상단 기구물 고려
            if obstacle_type in [OBSTACLE_TYPES[0], OBSTACLE_TYPES[2]]: # Top Reflector, Enclosure
                max_z = max(max(z_coords) + refl_z + refl_thick + 15.0, max(z_coords) + 50.0)
            else:
                max_z = max(z_coords) + refl_z + 20.0
                
            # 좌우 터널 고려
            if obstacle_type in [OBSTACLE_TYPES[1], OBSTACLE_TYPES[2]]: # Tunnel, Enclosure
                half_w = tunnel_w / 2.0
                min_u = min(min_u, -half_w - 20.0)
                max_u = max(max_u, half_w + 20.0)

            domain_w = max_u - min_u
            domain_h = max_z - min_z
            
            # 그리드 포인트 계산 (짝수 맞춤)
            Nu = int(np.ceil(domain_w / grid_res_mm))
            Nz = int(np.ceil(domain_h / grid_res_mm))
            if Nu % 2 != 0: Nu += 1
            if Nz % 2 != 0: Nz += 1
            
            # 지나치게 큰 그리드 방지 (상한 256x256)
            Nu = min(max(Nu, 64), 220)
            Nz = min(max(Nz, 64), 220)
            
            u_vec = np.linspace(min_u, max_u, Nu) # mm
            z_vec = np.linspace(min_z, max_z, Nz) # mm
            
            kgrid = kWaveGrid(Vector([Nz, Nu]), Vector([dx, dx]))
            
            self.progress_sig.emit(20, "매질 물성치(공기/기구물 계면) 및 기구물 맵 빌드 중...")
            
            # 기본 매질 초기화 (공기)
            c_field = np.full((Nz, Nu), c0, dtype=float)
            alpha_field = np.zeros((Nz, Nu), dtype=float)
            obstacle_mask = np.zeros((Nz, Nu), dtype=bool)

            # 기구물 마스크 생성 (Z축: 인덱스 0이 바닥, Nz-1이 상단)
            # numpy 메쉬그리드
            U_mesh, Z_mesh = np.meshgrid(u_vec, z_vec)
            
            tx_base_z = np.mean(z_coords)
            reflector_abs_z = tx_base_z + refl_z
            
            if obstacle_type == OBSTACLE_TYPES[0]: # 상단 평면 반사판
                obstacle_mask = (Z_mesh >= reflector_abs_z) & (Z_mesh <= reflector_abs_z + refl_thick)
            elif obstacle_type == OBSTACLE_TYPES[1]: # 좌우 가이드 터널
                half_w = tunnel_w / 2.0
                left_wall = (U_mesh <= -half_w) & (U_mesh >= -half_w - refl_thick) & (Z_mesh >= tx_base_z - 5.0) & (Z_mesh <= reflector_abs_z + 10.0)
                right_wall = (U_mesh >= half_w) & (U_mesh <= half_w + refl_thick) & (Z_mesh >= tx_base_z - 5.0) & (Z_mesh <= reflector_abs_z + 10.0)
                obstacle_mask = left_wall | right_wall
            elif obstacle_type == OBSTACLE_TYPES[2]: # 밀폐형 챔버
                half_w = tunnel_w / 2.0
                top_wall = (Z_mesh >= reflector_abs_z) & (Z_mesh <= reflector_abs_z + refl_thick) & (U_mesh >= -half_w - refl_thick) & (U_mesh <= half_w + refl_thick)
                left_wall = (U_mesh <= -half_w) & (U_mesh >= -half_w - refl_thick) & (Z_mesh >= tx_base_z - 5.0) & (Z_mesh <= reflector_abs_z + refl_thick)
                right_wall = (U_mesh >= half_w) & (U_mesh <= half_w + refl_thick) & (Z_mesh >= tx_base_z - 5.0) & (Z_mesh <= reflector_abs_z + refl_thick)
                obstacle_mask = top_wall | left_wall | right_wall

            # 기구물 물성치 매핑
            # 수치 안정성을 위해 의사스펙트럼 계면 스무딩 및 적정 음속/감쇠 매핑
            c_field[obstacle_mask] = c_mat
            alpha_field[obstacle_mask] = alpha_mat
            
            # 스무딩을 통해 FFT 깁스 발산 방지
            c_smooth = smooth(c_field)
            c_smooth = np.clip(c_smooth, 200.0, 7000.0)
            
            if np.any(alpha_field > 0):
                alpha_smooth = smooth(alpha_field)
                alpha_smooth = np.clip(alpha_smooth, 0.0, 30.0)
                medium = kWaveMedium(sound_speed=c_smooth, alpha_coeff=alpha_smooth, alpha_power=1.5)
            else:
                medium = kWaveMedium(sound_speed=c_smooth)

            self.progress_sig.emit(40, "시간 배열 생성 및 40kHz 다채널 위상 소스 신호 합성 중...")
            
            # 시뮬레이션 지속 시간: 10~14 주기 (주기당 25 us)
            T_period = 1.0 / f0
            sim_time = num_cycles * T_period
            
            kgrid.makeTime(c_smooth, cfl=0.15, t_end=sim_time)
            t_array = np.squeeze(kgrid.t_array)
            Nt = len(t_array)

            if self.is_cancelled: return

            # 트랜스듀서 소스 마스크 및 위상 신호 생성
            source_mask = np.zeros((Nz, Nu), dtype=bool)
            element_signals = []
            
            tx_radius_mm = 5.0 # 트랜스듀서 반경 (직경 10mm)
            
            for tx in active_tx:
                u_center = tx['u']
                z_center = tx['z']
                tx_phase = tx['phase']
                tx_amp = tx['amp']
                
                # 트랜스듀서 방출면 셀 탐색
                dist_u = np.abs(u_vec - u_center)
                dist_z = np.abs(z_vec - z_center)
                
                # 방출면 두께 1~2 그리드 셀, 반경 내
                u_indices = np.where(dist_u <= tx_radius_mm)[0]
                z_idx = np.argmin(dist_z)
                
                if len(u_indices) > 0:
                    for ui in u_indices:
                        if not source_mask[z_idx, ui]:
                            source_mask[z_idx, ui] = True
                            # 사인파 음원 신호: A * sin(2*pi*f*t + phase)
                            sig = tx_amp * np.sin(2 * np.pi * f0 * t_array + tx_phase)
                            element_signals.append(sig)

            num_source_points = np.sum(source_mask)
            if num_source_points == 0 or len(element_signals) == 0:
                self.error_sig.emit("격자 내에 배치된 트랜스듀서 소스 포인트를 생성하지 못했습니다.")
                return

            source = kSource()
            source.p_mask = source_mask
            source.p = np.array(element_signals)

            self.progress_sig.emit(60, f"k-Wave FDTD 파동 해석 실행 중 (격자 {Nu}x{Nz}, {Nt} 시간 스텝)...")
            
            sensor = kSensor()
            sensor.mask = np.ones((Nz, Nu), dtype=bool)
            sensor.record = ['p_max', 'p_final']

            t_start = time.time()
            sim_output = kspaceFirstOrder(
                kgrid,
                medium,
                source,
                sensor,
                backend='python',
                device='cpu',
                quiet=True,
                pml_inside=False,
                pml_size=15
            )
            sim_elapsed = time.time() - t_start

            if self.is_cancelled: return

            self.progress_sig.emit(90, "정재파 포락선 및 음향 부상 노드(Trap) 분석 중...")

            # p_max 배열 형상 복원 (방어적 형상 검증)
            p_max_arr = np.asarray(sim_output['p_max'])
            if p_max_arr.shape == (Nz, Nu):
                p_max_raw = p_max_arr
            elif p_max_arr.size == Nz * Nu:
                p_max_raw = p_max_arr.reshape(Nz, Nu)
            elif p_max_arr.ndim == 2:
                p_max_raw = np.zeros((Nz, Nu), dtype=float)
                sh, sw = min(Nz, p_max_arr.shape[0]), min(Nu, p_max_arr.shape[1])
                p_max_raw[:sh, :sw] = p_max_arr[:sh, :sw]
            else:
                p_max_raw = np.zeros((Nz, Nu), dtype=float)

            # p_final 배열 형상 복원 (방어적 형상 검증)
            p_final_arr = np.asarray(sim_output['p_final'])
            if p_final_arr.shape == (Nz, Nu):
                p_final_raw = p_final_arr
            elif p_final_arr.size == Nz * Nu:
                p_final_raw = p_final_arr.reshape(Nz, Nu)
            elif p_final_arr.ndim == 2:
                p_final_raw = np.zeros((Nz, Nu), dtype=float)
                sh, sw = min(Nz, p_final_arr.shape[0]), min(Nu, p_final_arr.shape[1])
                p_final_raw[:sh, :sw] = p_final_arr[:sh, :sw]
            else:
                p_final_raw = np.zeros((Nz, Nu), dtype=float)

            # 축 방향(중심선 U=0 부근) 정재파 프로파일 분석
            center_u_idx = np.argmin(np.abs(u_vec))
            # U=0 주변 3열 평균
            u_range = slice(max(0, center_u_idx - 1), min(Nu, center_u_idx + 2))
            axial_p_max = np.mean(p_max_raw[:, u_range], axis=1)

            # 노드(음압 극소점 = 부상 안정점) 검출
            # 상단 기구물 아래 영역에서만
            valid_z_mask = (z_vec >= min(z_coords) + 5.0) & (z_vec <= reflector_abs_z - 3.0)
            valid_indices = np.where(valid_z_mask)[0]
            
            nodes = []
            antinodes = []
            if len(valid_indices) > 5:
                sub_p = axial_p_max[valid_indices]
                sub_z = z_vec[valid_indices]
                for i in range(1, len(sub_p) - 1):
                    if sub_p[i] < sub_p[i-1] and sub_p[i] < sub_p[i+1]:
                        nodes.append((float(sub_z[i]), float(sub_p[i])))
                    elif sub_p[i] > sub_p[i-1] and sub_p[i] > sub_p[i+1]:
                        antinodes.append((float(sub_z[i]), float(sub_p[i])))

            # SWR (정재파비) 계산
            max_val = float(np.max(p_max_raw))
            min_val = float(np.min(p_max_raw))
            swr = max_val / max(min_val, 1e-4)

            # 음향 임피던스 및 이론적 반사율 계산
            z_air = rho0 * c0 # 411.6
            z_solid = rho_mat * c_mat
            refl_coeff = abs(z_solid - z_air) / (z_solid + z_air) * 100.0

            result = {
                'u_vec': u_vec,
                'z_vec': z_vec,
                'p_max': p_max_raw,
                'p_final': p_final_raw,
                'axial_p_max': axial_p_max,
                'nodes': nodes,
                'antinodes': antinodes,
                'obstacle_mask': obstacle_mask,
                'reflector_z': reflector_abs_z,
                'refl_thick': refl_thick,
                'swr': swr,
                'max_p': max_val,
                'refl_coeff': refl_coeff,
                'sim_elapsed': sim_elapsed,
                'plane_type': plane_type,
                'slice_pos': slice_pos,
                'obstacle_type': obstacle_type,
                'material_name': self.params.get('material_name', '아크릴')
            }

            self.progress_sig.emit(100, f"해석 완료! (소요 시간: {sim_elapsed:.2f}초)")
            self.finished_sig.emit(result)

        except Exception as e:
            import traceback
            err_details = traceback.format_exc()
            self.error_sig.emit(f"시뮬레이션 중 오류가 발생했습니다:\n{str(e)}\n\n{err_details}")


# ============================================================================
# 3. k-Wave 기구물 시뮬레이션 및 분석 대화상자 (KWaveDialog)
# ============================================================================
class KWaveDialog(QDialog):
    def __init__(self, parent=None, transducer_actors=None):
        super().__init__(parent)
        self.setWindowTitle("k-Wave 기구물(반사판/터널) 음향 전파 및 정재파 해석")
        self.resize(1200, 800)
        
        self.transducer_actors = transducer_actors or []
        self.sim_worker: Optional[KWaveSimWorker] = None
        self.last_result: Optional[dict] = None

        self.init_ui()
        self.update_material_fields()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # --------------------------------------------------------------------
        # 좌측: 시뮬레이션 설정 및 파라미터 패널
        # --------------------------------------------------------------------
        left_panel = QFrame()
        left_panel.setFixedWidth(400)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. 기구물 형상 설정 그룹
        geom_group = QGroupBox("1. 기구물(Obstacle) 기하 형상 설정")
        geom_lyt = QGridLayout(geom_group)
        geom_lyt.setSpacing(8)

        geom_lyt.addWidget(QLabel("기구물 유형:"), 0, 0)
        self.cb_obstacle_type = QComboBox()
        self.cb_obstacle_type.addItems(OBSTACLE_TYPES)
        self.cb_obstacle_type.currentIndexChanged.connect(self.on_obstacle_changed)
        geom_lyt.addWidget(self.cb_obstacle_type, 0, 1)

        self.lbl_refl_z = QLabel("반사판 높이 (Z 거리):")
        geom_lyt.addWidget(self.lbl_refl_z, 1, 0)
        self.spin_refl_z = QDoubleSpinBox()
        self.spin_refl_z.setRange(20.0, 200.0)
        self.spin_refl_z.setValue(60.0)
        self.spin_refl_z.setSuffix(" mm")
        geom_lyt.addWidget(self.spin_refl_z, 1, 1)

        self.lbl_refl_thick = QLabel("기구물 판재 두께:")
        geom_lyt.addWidget(self.lbl_refl_thick, 2, 0)
        self.spin_refl_thick = QDoubleSpinBox()
        self.spin_refl_thick.setRange(2.0, 30.0)
        self.spin_refl_thick.setValue(8.0)
        self.spin_refl_thick.setSuffix(" mm")
        geom_lyt.addWidget(self.spin_refl_thick, 2, 1)

        self.lbl_tunnel_w = QLabel("가이드 터널 폭:")
        geom_lyt.addWidget(self.lbl_tunnel_w, 3, 0)
        self.spin_tunnel_w = QDoubleSpinBox()
        self.spin_tunnel_w.setRange(30.0, 200.0)
        self.spin_tunnel_w.setValue(60.0)
        self.spin_tunnel_w.setSuffix(" mm")
        geom_lyt.addWidget(self.spin_tunnel_w, 3, 1)

        left_layout.addWidget(geom_group)

        # 2. 기구물 재질 물성치 그룹
        mat_group = QGroupBox("2. 기구물 재질(Material) 물성치")
        mat_lyt = QGridLayout(mat_group)
        mat_lyt.setSpacing(8)

        mat_lyt.addWidget(QLabel("재질 선택:"), 0, 0)
        self.cb_material = QComboBox()
        self.cb_material.addItems(list(MATERIALS.keys()))
        self.cb_material.currentIndexChanged.connect(self.update_material_fields)
        mat_lyt.addWidget(self.cb_material, 0, 1)

        mat_lyt.addWidget(QLabel("음속 (Sound Speed):"), 1, 0)
        self.spin_c = QDoubleSpinBox()
        self.spin_c.setRange(100.0, 8000.0)
        self.spin_c.setSuffix(" m/s")
        mat_lyt.addWidget(self.spin_c, 1, 1)

        mat_lyt.addWidget(QLabel("밀도 (Density):"), 2, 0)
        self.spin_rho = QDoubleSpinBox()
        self.spin_rho.setRange(10.0, 10000.0)
        self.spin_rho.setSuffix(" kg/m³")
        mat_lyt.addWidget(self.spin_rho, 2, 1)

        mat_lyt.addWidget(QLabel("감쇠율 (Alpha Coeff):"), 3, 0)
        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.0, 30.0)
        self.spin_alpha.setSingleStep(0.1)
        self.spin_alpha.setSuffix(" dB/MHz/cm")
        mat_lyt.addWidget(self.spin_alpha, 3, 1)

        self.lbl_mat_desc = QLabel()
        self.lbl_mat_desc.setWordWrap(True)
        self.lbl_mat_desc.setStyleSheet("color: #555; font-size: 11px; padding: 4px; background: #F5F5F5; border-radius: 4px;")
        mat_lyt.addWidget(self.lbl_mat_desc, 4, 0, 1, 2)

        left_layout.addWidget(mat_group)

        # 3. 단면 및 해석 정밀도 그룹
        calc_group = QGroupBox("3. 2D 해석 단면 및 FDTD 정밀도")
        calc_lyt = QGridLayout(calc_group)
        calc_lyt.setSpacing(8)

        calc_lyt.addWidget(QLabel("단면 평면:"), 0, 0)
        self.cb_plane = QComboBox()
        self.cb_plane.addItems(["XZ 평면 (X-축 가로, Z-축 상하)", "YZ 평면 (Y-축 가로, Z-축 상하)"])
        calc_lyt.addWidget(self.cb_plane, 0, 1)

        calc_lyt.addWidget(QLabel("단면 슬라이스 위치:"), 1, 0)
        self.spin_slice_pos = QDoubleSpinBox()
        self.spin_slice_pos.setRange(-200.0, 200.0)
        self.spin_slice_pos.setValue(0.0)
        self.spin_slice_pos.setSuffix(" mm")
        calc_lyt.addWidget(self.spin_slice_pos, 1, 1)

        calc_lyt.addWidget(QLabel("격자 해상도 (dx):"), 2, 0)
        self.cb_grid_res = QComboBox()
        self.cb_grid_res.addItem("고속 해석 (1.2 mm - 5~8초)", 1.2)
        self.cb_grid_res.addItem("표준 정밀도 (1.0 mm - 10~15초)", 1.0)
        self.cb_grid_res.addItem("고정밀 해석 (0.8 mm - 20~30초)", 0.8)
        self.cb_grid_res.setCurrentIndex(1)
        calc_lyt.addWidget(self.cb_grid_res, 2, 1)

        calc_lyt.addWidget(QLabel("시뮬레이션 지속 주기:"), 3, 0)
        self.spin_cycles = QSpinBox()
        self.spin_cycles.setRange(6, 20)
        self.spin_cycles.setValue(10)
        self.spin_cycles.setSuffix(" Cycles (40kHz)")
        calc_lyt.addWidget(self.spin_cycles, 3, 1)

        left_layout.addWidget(calc_group)

        # 4. 제어 및 프로그레스
        btn_lyt = QHBoxLayout()
        self.btn_run = QPushButton("k-Wave FDTD 해석 시작")
        self.btn_run.setFixedHeight(34)
        self.btn_run.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; font-size: 13px; border-radius: 4px;")
        self.btn_run.clicked.connect(self.start_simulation)
        btn_lyt.addWidget(self.btn_run)

        self.btn_cancel = QPushButton("중지")
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet("background-color: #C62828; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_cancel.clicked.connect(self.cancel_simulation)
        btn_lyt.addWidget(self.btn_cancel)
        left_layout.addLayout(btn_lyt)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        left_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("대기 중... 트랜스듀서 배치 및 파라미터를 확인하고 해석을 시작하세요.")
        self.lbl_status.setStyleSheet("color: #666; font-size: 11px;")
        self.lbl_status.setWordWrap(True)
        left_layout.addWidget(self.lbl_status)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # --------------------------------------------------------------------
        # 우측: Matplotlib 캔버스 시각화 및 공학 진단 카드
        # --------------------------------------------------------------------
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # 탭 위젯 (결과 시각화 모드 전환)
        self.tabs = QTabWidget()
        
        # 탭 1: 정재파 음압 분포 (|P|)
        self.fig_standing = Figure(figsize=(7, 5), dpi=100)
        self.canvas_standing = FigureCanvas(self.fig_standing)
        self.tabs.addTab(self.canvas_standing, "정재파 음압 진폭 (|P|)")

        # 탭 2: 축 방향 프로파일 및 트랩 노드 분석
        self.fig_axial = Figure(figsize=(7, 5), dpi=100)
        self.canvas_axial = FigureCanvas(self.fig_axial)
        self.tabs.addTab(self.canvas_axial, "중심축 음압 프로파일 (Trap 노드 분석)")

        # 탭 3: 순간 음압 파면 (Wavefront)
        self.fig_wavefront = Figure(figsize=(7, 5), dpi=100)
        self.canvas_wavefront = FigureCanvas(self.fig_wavefront)
        self.tabs.addTab(self.canvas_wavefront, "순간 파면 (Wavefront)")

        right_layout.addWidget(self.tabs, stretch=1)

        # 하단 엔지니어링 분석 요약 카드
        self.diag_card = QFrame()
        self.diag_card.setStyleSheet("background-color: #FAFAFA; border: 1px solid #E0E0E0; border-radius: 6px; padding: 8px;")
        diag_lyt = QHBoxLayout(self.diag_card)
        diag_lyt.setContentsMargins(10, 6, 10, 6)

        self.lbl_diag_grade = QLabel("해석 상태: 대기")
        self.lbl_diag_grade.setStyleSheet("font-size: 13px; font-weight: bold; color: #424242;")
        diag_lyt.addWidget(self.lbl_diag_grade)

        diag_lyt.addStretch()

        self.lbl_diag_metrics = QLabel("최대 음압: - | 정재파비: - | 트랩 노드: - | 재질 반사율: -")
        self.lbl_diag_metrics.setStyleSheet("font-size: 12px; color: #37474F;")
        diag_lyt.addWidget(self.lbl_diag_metrics)

        diag_lyt.addStretch()

        self.btn_export_plot = QPushButton("그래프 이미지 저장")
        self.btn_export_plot.setEnabled(False)
        self.btn_export_plot.clicked.connect(self.export_plot_image)
        diag_lyt.addWidget(self.btn_export_plot)

        self.btn_export_data = QPushButton("음압 데이터 (*.csv)")
        self.btn_export_data.setEnabled(False)
        self.btn_export_data.clicked.connect(self.export_csv_data)
        diag_lyt.addWidget(self.btn_export_data)

        right_layout.addWidget(self.diag_card)

        main_layout.addWidget(right_panel, stretch=1)

        # 초기 안내 화면 플롯
        self.draw_initial_placeholder()

    def on_obstacle_changed(self, idx):
        obs_type = self.cb_obstacle_type.currentText()
        if obs_type == OBSTACLE_TYPES[0]: # 상단 반사판
            self.lbl_refl_z.show(); self.spin_refl_z.show()
            self.lbl_refl_thick.show(); self.spin_refl_thick.show()
            self.lbl_tunnel_w.hide(); self.spin_tunnel_w.hide()
        elif obs_type == OBSTACLE_TYPES[1]: # 좌우 터널
            self.lbl_refl_z.show(); self.spin_refl_z.show()
            self.lbl_refl_thick.show(); self.spin_refl_thick.show()
            self.lbl_tunnel_w.show(); self.spin_tunnel_w.show()
        elif obs_type == OBSTACLE_TYPES[2]: # 밀폐 챔버
            self.lbl_refl_z.show(); self.spin_refl_z.show()
            self.lbl_refl_thick.show(); self.spin_refl_thick.show()
            self.lbl_tunnel_w.show(); self.spin_tunnel_w.show()
        else: # 기구물 없음
            self.lbl_refl_z.hide(); self.spin_refl_z.hide()
            self.lbl_refl_thick.hide(); self.spin_refl_thick.hide()
            self.lbl_tunnel_w.hide(); self.spin_tunnel_w.hide()

    def update_material_fields(self):
        mat_name = self.cb_material.currentText()
        mat_info = MATERIALS.get(mat_name, MATERIALS["아크릴 (Acrylic / PMMA)"])
        
        self.spin_c.setValue(mat_info['sound_speed'])
        self.spin_rho.setValue(mat_info['density'])
        self.spin_alpha.setValue(mat_info['alpha'])
        self.lbl_mat_desc.setText(mat_info['desc'])

        # Custom일 때만 직접 입력 허용
        is_custom = (mat_name == "사용자 정의 (Custom)")
        self.spin_c.setReadOnly(not is_custom)
        self.spin_rho.setReadOnly(not is_custom)
        self.spin_alpha.setReadOnly(not is_custom)

    def draw_initial_placeholder(self):
        # 1. 정재파 진폭 탭
        self.fig_standing.clear()
        ax1 = self.fig_standing.subplots()
        ax1.text(0.5, 0.5, "k-Wave FDTD 시뮬레이션을 실행하면\n여기에 정재파 음압장 히트맵이 표시됩니다.\n\n좌측의 [k-Wave FDTD 해석 시작] 버튼을 클릭하세요.",
                 horizontalalignment='center', verticalalignment='center',
                 transform=ax1.transAxes, color='#555555', fontsize=12, linespacing=1.6)
        ax1.set_axis_off()
        self.canvas_standing.draw()

        # 2. 중심축 프로파일 탭
        self.fig_axial.clear()
        ax2 = self.fig_axial.subplots()
        ax2.text(0.5, 0.5, "해석 완료 후 중심축(Z축)을 따른\n정재파 음압 분포 및 부상 트랩 노드가 표시됩니다.",
                 horizontalalignment='center', verticalalignment='center',
                 transform=ax2.transAxes, color='#555555', fontsize=12, linespacing=1.6)
        ax2.set_axis_off()
        self.canvas_axial.draw()

        # 3. 순간 파면 탭
        self.fig_wavefront.clear()
        ax3 = self.fig_wavefront.subplots()
        ax3.text(0.5, 0.5, "해석 완료 후 순간 파면(Wavefront) 스냅샷이 표시됩니다.",
                 horizontalalignment='center', verticalalignment='center',
                 transform=ax3.transAxes, color='#555555', fontsize=12, linespacing=1.6)
        ax3.set_axis_off()
        self.canvas_wavefront.draw()

    def start_simulation(self):
        if not self.transducer_actors:
            QMessageBox.warning(self, "경고", "배치된 트랜스듀서가 없습니다. 메인 뷰어에서 트랜스듀서를 먼저 배치하세요.")
            return

        tx_list = []
        for a in self.transducer_actors:
            c = a.center
            p = getattr(a, '_phase', 0.0)
            amp = getattr(a, '_amplitude', 1.0)
            tx_list.append({
                'x': float(c[0]),
                'y': float(c[1]),
                'z': float(c[2]),
                'phase': float(p),
                'amp': float(amp)
            })

        mat_name = self.cb_material.currentText()
        mat_info = {
            'sound_speed': self.spin_c.value(),
            'density': self.spin_rho.value(),
            'alpha': self.spin_alpha.value(),
            'desc': self.lbl_mat_desc.text()
        }

        plane_type = 'xz' if self.cb_plane.currentIndex() == 0 else 'yz'
        grid_res = self.cb_grid_res.currentData()

        params = {
            'transducers': tx_list,
            'plane_type': plane_type,
            'slice_pos': self.spin_slice_pos.value(),
            'obstacle_type': self.cb_obstacle_type.currentText(),
            'material_name': mat_name,
            'material_info': mat_info,
            'refl_z': self.spin_refl_z.value(),
            'refl_thick': self.spin_refl_thick.value(),
            'tunnel_w': self.spin_tunnel_w.value(),
            'grid_res_mm': grid_res,
            'num_cycles': self.spin_cycles.value()
        }

        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("k-Wave FDTD 시뮬레이션 준비 중...")

        self.sim_worker = KWaveSimWorker(params)
        self.sim_worker.progress_sig.connect(self.on_sim_progress)
        self.sim_worker.finished_sig.connect(self.on_sim_finished)
        self.sim_worker.error_sig.connect(self.on_sim_error)
        self.sim_worker.start()

    def cancel_simulation(self):
        if self.sim_worker and self.sim_worker.isRunning():
            self.sim_worker.cancel()
            self.lbl_status.setText("시뮬레이션 취소 요청됨...")
            self.btn_cancel.setEnabled(False)

    def on_sim_progress(self, val: int, msg: str):
        self.progress_bar.setValue(val)
        self.lbl_status.setText(msg)

    def on_sim_finished(self, result: dict):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_export_plot.setEnabled(True)
        self.btn_export_data.setEnabled(True)
        self.last_result = result

        # 플롯 렌더링
        self.render_results(result)

        # 공학 지표 업데이트
        swr = result['swr']
        num_nodes = len(result['nodes'])
        refl_coeff = result['refl_coeff']
        max_p = result['max_p']
        elapsed = result['sim_elapsed']

        # 4단계 엔지니어링 안정성 등급 판정
        if swr >= 4.0 and num_nodes >= 2:
            grade_str = "[최적 85%+] 강력한 정재파 형성 및 다중 부상 트랩 확보"
            grade_color = "#2E7D32" # Dark Green
        elif swr >= 2.5:
            grade_str = "[안정 60~84%] 부상 트랩 형성 가능, 안정성 양호"
            grade_color = "#1565C0" # Blue
        elif swr >= 1.5:
            grade_str = "[주의 40~59%] 반사파 간섭 미약, 위치 조정 권장"
            grade_color = "#EF6C00" # Orange
        else:
            grade_str = "[위험 <40%] 정재파 미형성 (진행파 우세), 부상 불안정"
            grade_color = "#C62828" # Red

        self.lbl_diag_grade.setText(f"평가: {grade_str}")
        self.lbl_diag_grade.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {grade_color};")

        self.lbl_diag_metrics.setText(
            f"최대 음압: {max_p:.2f} Pa(rel) | 정재파비(SWR): {swr:.2f} | "
            f"검출 노드(트랩): {num_nodes}개 | 재질 반사율: {refl_coeff:.2f}% ({result['material_name']}) | 해석: {elapsed:.2f}s"
        )

    def on_sim_error(self, err_msg: str):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("오류로 인해 해석이 중단되었습니다.")
        QMessageBox.critical(self, "시뮬레이션 오류", err_msg)

    def render_results(self, res: dict):
        u_vec = res['u_vec']
        z_vec = res['z_vec']
        p_max = res['p_max']
        p_final = res['p_final']
        obs_mask = res['obstacle_mask']
        axial_p = res['axial_p_max']
        nodes = res['nodes']
        antinodes = res['antinodes']
        plane_type = res['plane_type'].upper()
        slice_pos = res['slice_pos']

        extent = [u_vec[0], u_vec[-1], z_vec[0], z_vec[-1]]

        # --------------------------------------------------------------------
        # 1. 정재파 음압 진폭 (|P|) 히트맵
        # --------------------------------------------------------------------
        self.fig_standing.clear()
        ax1 = self.fig_standing.subplots()
        im1 = ax1.imshow(p_max, origin='lower', extent=extent, cmap='hot', aspect='auto')
        cbar1 = self.fig_standing.colorbar(im1, ax=ax1)
        cbar1.set_label("Acoustic Pressure Amplitude [Rel. Pa]")

        # 기구물 마스크 윤곽선 오버레이
        if np.any(obs_mask):
            ax1.contour(U := np.linspace(extent[0], extent[1], obs_mask.shape[1]),
                        Z := np.linspace(extent[2], extent[3], obs_mask.shape[0]),
                        obs_mask, levels=[0.5], colors=['cyan'], linewidths=1.5, linestyles='--')
            # 기구물 영역 텍스트 표기
            ax1.text(0.5, 0.95, f"[기구물: {res['material_name']}]", transform=ax1.transAxes,
                     color='cyan', fontsize=10, horizontalalignment='center',
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.6))

        # 노드(부상 트랩 안정점) 십자선 마킹
        for nz, np_val in nodes:
            ax1.plot(0.0, nz, 'g+', markersize=12, markeredgewidth=2)
            ax1.text(2.0, nz, f"Trap Node (Z={nz:.1f})", color='#00E676', fontsize=8, verticalalignment='center')

        u_label = "X-Position [mm]" if plane_type == 'XZ' else "Y-Position [mm]"
        ax1.set_xlabel(u_label)
        ax1.set_ylabel("Z-Position (Height) [mm]")
        ax1.set_title(f"Standing Wave Acoustic Field (|P|) - {plane_type} Slice @ {slice_pos:.1f} mm")
        ax1.grid(True, linestyle=':', alpha=0.4)
        self.fig_standing.tight_layout()
        self.canvas_standing.draw()

        # --------------------------------------------------------------------
        # 2. 중심축 음압 프로파일 (노드 및 안티노드 분석)
        # --------------------------------------------------------------------
        self.fig_axial.clear()
        ax2 = self.fig_axial.subplots()
        ax2.plot(z_vec, axial_p, 'b-', linewidth=2.0, label="Axial Pressure Profile (U=0)")

        # 노드 및 안티노드 마커
        if nodes:
            node_z = [n[0] for n in nodes]
            node_p = [n[1] for n in nodes]
            ax2.plot(node_z, node_p, 'go', markersize=8, label="Levitation Node (Trap Min)")

        if antinodes:
            anode_z = [an[0] for an in antinodes]
            anode_p = [an[1] for an in antinodes]
            ax2.plot(anode_z, anode_p, 'r^', markersize=8, label="Antinode (Max)")

        # 반사판 위치 선
        refl_z = res.get('reflector_z', None)
        if refl_z and refl_z <= z_vec[-1]:
            ax2.axvline(refl_z, color='c', linestyle='--', linewidth=1.5, label=f"Reflector Boundary ({refl_z:.1f} mm)")

        ax2.set_xlabel("Z-Position (Height) [mm]")
        ax2.set_ylabel("Acoustic Pressure Amplitude [Rel. Pa]")
        ax2.set_title("Axial Standing Wave Distribution & Acoustic Traps")
        ax2.grid(True, linestyle=':', alpha=0.6)
        ax2.legend(loc='upper right')
        self.fig_axial.tight_layout()
        self.canvas_axial.draw()

        # --------------------------------------------------------------------
        # 3. 순간 음압 파면 (Wavefront)
        # --------------------------------------------------------------------
        self.fig_wavefront.clear()
        ax3 = self.fig_wavefront.subplots()
        vmax = max(abs(np.min(p_final)), abs(np.max(p_final)))
        im3 = ax3.imshow(p_final, origin='lower', extent=extent, cmap='RdBu_r', vmin=-vmax, vmax=vmax, aspect='auto')
        cbar3 = self.fig_wavefront.colorbar(im3, ax=ax3)
        cbar3.set_label("Instantaneous Acoustic Pressure [Rel. Pa]")

        if np.any(obs_mask):
            ax3.contour(np.linspace(extent[0], extent[1], obs_mask.shape[1]),
                        np.linspace(extent[2], extent[3], obs_mask.shape[0]),
                        obs_mask, levels=[0.5], colors=['black'], linewidths=1.5, linestyles='--')

        ax3.set_xlabel(u_label)
        ax3.set_ylabel("Z-Position (Height) [mm]")
        ax3.set_title(f"Instantaneous Wavefront Snapshot (t_final) - {plane_type} Slice")
        ax3.grid(True, linestyle=':', alpha=0.4)
        self.fig_wavefront.tight_layout()
        self.canvas_wavefront.draw()

    def export_plot_image(self):
        if not self.last_result: return
        file_path, _ = QFileDialog.getSaveFileName(self, "시뮬레이션 그래프 저장", "kwave_acoustic_simulation.png", "PNG Image (*.png);;PDF Document (*.pdf)")
        if not file_path: return
        
        # 현재 활성화된 탭의 그림 저장
        cur_idx = self.tabs.currentIndex()
        if cur_idx == 0:
            self.fig_standing.savefig(file_path, dpi=300)
        elif cur_idx == 1:
            self.fig_axial.savefig(file_path, dpi=300)
        else:
            self.fig_wavefront.savefig(file_path, dpi=300)
            
        QMessageBox.information(self, "완료", f"선택한 그래프가 성공적으로 저장되었습니다:\n{file_path}")

    def export_csv_data(self):
        if not self.last_result: return
        file_path, _ = QFileDialog.getSaveFileName(self, "음압장 격자 데이터 내보내기", "kwave_pressure_field.csv", "CSV File (*.csv);;NumPy Zip (*.npz)")
        if not file_path: return

        if file_path.endswith('.npz'):
            np.savez_compressed(
                file_path,
                u_vec=self.last_result['u_vec'],
                z_vec=self.last_result['z_vec'],
                p_max=self.last_result['p_max'],
                p_final=self.last_result['p_final'],
                axial_p=self.last_result['axial_p_max']
            )
        else:
            # CSV로 Z, U, p_max 저장
            u_vec = self.last_result['u_vec']
            z_vec = self.last_result['z_vec']
            p_max = self.last_result['p_max']
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# k-Wave Acoustic Simulation Pressure Field Export\n")
                f.write(f"# Plane: {self.last_result['plane_type'].upper()}, Slice: {self.last_result['slice_pos']:.2f} mm\n")
                f.write(f"# Material: {self.last_result['material_name']}, Obstacle: {self.last_result['obstacle_type']}\n")
                f.write("Z_mm, " + ", ".join([f"U_{u:.2f}mm" for u in u_vec]) + "\n")
                for zi, z_val in enumerate(z_vec):
                    row_vals = [f"{z_val:.3f}"] + [f"{p:.5e}" for p in p_max[zi, :]]
                    f.write(", ".join(row_vals) + "\n")

        QMessageBox.information(self, "완료", f"음압 데이터가 성공적으로 내보내졌습니다:\n{file_path}")
