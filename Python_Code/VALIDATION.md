# Verification record

Checked on September 28, 2026, using Python 3.12.14.

**Numerical verification is not experimental validation. The default model does not reproduce Figure 3's published temperatures.**

## Independent physics checks

`python -m unittest -v test_physics.py` passed all eight tests:

1. Zero-power equilibrium in both geometries.
2. Correct conversion from W/cm² to W/m² and exact integrated source power.
3. Uniform-heating analytical one-dimensional solution in both geometries (maximum discrepancy below 0.002 K on the test mesh).
4. Analytical Robin-boundary solution with warmer ambient and zero internal source (error below 10⁻⁸ K).
5. Local equation residual and global energy conservation for nonlinear conduction.
6. Lower temperature after thinning and higher temperature when k(T) decreases with heating.
7. Correct implementation of the Table I conductivity laws.
8. Invalid physical inputs raise errors.

## Default model diagnostics

| Quantity | 630 μm substrate | 50 μm substrate |
|---|---:|---:|
| Peak (°C) | 1273.869253 | 92.812446 |
| Rise above sink (K) | 1247.019253 | 65.962446 |
| Generated heat (W) | 11.780972451 | 11.780972451 |
| Heat to sink (W) | 11.770977237 | 11.780461851 |
| Heat to ambient (W) | 0.009995214 | 0.000510597 |
| Relative energy imbalance | 2.978e-14 | 2.853e-10 |
| Relative nonlinear residual | 5.728e-10 | 2.097e-08 |
| Last iteration update (K) | 4.765e-07 | 5.739e-07 |
| Iterations | 37 | 21 |

The default uses the temperature-dependent laws, 1500 W/cm², a 500 μm contact radius, a 1000 μm outer radius, and an axisymmetric effective radial conductivity. Both cases have 10,800 cells. Numerical peaks are cell-centre values, not calibrated paper values.

## Mesh refinement

| Substrate | Mesh | Cells | Peak (°C) | Change from preceding mesh (K) |
|---|---|---:|---:|---:|
| 630 μm | Quick | 2,944 | 1273.845383 | — |
| 630 μm | Standard | 10,800 | 1273.869253 | 0.023871 |
| 630 μm | Fine | 31,200 | 1273.870890 | 0.001636 |
| 50 μm | Quick | 2,944 | 92.813964 | — |
| 50 μm | Standard | 10,800 | 92.812446 | -0.001518 |
| 50 μm | Fine | 31,200 | 92.811934 | -0.000513 |

The Standard-to-Fine peak change is below 0.002 K in both cases. This is a mesh sensitivity check at the default settings, not a formal uncertainty bound or a claim of three-decimal physical accuracy. Re-run the in-app mesh check after substantial changes in geometry or material properties.

## Interface and export checks

- Streamlit AppTest completed the default app, a power change to 500 W/cm², a display change, download preparation, and a parameter study without app exceptions.
- At 500 W/cm², the displayed model peaks dropped to approximately 199.9 °C and 47.0 °C.
- Chromium opened the self-contained HTML with network access disabled. Hovering a map updated the point inspector and showed coordinates, °C/K, conductivity, and heat generation.
- The offline common-depth and individually zoomed-depth buttons changed the thin-panel range between 640 μm and 60 μm.
- Scientific color scales are supplied as RGB values to avoid Streamlit substituting a theme placeholder for Inferno's near-black endpoint.
- The live Streamlit page rendered; the shared-color control and the 3D/profile tab were exercised in Chromium.
- Zero-power HTML generation handles the undefined cooling percentage with an em dash.
- PNG/SVG static output and browser layouts were visually inspected.
- The report is about 7.5 MB because Plotly JavaScript and numerical data are embedded. No network connection is required to view it.

## Practical limits

The original TCAD deck and raw published field were unavailable, so agreement with the authors' full simulation has not been verified. High-temperature nonlinear outputs extrapolate the paper's formulas and should not be treated as validated device operating temperatures. The code was executed in Linux with the dependency versions in requirements.txt. Windows installation instructions are provided, but this environment did not run Windows itself.
