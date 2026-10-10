"""Conservative 2D steady heat conduction inspired by Chiang et al. (2024).

SI units inside the solver. Public geometry inputs use micrometres and W/cm^2.
This is a thermal-only reconstruction, not the authors' coupled TCAD model.
"""
from dataclasses import asdict, dataclass, replace
import math
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

PAPER_DOI = "https://doi.org/10.1149/2162-8777/ad89fa"
LAWS = {"001": (18765.0, 1.26), "100": (11078.0, 1.21),
        "010": (659992.0, 1.77)}
MESHES = {"Quick": (64, 40, 6), "Standard": (120, 80, 10),
          "Fine": (200, 140, 16)}


@dataclass(frozen=True)
class Parameters:
    substrate_um: float = 630.0
    drift_um: float = 10.0
    contact_radius_um: float = 500.0
    domain_radius_um: float = 1000.0
    power_w_cm2: float = 1500.0
    ambient_k: float = 300.0
    sink_k: float = 300.0
    h_w_m2k: float = 10.0
    geometry: str = "axisymmetric"
    lateral_axis: str = "effective"
    conductivity: str = "temperature"
    constant_k: float = 14.0
    nx: int = 120
    nz_substrate: int = 80
    nz_drift: int = 10
    tolerance_k: float = 1e-6
    max_iterations: int = 250
    relaxation: float = 0.65

    def validate(self):
        positive = [self.substrate_um, self.drift_um, self.contact_radius_um,
                    self.domain_radius_um, self.ambient_k, self.sink_k,
                    self.constant_k, self.tolerance_k]
        if not all(math.isfinite(v) and v > 0 for v in positive):
            raise ValueError("Lengths, absolute temperatures, k, and tolerance must be finite and positive.")
        if self.domain_radius_um < self.contact_radius_um:
            raise ValueError("The domain must contain the entire contact.")
        if not all(math.isfinite(v) and v >= 0 for v in [self.power_w_cm2, self.h_w_m2k]):
            raise ValueError("Power and convection coefficient must be finite and nonnegative.")
        if self.geometry not in {"axisymmetric", "planar"}:
            raise ValueError("Geometry must be axisymmetric or planar.")
        if self.lateral_axis not in {"effective", "100", "010"}:
            raise ValueError("Invalid lateral crystal direction.")
        if self.conductivity not in {"temperature", "frozen", "constant"}:
            raise ValueError("Invalid conductivity model.")
        if min(self.nx, self.nz_substrate, self.nz_drift) < 2:
            raise ValueError("At least two cells are required in each mesh segment.")
        if not 0 < self.relaxation <= 1 or self.max_iterations < 1:
            raise ValueError("Invalid iteration settings.")


@dataclass
class Solution:
    parameters: Parameters
    x_edges_m: np.ndarray
    z_edges_m: np.ndarray
    temperature_k: np.ndarray
    source_w: np.ndarray
    iterations: int
    residual_relative: float
    balance_relative: float
    bottom_heat: float
    top_heat: float
    last_update_k: float

    @property
    def x_um(self):
        return 0.5 * (self.x_edges_m[:-1] + self.x_edges_m[1:]) * 1e6

    @property
    def z_um(self):
        return 0.5 * (self.z_edges_m[:-1] + self.z_edges_m[1:]) * 1e6

    @property
    def temperature_c(self):
        return self.temperature_k - 273.15

    @property
    def peak_c(self):
        return float(self.temperature_c.max())

    @property
    def power_unit(self):
        return "W" if self.parameters.geometry == "axisymmetric" else "W/m"

    def summary(self):
        j, i = np.unravel_index(np.argmax(self.temperature_k), self.temperature_k.shape)
        return {"substrate_um": self.parameters.substrate_um,
                "total_semiconductor_um": self.parameters.substrate_um + self.parameters.drift_um,
                "power_density_W_cm2": self.parameters.power_w_cm2,
                "peak_C": self.peak_c,
                "rise_above_sink_K": float(self.temperature_k.max() - self.parameters.sink_k),
                "peak_x_or_r_um": float(self.x_um[i]), "peak_depth_um": float(self.z_um[j]),
                "generated_heat": float(self.source_w.sum()), "bottom_heat": self.bottom_heat,
                "top_heat": self.top_heat, "heat_unit": self.power_unit,
                "energy_balance_relative": self.balance_relative,
                "nonlinear_residual_relative": self.residual_relative,
                "last_update_K": self.last_update_k, "iterations": self.iterations,
                "cells": int(self.temperature_k.size), "parameters": asdict(self.parameters)}


