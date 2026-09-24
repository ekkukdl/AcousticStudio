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
