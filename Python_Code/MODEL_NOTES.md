# Model notes and scientific interpretation

## Scope

The task is a two-dimensional thermal simulation inspired by Figure 3 of the supplied paper. The implementation solves the steady thermal equation independently in Python. It does not digitize the plotted colors or use the paper's peak temperatures as prescribed values.

The original paper uses coupled electrical and lattice-heating models in Silvaco TCAD. Its input deck, mesh, local electrical current and field distribution, source normalization details, and fully specified recurrent boundary implementation were not supplied. An exact numerical reproduction of the paper cannot be established from the available information. Agreement with a PDE benchmark verifies this implementation; it does not validate the model against the physical diode.

## Source audit

Locations below refer to the supplied six-page PDF, **including its publisher cover sheet**. Its fourth PDF page is the third article page.

| Quantity | Paper location | Treatment here |
|---|---|---|
| 630 μm / 50 μm substrates | PDF p. 3, Figure 1; p. 4, Figure 3 | Substrate thickness, plus separate 10 μm drift layer |
| 10 μm drift layer | PDF p. 2, Experimental; p. 3, Figure 1 | Explicit mesh segment |
| 1 mm contact diameter; 500 μm half-width in drawing | PDF p. 4, Figure 3 and discussion | 500 μm source radius or planar half-width |
| 1500 W/cm² | PDF p. 4, Figure 3 discussion | Integrated areal heating under the contact |
| Conductivity laws | PDF p. 4, Table I | Implemented with absolute T in K |
| Top convection, h = 10 W/(m² K) | PDF p. 4, Table I and Eq. (2) discussion | Robin boundary on the entire top surface |
| Bottom and ambient at 300 K | PDF p. 4, boundary paragraph | Default Dirichlet sink and ambient |
| Recurrent side boundaries | PDF p. 4, boundary paragraph | Replaced by explicit zero-flux symmetry/closed-cell boundaries |
| Reported peaks: 155 °C, 55 °C | PDF p. 4, Figure 3 and discussion | Reference values only |
| Outer domain radius: 1000 μm | Not specified numerically | Adjustable assumption, suggested by the drawing's relative widths; not a measured dimension |
| Uniform drift-layer source | Not provided by the paper | Explicit replacement for unknown spatial Joule heating |
| Effective radial conductivity | Not specified by the paper | Geometric mean of in-plane values; adjustable approximation |

The figure gives substrate thickness while its graphical arrow may be read as total depth. This implementation uses 640 μm and 60 μm total semiconductor thickness, respectively, and labels that choice clearly.

## Equation and coordinates

Depth z increases downward from the semiconductor's top. For the default circular approximation, radius r extends from 0 to R = 1000 μm, and z extends from 0 to L = d + t_sub.

The steady axisymmetric equation is

\[
\frac{1}{r}\frac{\partial}{\partial r}\left(r k_r(T)\frac{\partial T}{\partial r}\right)
+\frac{\partial}{\partial z}\left(k_z(T)\frac{\partial T}{\partial z}\right)+Q(r,z)=0.
\]

For the planar alternative, replace the radial term with

\[
\frac{\partial}{\partial x}\left(k_x(T)\frac{\partial T}{\partial x}\right).
\]

This is the steady limit of Eq. (1). Heat capacity and density are unnecessary; the model does not simulate transient heating or solve current–voltage behavior.

## Thermal conductivity

Table I provides, in W/(m K), with **T in kelvin**:

\[
k_{001}(T)=18765T^{-1.26},\quad
k_{100}(T)=11078T^{-1.21},\quad
k_{010}(T)=659992T^{-1.77}.
\]

The through-thickness value is k_z = k_001 for the stated (001) substrate. By default, k_r = √(k_100 k_010). This geometric mean is an effective-medium modeling choice. Unequal lateral conductivities break exact rotational symmetry, so a 2D r–z model cannot fully capture the in-plane anisotropy of a circular diode. A full 3D anisotropic solution or more detailed dimensional reduction would be needed to remove this assumption. The planar option permits separate [100] or [010] cross-sections; it too is a reduced model with no heat flow in the omitted direction.

The code treats these directions as principal diagonal directions; it does not reconstruct a full monoclinic conductivity tensor or off-diagonal terms. Drift layer and substrate use the same thermal laws; doping-dependent thermal changes are not specified.

`frozen` mode evaluates the directional laws at 300 K throughout. `constant` mode uses the chosen isotropic k in both directions. Temperatures supplied to the power laws are never in Celsius.

## Heat generation and units

Let a = 500 μm and d = 10 μm. Heating is uniform beneath the contact and confined to the drift layer:

\[
Q(r,z)=\begin{cases}
q''/d, & 0\le r<a,\;0\le z<d,\\
0,&\text{elsewhere.}
\end{cases}
\]

\[
1\ \mathrm{W/cm^2}=10^4\ \mathrm{W/m^2}.
\]

At the default 1500 W/cm², q″ = 1.5 × 10⁷ W/m² and Q = 1.5 × 10¹² W/m³. In the circular model:

\[
P=q''\pi a^2=11.78097245\ \mathrm{W}.
\]