def conductivity_values(temperature_k, p):
    """Table I laws, with [001] through-thickness; effective radial k is an assumption."""
    t = np.asarray(temperature_k, dtype=float)
    if p.conductivity == "constant":
        return np.full_like(t, p.constant_k), np.full_like(t, p.constant_k)
    if p.conductivity == "frozen":
        t = np.full_like(t, 300.0)
    ks = {a: prefactor * t ** (-exponent) for a, (prefactor, exponent) in LAWS.items()}
    lateral = np.sqrt(ks["100"] * ks["010"]) if p.lateral_axis == "effective" else ks[p.lateral_axis]
    return lateral, ks["001"]


def mesh(p):
    """Contact edge and layer interface coincide exactly with control-volume faces."""
    radius, extent = p.contact_radius_um * 1e-6, p.domain_radius_um * 1e-6
    if radius < extent:
        inner = max(2, min(p.nx - 2, round(p.nx * radius / extent)))
        xe = np.r_[np.linspace(0, radius, inner + 1),
                   np.linspace(radius, extent, p.nx - inner + 1)[1:]]
    else:
        xe = np.linspace(0, extent, p.nx + 1)
    drift = p.drift_um * 1e-6
    # Quadratic grading resolves the junction while keeping thick-wafer solves fast.
    ze = np.r_[np.linspace(0, drift, p.nz_drift + 1),
               drift + p.substrate_um * 1e-6 * np.linspace(0, 1, p.nz_substrate + 1)[1:] ** 1.5]
    return xe, ze


def geometry_arrays(p, xe, ze):
    dx, dz = np.diff(xe), np.diff(ze)
    if p.geometry == "axisymmetric":
        area = np.pi * (xe[1:] ** 2 - xe[:-1] ** 2)
        side_area = 2 * np.pi * xe[1:-1][None, :] * dz[:, None]
    else:
        area = dx  # per metre of out-of-plane depth; only the symmetric half is solved
        side_area = np.broadcast_to(dz[:, None], (len(dz), len(dx) - 1))
    volume = dz[:, None] * area[None, :]
    return dx, dz, area, side_area, volume


def assemble(temperature_k, p, xe, ze, source):
    """Face resistance = left half-cell/k + right half-cell/k.

    Every internal flux is assembled once with equal and opposite contributions.
    Top Robin condition includes the half-cell conduction resistance. Bottom
    Dirichlet condition is located at the physical face, not the last cell centre.
    """
    dx, dz, area, side_area, _ = geometry_arrays(p, xe, ze)
    kx, kz = conductivity_values(temperature_k, p)
    gx = side_area / (dx[:-1][None, :] / (2 * kx[:, :-1]) +
                      dx[1:][None, :] / (2 * kx[:, 1:]))
    gz = area[None, :] / (dz[:-1, None] / (2 * kz[:-1, :]) +
                          dz[1:, None] / (2 * kz[1:, :]))
    shape = temperature_k.shape
    ids = np.arange(temperature_k.size).reshape(shape)
    a = np.r_[ids[:, :-1].ravel(), ids[:-1, :].ravel()]
    b = np.r_[ids[:, 1:].ravel(), ids[1:, :].ravel()]
    g = np.r_[gx.ravel(), gz.ravel()]
    diag = np.bincount(np.r_[a, b], weights=np.r_[g, g], minlength=temperature_k.size)
    bottom = area / (dz[-1] / (2 * kz[-1, :]))
    top = np.zeros_like(area) if p.h_w_m2k == 0 else area / (dz[0] / (2 * kz[0, :]) + 1 / p.h_w_m2k)
    diag[ids[-1]] += bottom
    diag[ids[0]] += top
    # Solve temperature rise relative to sink to avoid cancellation of large T terms.
    rhs = source.ravel().copy()
    rhs[ids[0]] += top * (p.ambient_k - p.sink_k)
    matrix = coo_matrix((np.r_[diag, -g, -g],
                         (np.r_[ids.ravel(), a, b], np.r_[ids.ravel(), b, a])),
                        shape=(temperature_k.size, temperature_k.size)).tocsr()
    return matrix, rhs, bottom, top


