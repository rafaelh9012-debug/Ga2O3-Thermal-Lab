"""Independent physical checks. Run: python -m unittest -v test_physics.py"""
from dataclasses import replace
import unittest
import numpy as np
from thermal_model import Parameters, solve, conductivity_values


class PhysicsTests(unittest.TestCase):
    def setUp(self):
        self.p=Parameters(nx=32,nz_substrate=30,nz_drift=8,power_w_cm2=100.)

    def test_zero_source_equilibrium(self):
        for geometry in ["planar","axisymmetric"]:
            s=solve(replace(self.p,power_w_cm2=0,geometry=geometry))
            np.testing.assert_allclose(s.temperature_k,300.,atol=1e-10)

    def test_source_area_and_unit_conversion(self):
        p=self.p
        for geom in ["planar","axisymmetric"]:
            s=solve(replace(p,geometry=geom))
            r=p.contact_radius_um*1e-6
            area=np.pi*r*r if geom=="axisymmetric" else r
            expected=p.power_w_cm2*1e4*area
            self.assertAlmostEqual(float(s.source_w.sum()),expected,places=10)

    def test_uniform_heating_analytic_one_dimensional(self):
        # Independent closed form: dT/dz=0 at top, T=Tb at bottom.
        # Q=q''/d in the drift; Q=0 in the substrate. No lateral gradients.
        for geometry in ["planar","axisymmetric"]:
            p=replace(self.p,geometry=geometry,contact_radius_um=1000.,
                      conductivity="constant",constant_k=14.,h_w_m2k=0.)
            s=solve(p)
            d,L=p.drift_um*1e-6,(p.drift_um+p.substrate_um)*1e-6
            z=s.z_um*1e-6;q=p.power_w_cm2*1e4;k=p.constant_k
            exact=p.sink_k+np.where(z<d,q/k*((L-d)+(d*d-z*z)/(2*d)),q/k*(L-z))
            self.assertLess(float(np.max(np.abs(s.temperature_k-exact[:,None]))),.002)
            self.assertLess(float(np.max(np.ptp(s.temperature_k,axis=1))),1e-8)

    def test_robin_boundary_analytic_no_source(self):
        p=replace(self.p,power_w_cm2=0,ambient_k=340.,h_w_m2k=700.,
                  conductivity="constant",constant_k=14.)
        s=solve(p)
        L=(p.drift_um+p.substrate_um)*1e-6
        flux=(p.ambient_k-p.sink_k)/(1/p.h_w_m2k+L/p.constant_k)
        exact=p.sink_k+flux*(L-s.z_um*1e-6)/p.constant_k
        self.assertLess(float(np.max(np.abs(s.temperature_k-exact[:,None]))),1e-8)
        self.assertLess(s.top_heat,0.)  # The hotter ambient supplies heat.
        self.assertLess(s.balance_relative,1e-8)

    def test_nonlinear_local_and_global_conservation(self):
        for geometry in ["axisymmetric","planar"]:
            s=solve(replace(self.p,power_w_cm2=500.,geometry=geometry))
            self.assertLess(s.balance_relative,1e-7)
            self.assertLess(s.residual_relative,1e-7)
            self.assertGreaterEqual(float(s.temperature_k.min()),s.parameters.sink_k)

    def test_thinner_substrate_cools_and_kT_heats_more(self):
        thick=solve(self.p)
        thin=solve(replace(self.p,substrate_um=50.))
        frozen=solve(replace(self.p,conductivity="frozen"))
        self.assertLess(thin.peak_c,thick.peak_c)
        self.assertGreater(thick.peak_c,frozen.peak_c)

    def test_paper_conductivity_values(self):
        p=replace(self.p,lateral_axis="100")
        kx,kz=conductivity_values(np.array([300.]),p)
        self.assertAlmostEqual(kx[0],11078/300**1.21,places=12)
        self.assertAlmostEqual(kz[0],18765/300**1.26,places=12)

    def test_invalid_inputs_fail(self):
        for p in [replace(self.p,power_w_cm2=-1),replace(self.p,drift_um=0),
                  replace(self.p,contact_radius_um=2000),replace(self.p,geometry="unknown")]:
            with self.assertRaises(ValueError):
                solve(p)


if __name__=="__main__":
    unittest.main()
