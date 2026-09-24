import numpy as np
import pyvista as pv

def calculate_pressure_field(grid_x, grid_y, grid_z, transducers, frequency=40000, speed_of_sound=343.0):
    """
    레일리 적분(Rayleigh integral)의 점음원(Point-source) 근사를 이용한 음압 계산 함수.
    
    transducers: 'pos'(위치 튜플), 'phase'(위상 지연, 라디안), 'amp'(진폭)을 갖는 딕셔너리 리스트
    """
    omega = 2 * np.pi * frequency
    k = omega / speed_of_sound # 파수(Wave number)
    
    # 복소수 음압 필드 초기화
    p_complex = np.zeros_like(grid_x, dtype=np.complex128)
    
    for tr in transducers:
        tx, ty, tz = tr['pos']
        phase = tr['phase']
        amp = tr['amp']
        
        # 트랜스듀서에서 각 그리드 포인트까지의 거리 계산
        r = np.sqrt((grid_x - tx)**2 + (grid_y - ty)**2 + (grid_z - tz)**2)
        r[r == 0] = 1e-9 # 0으로 나누는 오류 방지
        
        # 음압 = (A / r) * exp(i * (k * r + phase))
        p_complex += (amp / r) * np.exp(1j * (k * r + phase))
        
    # 절대 음압 크기 계산
    p_amp = np.abs(p_complex)
    return p_amp

# PyVista 시각화 예제
if __name__ == "__main__":
    # 시각화를 위한 2D 그리드 단면 생성 (예: y=0 단면, xz 평면)
    # 20cm x 20cm 공간
    x = np.linspace(-0.1, 0.1, 100) 
    z = np.linspace(0, 0.2, 100)
    
    # 2D 단면이므로 meshgrid 후 flatten 시 y는 0으로 채움
    xx, zz = np.meshgrid(x, z, indexing='ij')
    yy = np.zeros_like(xx)
    
    # 간단한 2개의 트랜스듀서 배열 생성 (간섭무늬 확인용)
    transducers = [
        {'pos': (-0.05, 0, 0), 'phase': 0, 'amp': 1.0},
        {'pos': (0.05, 0, 0), 'phase': 0, 'amp': 1.0}
    ]
    
    # 음압 계산
    p_amp = calculate_pressure_field(xx, yy, zz, transducers)
    
    # PyVista StructuredGrid 생성 (데이터 형태를 맞추기 위해 x, y, z 차원 추가)
    # PyVista는 (nx, ny, nz) 형태의 grid를 요구하므로 (100, 1, 100) 형태로 구성
    grid = pv.StructuredGrid(xx[:, np.newaxis, :], yy[:, np.newaxis, :], zz[:, np.newaxis, :])
    
    # 스칼라 데이터 주입
    grid.point_data["Pressure"] = p_amp.flatten(order="F")
    
    # 시각화 설정
    plotter = pv.Plotter(title="Acoustic Pressure Field Visualization")
    
    # 음압 분포 맵핑
    plotter.add_mesh(grid, scalars="Pressure", cmap="jet", show_scalar_bar=True, opacity=0.8)
    
    # 트랜스듀서 위치 표시
    for tr in transducers:
        sphere = pv.Sphere(radius=0.005, center=tr['pos'])
        plotter.add_mesh(sphere, color='red')
        
    # 카메라 뷰 설정
    plotter.view_xz()
    plotter.show()