def solve(p=Parameters()):
    p.validate()
    xe, ze = mesh(p)
    _, dz, area, _, volume = geometry_arrays(p, xe, ze)
    xc = 0.5 * (xe[:-1] + xe[1:])
    zc = 0.5 * (ze[:-1] + ze[1:])
    active = (zc[:, None] < p.drift_um * 1e-6) & (xc[None, :] < p.contact_radius_um * 1e-6)
    # 1 W/cm^2 = 10^4 W/m^2; integrating Q over drift depth returns q''.
    source = np.where(active, p.power_w_cm2 * 1e4 / (p.drift_um * 1e-6) * volume, 0.0)
    t = np.full(source.shape, p.sink_k)
    nonlinear = p.conductivity == "temperature"
    last_update, residual = math.inf, math.inf
    for iteration in range(1, p.max_iterations + 1):
        matrix, rhs, _, _ = assemble(t, p, xe, ze, source)
        candidate = spsolve(matrix, rhs).reshape(t.shape) + p.sink_k
        if not np.all(np.isfinite(candidate)) or candidate.min() <= 0 or candidate.max() > 10000:
            raise RuntimeError("No acceptable steady solution at these settings. Reduce power, improve cooling, or inspect the conductivity model; the iteration exceeded its 10000 K numerical guard.")
        new_t = t + (p.relaxation if nonlinear else 1.0) * (candidate - t)
        last_update = float(np.max(np.abs(new_t - t)))
        t = new_t
        if not nonlinear or last_update < p.tolerance_k:
            final_matrix, final_rhs, bottom, top = assemble(t, p, xe, ze, source)
            r = final_matrix @ (t.ravel() - p.sink_k) - final_rhs
            residual = float(np.linalg.norm(r, 1) / max(np.linalg.norm(final_rhs, 1), 1e-20))
            if residual < 1e-7 or not nonlinear:
                break
    else:
        raise RuntimeError(f"Nonlinear solver did not converge in {p.max_iterations} iterations. Last update: {last_update:.3g} K. No unconverged field is displayed.")
    final_matrix, final_rhs, bottom, top = assemble(t, p, xe, ze, source)
    r = final_matrix @ (t.ravel() - p.sink_k) - final_rhs
    residual = float(np.linalg.norm(r, 1) / max(np.linalg.norm(final_rhs, 1), 1e-20))
    qb = float(np.sum(bottom * (t[-1] - p.sink_k)))
    qt = float(np.sum(top * (t[0] - p.ambient_k)))
    balance = abs(float(source.sum()) - qb - qt) / max(abs(float(source.sum())), abs(qb) + abs(qt), 1e-20)
    return Solution(p, xe, ze, t, source, iteration, residual, float(balance), qb, qt, last_update)


def mesh_comparison(p):
    rows, previous = [], None
    for name, (nx, nz, nd) in MESHES.items():
        s = solve(replace(p, nx=nx, nz_substrate=nz, nz_drift=nd))
        row = {"mesh": name, "cells": s.temperature_k.size, "peak_C": s.peak_c,
               "peak_change_K": None if previous is None else s.peak_c - previous,
               "energy_balance_relative": s.balance_relative}
        rows.append(row)
        previous = s.peak_c
    return rows
