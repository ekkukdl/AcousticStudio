import os
import ctypes
import numpy as np

_cpp_lib = None
_lib_path = os.path.join(os.path.dirname(__file__), "sonic_core.dll")

if os.path.exists(_lib_path):
    try:
        _cpp_lib = ctypes.CDLL(_lib_path)
        _cpp_lib.calculate_phases_and_packet.argtypes = [
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'), # cx
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'), # cy
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'), # cz
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'), # tx
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'), # ty
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'), # tz
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'), # amplitudes
            ctypes.c_int, # num_transducers
            ctypes.c_int, # num_points
            ctypes.c_int, # algorithm
            ctypes.c_double, # k
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'), # out_phases
            np.ctypeslib.ndpointer(dtype=np.uint8, ndim=1, flags='C_CONTIGUOUS'),   # out_packet
        ]
        _cpp_lib.calculate_phases_and_packet.restype = None
        
        _cpp_lib.calculate_field_slice.argtypes = [
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_double,
            np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),
        ]
        _cpp_lib.calculate_field_slice.restype = None
    except Exception as e:
        print(f"[SonicSurface C++] Failed to load DLL: {e}")
        _cpp_lib = None

def calculate_phases_sonic(cx, cy, cz, tx, ty, tz, amplitudes, algorithm_str, k):
    """
    algorithm: 1 for Twin Trap, 2 for Vortex Trap, 0 for others
    Returns (phases_array, packet_bytes)
    """
    if _cpp_lib is None:
        return None, None # C++ DLL not found, fallback to numpy
        
    num_transducers = len(cx)
    num_points = len(tx)
    
    algo_int = 0
    if "Twin Trap" in algorithm_str:
        algo_int = 1
    elif "Vortex Trap" in algorithm_str:
        algo_int = 2
        
    out_phases = np.zeros(num_transducers, dtype=np.float64)
    out_packet = np.zeros(num_transducers + 2, dtype=np.uint8) # [254, data..., 253]
    
    _cpp_lib.calculate_phases_and_packet(
        np.ascontiguousarray(cx, dtype=np.float64),
        np.ascontiguousarray(cy, dtype=np.float64),
        np.ascontiguousarray(cz, dtype=np.float64),
        np.ascontiguousarray(tx, dtype=np.float64),
        np.ascontiguousarray(ty, dtype=np.float64),
        np.ascontiguousarray(tz, dtype=np.float64),
        np.ascontiguousarray(amplitudes, dtype=np.float64),
        num_transducers,
        num_points,
        algo_int,
        k,
        out_phases,
        out_packet
    )
    
    return out_phases, out_packet.tobytes()

def calculate_field_slice_sonic(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k):
    if _cpp_lib is None or not hasattr(_cpp_lib, 'calculate_field_slice'):
        return None
        
    num_pts = len(pts_x)
    num_tx = len(tx_x)
    out_pressure = np.zeros(num_pts, dtype=np.float64)
    
    _cpp_lib.calculate_field_slice(
        np.ascontiguousarray(pts_x, dtype=np.float64),
        np.ascontiguousarray(pts_y, dtype=np.float64),
        np.ascontiguousarray(pts_z, dtype=np.float64),
        np.ascontiguousarray(tx_x, dtype=np.float64),
        np.ascontiguousarray(tx_y, dtype=np.float64),
        np.ascontiguousarray(tx_z, dtype=np.float64),
        np.ascontiguousarray(tx_phases, dtype=np.float64),
        np.ascontiguousarray(tx_amplitudes, dtype=np.float64),
        num_pts,
        num_tx,
        k,
        out_pressure
    )
    return out_pressure

# --- GPU Acceleration via PyTorch ---
try:
    import torch
    _has_torch = True
    _has_cuda = torch.cuda.is_available()
except ImportError:
    _has_torch = False
    _has_cuda = False

def is_gpu_available():
    return _has_torch and _has_cuda

