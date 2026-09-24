---
name: python-performance-optimization
description: Python code optimization techniques, focusing on profiling, async/multiprocessing, VTK/PyVista rendering optimization, memory management, and C++ offloading.
---

# Python Performance Optimization Skill

This skill provides advanced workflows for maximizing Python performance, especially in heavy compute and 3D rendering (VTK/PyVista) environments.

## Optimization Strategies

### 1. Vectorization and NumPy
- Never use or loops in Python for numerical arrays. Always use NumPy vectorized operations (e.g., 
p.sum(..., axis)) or broadcasting.
- For massive arrays (e.g. 1M+ points), avoid intermediate array allocations to prevent memory bottleneck.

### 2. PyVista / VTK Rendering Optimization (In-place Updates)
- Calling plotter.add_mesh and plotter.remove_actor is incredibly expensive.
- **In-place Scalar Update**: If the geometry is static and only colors/values change, update grid.point_data['scalars'][:] = new_values directly. 
- Use mapper.update() or plotter.render() instead of recreating the mesh.

### 3. C++ Offloading (ctypes / pybind11)
- If NumPy is still too slow (e.g. complex math over millions of points per frame), write the bottleneck in C/C++ and use OpenMP (#pragma omp parallel for).
- Connect to Python via ctypes or pybind11 using contiguous NumPy arrays.

### 4. Zero-copy Memory Transfer
- Ensure NumPy arrays passed to C++ are C-contiguous (
p.ascontiguousarray) to avoid deep copies.

## When to use
Use this skill when the user requests "최적화" (Optimization), complains about "Lag" (버벅임), or needs high FPS rendering.
