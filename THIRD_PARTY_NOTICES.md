# Ultraino propagation, Gor'kov analysis and Kinoforms

The `ultraino_sinc` propagation in `src/acousticstudio/field_model.py` is adapted
from Ultraino's `CalcField.java` and `M.sinc`. The Gor'kov coefficients and
fourth-order first-derivative stencils in `src/acousticstudio/force_analysis.py`
are adapted from `CalcField.java`; fixed-drive axis scans follow the analysis
flow in `ForcePlotsFrame.java`. The virtual-point construction and iterative
forward projection, target constraints and conjugate backprojection in
`src/acousticstudio/hologram.py` are adapted from `Kinoforms.java`, using
phase-only drives with fixed source gains and an explicit coordinate transform.
Original source is retained at
`../simulations/Ultraino`. Its license notice follows:

MIT License

Copyright (c) 2017 asiermarzo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