def calculate_phases_gpu(cx, cy, cz, tx, ty, tz, amplitudes, algorithm_str, k):
    if not is_gpu_available():
        return None, None
        
    device = torch.device('cuda')
    
    # cx, cy, cz: (N,) transducers
    # tx, ty, tz: (M,) target points
    cx_t = torch.tensor(cx, dtype=torch.float64, device=device)
    cy_t = torch.tensor(cy, dtype=torch.float64, device=device)
    cz_t = torch.tensor(cz, dtype=torch.float64, device=device)
    
    tx_t = torch.tensor(tx, dtype=torch.float64, device=device).unsqueeze(1) # (M, 1)
    ty_t = torch.tensor(ty, dtype=torch.float64, device=device).unsqueeze(1)
    tz_t = torch.tensor(tz, dtype=torch.float64, device=device).unsqueeze(1)
    
    amp_t = torch.tensor(amplitudes, dtype=torch.float64, device=device)
    
    dx = cx_t.unsqueeze(0) - tx_t # (M, N)
    dy = cy_t.unsqueeze(0) - ty_t
    dz = cz_t.unsqueeze(0) - tz_t
    
    d = torch.sqrt(dx**2 + dy**2 + dz**2)
    phase_focal = -d * k
    
    signature = torch.zeros_like(dx)
    if "Twin Trap" in algorithm_str:
        signature = torch.where(dx > 0, torch.tensor(np.pi, dtype=torch.float64, device=device), torch.tensor(0.0, dtype=torch.float64, device=device))
    elif "Vortex Trap" in algorithm_str:
        signature = torch.atan2(dy, dx)
        
    pt_phase = phase_focal + signature
    
    # complex sum across points
    complex_p = torch.zeros(len(cx), dtype=torch.complex128, device=device)
    for p_idx in range(len(tx)):
        complex_p += amp_t * torch.exp(1j * pt_phase[p_idx])
        
    total_phases = torch.angle(complex_p) % (2.0 * np.pi)
    total_phases[total_phases < 0] += 2.0 * np.pi
    
    # Hardware packet mapping
    phase_disc = torch.round((total_phases / (2.0 * np.pi)) * 32.0).to(torch.int32)
    phase_disc = torch.clamp(phase_disc, 0, 31)
    
    packet = bytearray([254]) + bytearray(phase_disc.cpu().numpy().astype(np.uint8)) + bytearray([253])
    return total_phases.cpu().numpy(), bytes(packet)

def calculate_field_slice_gpu(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k):
    if not is_gpu_available():
        return None
        
    device = torch.device('cuda')
    
    # pts: (P,) grid points
    # tx: (N,) transducers
    px = torch.tensor(pts_x, dtype=torch.float64, device=device).unsqueeze(1) # (P, 1)
    py = torch.tensor(pts_y, dtype=torch.float64, device=device).unsqueeze(1)
    pz = torch.tensor(pts_z, dtype=torch.float64, device=device).unsqueeze(1)
    
    cx = torch.tensor(tx_x, dtype=torch.float64, device=device).unsqueeze(0) # (1, N)
    cy = torch.tensor(tx_y, dtype=torch.float64, device=device).unsqueeze(0)
    cz = torch.tensor(tx_z, dtype=torch.float64, device=device).unsqueeze(0)
    
    tx_p = torch.tensor(tx_phases, dtype=torch.float64, device=device).unsqueeze(0)
    tx_a = torch.tensor(tx_amplitudes, dtype=torch.float64, device=device).unsqueeze(0)
    
    dx = px - cx # (P, N)
    dy = py - cy
    dz = pz - cz
    
    dist = torch.sqrt(dx**2 + dy**2 + dz**2)
    dist = torch.clamp(dist, min=1e-3)
    
    amp = tx_a / dist
    phase = k * dist + tx_p
    
    real_sum = torch.sum(amp * torch.cos(phase), dim=1) # (P,)
    imag_sum = torch.sum(amp * torch.sin(phase), dim=1)
    
    return real_sum.cpu().numpy(), imag_sum.cpu().numpy()

def get_cpu_name():
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0')
        cpu_name = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
        return cpu_name
    except:
        import platform
        return platform.processor()

def get_gpu_name():
    if is_gpu_available():
        import torch
        return torch.cuda.get_device_name(0)
    else:
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000')
            gpu_name = winreg.QueryValueEx(key, 'DriverDesc')[0].strip()
            return gpu_name
        except:
            return 'Unknown GPU'


# --- GPU Acceleration via Taichi ---
try:
    import taichi as ti
    ti.init(arch=ti.gpu, log_level=ti.ERROR)
    _has_taichi = True
except ImportError:
    _has_taichi = False

