"""Hazus capacity spectrum method (Hazus 6.1 Earthquake Model Technical Manual, Section 5.6).

Given a ShakeMap's 5%-damped spectral accelerations at 0.3 s (SAS) and 1.0 s (SA1) and the
earthquake magnitude, find a building's performance point: the peak spectral displacement D
and acceleration A where its capacity (pushover) curve meets the demand spectrum reduced for
the building's effective damping. Damage-state probabilities then follow from the Hazus
fragility curves on D (structural, drift-sensitive nonstructural) and A (acceleration-
sensitive nonstructural).

Equations implemented (manual numbering):
  4-2   T = 0.32 * sqrt(SD / SA)                       effective period, SD in inches, SA in g
  4-4   T_VD = 10 ** ((M - 5) / 2)                     velocity/displacement corner period
  5-7   R_A = 2.12 / (3.21 - 0.68 ln B_eff)            short-period damping reduction, B in %
  5-8   R_V = 1.65 / (2.31 - 0.41 ln B_eff)            long-period damping reduction
  5-10  B_eff = B_E + kappa * Area / (2 pi D A)        effective damping (here x100, in %)
  5-11..5-13  damped demand spectrum: SAS/R_A, SA1/(T R_V), SA1 T_VD/(T^2 R_V)
  5-14  T_AVB = T_AV * R_A / R_V,  T_AV = SA1 / SAS
Capacity curve (Section 5.4.1): linear to the yield point (Dy, Ay); then an elliptical
transition, tangent to the elastic line at yield and horizontal at the ultimate point
(Du, Au); plastic beyond Du. Hysteresis-loop area for a symmetric push-pull to +-D with
elastic unloading: Area = 4 * (integral_0^D C(x) dx - A^2 / (2 K)), K = Ay / Dy.
"""
import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

# Elastic damping B_E (% of critical), Hazus AEBM Manual Table 5.1 by material:
# wood 10-15% (15% for nailed wood), concrete and precast 7%, most steel 5%.
ELASTIC_DAMPING = {"W1": 15.0, "W2": 15.0, "PC1": 7.0, "C2L": 7.0, "C2M": 7.0, "C2H": 7.0,
                   "S1L": 5.0, "S1M": 5.0, "S1H": 5.0}
D_GRID = np.geomspace(1e-3, 300.0, 1500)  # spectral displacement grid, inches


def duration_class(magnitude: float) -> str:
    """Hazus Section 5.6.1.1: M <= 5.5 short, M >= 7.5 long, otherwise moderate."""
    return "short" if magnitude <= 5.5 else "long" if magnitude >= 7.5 else "moderate"


class CapacityCurve:
    def __init__(self, dy, ay, du, au):
        self.dy, self.ay, self.du, self.au = dy, ay, du, au
        self.k = ay / dy
        delta = du - dy
        if self.k * delta <= 2 * (au - ay):
            raise ValueError("elliptical transition needs k > 2 (Au - Ay) / (Du - Dy)")

        def f(u):  # u = (Du - Dy) / a, the ellipse's normalised half-width at yield
            s = np.sqrt(1 - u * u)
            return (au - ay) * u * u / (delta * (1 - s) * s) - self.k

        u = brentq(f, 1e-6, 1 - 1e-9)
        s = np.sqrt(1 - u * u)
        self.a = delta / u                       # horizontal semi-axis
        self.b = (au - ay) / (1 - s)             # vertical semi-axis
        self.a0 = au - self.b                    # centre (Du, a0)

    def accel(self, d: np.ndarray) -> np.ndarray:
        d = np.asarray(d, float)
        x = np.clip((d - self.du) / self.a, -1, 0)
        ellipse = self.a0 + self.b * np.sqrt(1 - x * x)
        return np.where(d <= self.dy, self.k * d, np.where(d >= self.du, self.au, ellipse))


def reduction_factors(b_eff_pct):
    lnb = np.log(b_eff_pct)
    return 2.12 / (3.21 - 0.68 * lnb), 1.65 / (2.31 - 0.41 * lnb)


def performance_point(curve: CapacityCurve, b_elastic: float, kappa: float,
                      sas: np.ndarray, sa1: np.ndarray, magnitude: float):
    """Peak (D, A) for arrays of spectra; D = D_GRID max when demand exceeds capacity throughout."""
    d = D_GRID
    a = curve.accel(d)
    # Hysteretic damping from the loop area of a symmetric push-pull to +-d.
    energy = np.concatenate([[0], np.cumsum(0.5 * (a[1:] + a[:-1]) * np.diff(d))]) + 0.5 * a[0] * d[0]
    area = np.maximum(4 * (energy - a * a / (2 * curve.k)), 0)
    b_eff = b_elastic + 100 * kappa * area / (2 * np.pi * d * a)
    ra, rv = reduction_factors(b_eff)
    t = 0.32 * np.sqrt(d / a)
    t_vd = 10 ** ((magnitude - 5) / 2)

    sas, sa1 = np.atleast_1d(sas)[:, None], np.atleast_1d(sa1)[:, None]
    t_avb = (sa1 / sas) * ra / rv
    demand = np.where(t <= t_avb, sas / ra,
                      np.where(t <= t_vd, sa1 / (t * rv), sa1 * t_vd / (t * t * rv)))
    gap = a - demand                                   # capacity minus demand along the curve
    crossed = gap >= 0
    first = np.where(crossed.any(axis=1), crossed.argmax(axis=1), len(d) - 1)
    i0 = np.maximum(first - 1, 0)
    g0, g1 = gap[np.arange(len(first)), i0], gap[np.arange(len(first)), first]
    w = np.where((first > 0) & (g1 != g0), -g0 / (g1 - g0), 0.0)
    d_pp = np.where(crossed.any(axis=1), d[i0] + w * (d[first] - d[i0]), d[-1])
    return d_pp, curve.accel(d_pp)


def state_probabilities(x: np.ndarray, medians, betas) -> np.ndarray:
    """P(DS = 0..4) given demand x, for lognormal fragilities on the 4 damage states."""
    p_ge = norm.cdf(np.log(np.asarray(x)[:, None] / np.asarray(medians)[None, :]) / np.asarray(betas)[None, :])
    p_ge = np.minimum.accumulate(p_ge, axis=1)
    p_ge = np.hstack([np.ones((len(x), 1)), p_ge, np.zeros((len(x), 1))])
    return p_ge[:, :-1] - p_ge[:, 1:]