The planar model solves only a symmetric half-section and reports heat per metre of out-of-plane depth: P′_half = q″a = 7500 W/m. These values are not interchangeable. No arbitrary out-of-plane length is used to convert the strip's result into circular-diode power.

## Boundary conditions

- Bottom face: T(r,L) = T_sink = 300 K by default.
- Top face: outward conductive heat flux equals h(T_surface − T_ambient), with h = 10 W/(m² K) and T_ambient = 300 K.
- Centre: symmetry, ∂T/∂r = 0 (or ∂T/∂x = 0).
- Outer edge: no lateral heat flux. In a symmetric planar periodic array this can represent a midpoint between identical heated strips; for r–z it is an assumed closed thermal unit cell, not a general periodic lattice.

Convection covers the collapsed contact region as well as the exposed semiconductor. Radiation, interface resistance, and explicit packaging are omitted. The 100 nm contacts drawn in Figure 1 are collapsed into thermal boundaries; their lateral spreading is not resolved. A 100 nm gold layer with k = 315 W/(m K) has through-plane areal resistance 3.17 × 10⁻¹⁰ m² K/W, but omitting the real contact and bond interfaces can still matter.

The fabrication text gives micrometre metal thicknesses whereas Figure 1 labels 100 nm contacts. The schematic and experimental description use brass, while Table I lists copper. This model follows the explicitly stated 300 K wafer-bottom boundary. It does not add a 5 mm brass/copper layer or invent missing bond properties.

## Finite-volume discretization

Unknowns are temperatures at cell centres. Mesh faces align exactly with the contact edge and the drift/substrate interface. The substrate mesh is graded toward the active region; the drift mesh is uniform.

For two adjacent cells P and N, the face conductance is

\[
G_f=\frac{A_f}{\delta_P/k_P+\delta_N/k_N}.
\]

Thus face conductivity is evaluated through series thermal resistances, accounting for unequal cell sizes. Every internal face contributes equal and opposite heat flow. The algebraic cell equation is

\[
\sum_N G_{PN}(T_P-T_N)+\sum_b G_b(T_P-T_b)=Q_PV_P.
\]

Axisymmetric volumes and face areas are exact annular geometrical measures, with V = π(r_e²−r_w²)Δz. Radial face area is 2πr_fΔz. The axis face has zero area, avoiding any division by zero at r = 0. Planar quantities are per unit depth.

The bottom boundary includes its half-cell conduction resistance. The top boundary includes the half-cell conduction resistance in series with 1/h. T = 300 K is imposed at the actual bottom face, not at the last interior cell centre.

SciPy's sparse direct solver handles each linear system. For k(T), relaxed Picard iteration updates conductivity and temperature. The default relaxation is 0.65. Convergence requires a maximum update below 10⁻⁶ K and a relative L¹ equation residual below 10⁻⁷. A separate global heat balance is reported. The numerical 10000 K guard stops divergent/extreme iterations; it is not a material melting threshold or a physical stability criterion.

## Why the computed peaks differ

Default Standard-grid results are approximately **1273.87 °C and 92.81 °C**, versus the paper's **155 °C and 55 °C**. This gap is substantial. At fixed 300 K conductivity, the model also differs (roughly 408 °C and 85 °C). The default high-temperature field is an extrapolation of the listed laws in an assumed thermal-only model, not a validated operating-temperature prediction.

The small numerical residual and mesh change establish that the discrete model was solved consistently. They do **not** establish that its unknown TCAD source and heat paths match the article. A useful simple scale is the one-dimensional 50 μm estimate:

\[
\Delta T\approx\frac{q''(t_\mathrm{sub}+d/2)}{k_{001}(300\ \mathrm K)},
\]

which gives about 58 K with the stated power and this source model, already above the reported 28 K rise. Lateral spreading, heat-source distribution, boundary conditions, and conductivity treatment can alter that estimate. This comparison does not prove an error in the paper; it identifies information needed for a quantitative reproduction.

For an exact TCAD comparison, obtain the authors' simulation deck or the full device domain and boundary definitions, spatial heating/current solution, source-area normalization, tensor handling, contact/heat-sink implementation, and exported temperature field.

## Visualization and precision

- Heatmap colors represent unsmoothed computed control-volume values; nonuniform cell widths are preserved.
- Hover readouts display three decimal places for inspection. Those decimals are numerical display precision, not experimental accuracy.
- Contour lines interpolate between cell centres and do not add numerical resolution.
- Both default panels share a temperature scale. Independent color scales are explicitly selectable for local-detail inspection.
- Panels zoom their depth ranges independently by default. The common-depth and true-aspect options support geometry comparisons.
- The coordinate inspector returns the nearest computed cell and its actual position. On the bottom boundary it returns the prescribed temperature exactly.
- Percent cooling uses temperature rise above the sink: 100[1 − ΔT_B/ΔT_A], not a ratio of Celsius temperatures. It is undefined at zero rise.

## Reference

Chiang, C.-C., Li, J.-S., Wan, H.-H., Ren, F., & Pearton, S. J. (2024). *Effect of Substrate Thinning on Temperature Rise in Ga₂O₃ Rectifiers.* ECS Journal of Solid State Science and Technology, 13, 115001. DOI: [10.1149/2162-8777/ad89fa](https://doi.org/10.1149/2162-8777/ad89fa).