if _has_taichi:
    @ti.kernel
    def _calculate_phases_taichi_kernel(
        cx: ti.types.ndarray(dtype=ti.f64, ndim=1),
        cy: ti.types.ndarray(dtype=ti.f64, ndim=1),
        cz: ti.types.ndarray(dtype=ti.f64, ndim=1),
        tx: ti.types.ndarray(dtype=ti.f64, ndim=1),
        ty: ti.types.ndarray(dtype=ti.f64, ndim=1),
        tz: ti.types.ndarray(dtype=ti.f64, ndim=1),
        amp: ti.types.ndarray(dtype=ti.f64, ndim=1),
        out_real: ti.types.ndarray(dtype=ti.f64, ndim=1),
        out_imag: ti.types.ndarray(dtype=ti.f64, ndim=1),
        algorithm: ti.i32,
        k: ti.f64
    ):
        num_tx = cx.shape[0]
        num_pts = tx.shape[0]
        
        for i in range(num_tx):
            real_sum = 0.0
            imag_sum = 0.0
            for p in range(num_pts):
                dx = cx[i] - tx[p]
                dy = cy[i] - ty[p]
                dz = cz[i] - tz[p]
                
                d = ti.math.sqrt(dx*dx + dy*dy + dz*dz)
                phase_focal = -d * k
                
                signature = 0.0
                if algorithm == 1: # Twin Trap
                    if dx > 0:
                        signature = 3.14159265358979323846
                elif algorithm == 2: # Vortex Trap
                    signature = ti.cast(ti.math.atan2(ti.cast(dy, ti.f32), ti.cast(dx, ti.f32)), ti.f64)
                    
                pt_phase = phase_focal + signature
                
                real_sum += amp[i] * ti.cast(ti.math.cos(ti.cast(pt_phase, ti.f32)), ti.f64)
                imag_sum += amp[i] * ti.cast(ti.math.sin(ti.cast(pt_phase, ti.f32)), ti.f64)
                
            out_real[i] = real_sum
            out_imag[i] = imag_sum

    @ti.kernel
    def _calculate_field_slice_taichi_kernel(
        pts_x: ti.types.ndarray(dtype=ti.f64, ndim=1),
        pts_y: ti.types.ndarray(dtype=ti.f64, ndim=1),
        pts_z: ti.types.ndarray(dtype=ti.f64, ndim=1),
        tx_x: ti.types.ndarray(dtype=ti.f64, ndim=1),
        tx_y: ti.types.ndarray(dtype=ti.f64, ndim=1),
        tx_z: ti.types.ndarray(dtype=ti.f64, ndim=1),
        tx_p: ti.types.ndarray(dtype=ti.f64, ndim=1),
        tx_a: ti.types.ndarray(dtype=ti.f64, ndim=1),
        out_real: ti.types.ndarray(dtype=ti.f64, ndim=1),
        out_imag: ti.types.ndarray(dtype=ti.f64, ndim=1),
        k: ti.f64
    ):
        num_pts = pts_x.shape[0]
        num_tx = tx_x.shape[0]
        
        for p in range(num_pts):
            r_sum = 0.0
            i_sum = 0.0
            for t in range(num_tx):
                dx = pts_x[p] - tx_x[t]
                dy = pts_y[p] - tx_y[t]
                dz = pts_z[p] - tx_z[t]
                dist = ti.math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist < 1e-3:
                    dist = 1e-3
                
                amp = tx_a[t] / dist
                phase = k * dist + tx_p[t]
                
                r_sum += amp * ti.cast(ti.math.cos(ti.cast(phase, ti.f32)), ti.f64)
                i_sum += amp * ti.cast(ti.math.sin(ti.cast(phase, ti.f32)), ti.f64)
            out_real[p] = r_sum
            out_imag[p] = i_sum

def calculate_phases_taichi(cx, cy, cz, tx, ty, tz, amplitudes, algorithm_str, k):
    if not _has_taichi:
        return None, None
    import numpy as np
    
    algo_int = 0
    if "Twin Trap" in algorithm_str:
        algo_int = 1
    elif "Vortex Trap" in algorithm_str:
        algo_int = 2
        
    out_real = np.zeros(len(cx), dtype=np.float64)
    out_imag = np.zeros(len(cx), dtype=np.float64)
    
    _calculate_phases_taichi_kernel(
        np.ascontiguousarray(cx, dtype=np.float64),
        np.ascontiguousarray(cy, dtype=np.float64),
        np.ascontiguousarray(cz, dtype=np.float64),
        np.ascontiguousarray(tx, dtype=np.float64),
        np.ascontiguousarray(ty, dtype=np.float64),
        np.ascontiguousarray(tz, dtype=np.float64),
        np.ascontiguousarray(amplitudes, dtype=np.float64),
        out_real,
        out_imag,
        algo_int,
        k
    )
    
    total_phases = np.arctan2(out_imag, out_real) % (2.0 * np.pi)
    total_phases[total_phases < 0] += 2.0 * np.pi
    
    phase_disc = np.round((total_phases / (2.0 * np.pi)) * 32.0).astype(np.int32)
    phase_disc = np.clip(phase_disc, 0, 31)
    
    packet = bytearray([254]) + bytearray(phase_disc.astype(np.uint8)) + bytearray([253])
    return total_phases, bytes(packet)

def calculate_field_slice_taichi(pts_x, pts_y, pts_z, tx_x, tx_y, tx_z, tx_phases, tx_amplitudes, k):
    if not _has_taichi:
        return None
    import numpy as np
    out_real = np.zeros(len(pts_x), dtype=np.float64)
    out_imag = np.zeros(len(pts_x), dtype=np.float64)
    
    _calculate_field_slice_taichi_kernel(
        np.ascontiguousarray(pts_x, dtype=np.float64),
        np.ascontiguousarray(pts_y, dtype=np.float64),
        np.ascontiguousarray(pts_z, dtype=np.float64),
        np.ascontiguousarray(tx_x, dtype=np.float64),
        np.ascontiguousarray(tx_y, dtype=np.float64),
        np.ascontiguousarray(tx_z, dtype=np.float64),
        np.ascontiguousarray(tx_phases, dtype=np.float64),
        np.ascontiguousarray(tx_amplitudes, dtype=np.float64),
        out_real,
        out_imag,
        k
    )
    return out_real, out_imag
