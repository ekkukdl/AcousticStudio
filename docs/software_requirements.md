# Fixtureless 360° inspection software roadmap

## Goal and current boundary

The target system described in `설계문제정의보고서.hwp` is an inspection
workflow, not only an acoustic-field viewer:

`levitate / orient → verify stability → capture images → reconstruct and compare → decide pass/fail`

AcousticStudio currently covers array design, phase calculation, field display,
trajectory generation, relative trap-stiffness diagnosis, k-Wave 2D analysis,
and phase-frame transmission.  A displayed stability score is a model-relative
score, not a measured levitation success rate.

## Implemented in this update

### Board profile and transport layer

`acousticstudio.hardware` now owns the board protocol rather than allowing UI
code to construct raw packets.  The selectable profiles are:

| Profile | Frame / transport | Reference inspected |
| --- | --- | --- |
| Legacy Phase32 | `0xFE + N×phase(0..31) + 0xFD` | Existing AcousticStudio behavior |
| Ultraino SimpleFPGA 256 | `0xFE + 256×phase + 0xFD`, 230400 baud | `Ultraino/.../SimpleFPGA.java` |
| SonicSurface FPGA 256 (direct) | `0xFE + 256×phase + 0xFD`, 230400 baud | `SonicSurface/.../TestHoloConnection4.ino` |
| SonicSurface FPGA 256 (board tags) | `0xFE, 0xC0, 128 phases, 0xC1, 128 phases, 0xFD` | `SonicSurface/.../CommandSenderESP32.ino` |
| SonicSurface ESP32 CommandSender | `phases=<256 comma-separated values>,\n`, 230400 baud | `SonicSurface/.../CommandSenderESP32.ino` |

Fixed 256-channel profiles reject partial arrays. Phase values are finite
radians, wrapped before 32-step quantisation; code `32` is never emitted as a
phase because the SonicSurface firmware uses it as an off value. The selected
profile is stored in project JSON. A validated physical-frame-index to
software-channel mapping API is included for a future calibration result.

These are software framing checks only. The selected profile must match the
firmware actually flashed on the connected board. No physical board acceptance,
channel order, or levitation result has been verified here.

## Remaining implementation backlog

### P0 — required for a credible inspection demonstrator

1. **Field mapping and calibration**: control a microphone/receiver scan,
   estimate channel amplitude and phase errors, review the map, store its
   provenance, and apply it through the channel-map/calibration layer.
2. **Vision closed loop**: camera acquisition, intrinsic/extrinsic calibration,
   part pose and angle estimation, bounded controller, settle-time criterion,
   then deterministic image capture.
3. **Safety state machine**: explicit idle/armed/levitating/moving/settling/
   capturing/fault states; emergency output-off; communication timeout;
   object-loss and camera-loss handling. Never continue to capture after a
   failed state transition.
4. **Board validation**: fake-serial protocol tests plus a physical test sheet
   for boot version, channel map, 32-step convention, frame commit, maximum
   sustainable update rate, and disconnect behavior.

### P1 — inspection-system functions

1. **Part recipe**: versioned CAD/mesh, mass/material, allowed orientation,
   array geometry, calibration IDs, camera setup, angle plan and tolerances.
2. **Acquisition and traceability**: per-part ID, timestamped raw images,
   command/pose/quality log, calibration versions and repeatable export.
3. **Geometry inspection**: image registration, point cloud/mesh reconstruction,
   CAD registration, deviation map and tolerance decision.
4. **Appearance inspection**: labelled image dataset, inference interface,
   defect location/severity, human review and combined geometry/appearance
   pass-fail report.

### P2 — higher-fidelity design analysis

1. Model mass, inertia, geometry and orientation-dependent force/torque; do
   not infer six-degree-of-freedom stability from a scalar stiffness score.
2. Validate k-Wave grid/time convergence and compare against measured fields.
   The present 2D result (`p_max` and final transient sample) is not by itself a
   3D steady-state validation.
3. Add robust phase optimisation with measured channel errors and phase
   quantisation in the objective, then compare a deterministic small case among
   CPU/native/GPU implementations.

## Acceptance milestones

| Milestone | Evidence required |
| --- | --- |
| Board protocol ready | Unit tests plus physical captured frame/firmware version/channel mapping record |
| Controlled rotation | Pose error, settle time and repeatability across a defined number of cycles |
| Calibrated field | Measured versus predicted amplitude/phase map and applied correction version |
| Inspection result | Raw images, reconstruction/CAD deviation, AI result, final decision and recipe ID |
