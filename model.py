"""Constant-weather solar soiling model, independent of the Streamlit UI.

Units: days, g/m², kWh/day, AED/kWh, and AED per cleaning.
The objective is long-run cycle-average cost, not finite-year total cost.
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import gammainc


@dataclass(frozen=True)
class Parameters:
    a: float = 0.0457
    r: float = 0.010
    E0: float = 60000.0
    p: float = 0.06
    K: float = 1000.0
    alpha: float = 0.017

    def validate(self):
        for name in ('a', 'r', 'E0', 'p', 'K', 'alpha'):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f'{name} must be a finite number.')
            if value < 0 or (name not in ('a', 'r') and value == 0):
                relation = 'nonnegative' if name in ('a', 'r') else 'positive'
                raise ValueError(f'{name} must be {relation}.')


@dataclass(frozen=True)
class Result:
    status: str
    continuous_days: float | None
    recommended_days: int | None
    daily_cost: float | None
    cleaning_daily: float | None
    dust_daily: float | None
    no_cleaning_daily: float
    second_derivative: float | None


def scenarios():
    """Preserve S01-S16 and their exact inputs from the uploaded script."""
    rows = {}
    removal = {(3, 20): 0.010, (3, 80): 0.005,
               (6, 20): 0.050, (6, 80): 0.020}
    for wind in (3, 6):
        for dust in ('Low', 'High'):
            for rh in (20, 80):
                for solar in ('Low', 'High'):
                    rows[f'S{len(rows)+1:02d}'] = {
                        'dust': dust, 'rh': rh, 'wind': wind, 'solar': solar,
                        'a': 0.0114 if dust == 'Low' else 0.0457,
                        'r': removal[wind, rh],
                        'E0': 25000.0 if solar == 'Low' else 60000.0,
                    }
    return rows


SCENARIOS = scenarios()


def dust(t, params, initial=0.0):
    """Dust after t days, before another cleaning, including the r=0 limit."""
    t = np.asarray(t, dtype=float)
    if params.r == 0:
        value = initial + params.a * t
    else:
        value = initial * np.exp(-params.r*t) - params.a/params.r * np.expm1(-params.r*t)
    return float(value) if value.ndim == 0 else value


def fraction_lost(t, params):
    return -np.expm1(-params.alpha*dust(t, params))


def loss_integral(T, params):
    """Integral of the dimensionless soiling loss over a clean-start cycle."""
    if T <= 0:
        return 0.0
    # Breakpoints resolve a fast initial transient even for long intervals.
    rate = params.r + params.alpha*params.a
    points = [x/rate for x in (0.1, 1, 5, 20) if rate and x/rate < T]
    return quad(lambda t: float(fraction_lost(t, params)), 0, T,
                points=points, epsabs=1e-8, epsrel=1e-9)[0]


def cost_components(T, params):
    if T <= 0:
        raise ValueError('The cleaning interval must be positive.')
    cleaning = params.K/T
    soiling = params.p*params.E0*loss_integral(T, params)/T
    return cleaning, soiling, cleaning+soiling


def no_cleaning_cost(params):
    if params.a == 0:
        return 0.0
    if params.r == 0:
        return params.p*params.E0
    return params.p*params.E0*(-math.expm1(-params.alpha*params.a/params.r))


def maximum_cleaning_benefit(params):
    """Limit of T L(T) - integral L as T→infinity.

    A finite stationary point exists precisely when K is below this limit
    (with positive a, alpha, p, E0). Stable forms avoid exp(b) overflow.
    """
    if params.a == 0:
        return 0.0
    value = params.p*params.E0
    lam = params.alpha*params.a
    if params.r == 0:
        return value/lam
    b = lam/params.r
    if b <= 50:
        def integrand(u):
            if u == 0:
                return b*math.exp(-b)
            return math.exp(-b*(1-u))*(-math.expm1(-b*u))/u
        return value/params.r*quad(integrand, 0, 1, epsabs=1e-11, epsrel=1e-10)[0]
    # Substitute z=b(1-u). Beyond z=50 the tail is negligible for b>50.
    def transformed(z):
        if z == b:
            return b*math.exp(-b)
        return math.exp(-z)*(-math.expm1(-(b-z)))/(1-z/b)
    return value/lam*quad(transformed, 0, min(b, 50), epsabs=1e-11)[0]


def stationarity(T, params):
    """T² C'(T), computed as integral(t L'(t)) - K for stability."""
    if params.a == 0 or T == 0:
        return -params.K
    value = params.p*params.E0
    lam = params.alpha*params.a
    if params.r == 0:
        return value/lam*float(gammainc(2, lam*T))-params.K
    rate = params.r+lam
    points = [x/rate for x in (0.1, 1, 5, 20) if x/rate < T]
    if 1/params.r < T:
        points.append(1/params.r)
    integral = quad(lambda t: t*value*lam*math.exp(-params.r*t-params.alpha*dust(t, params)),
                    0, T, points=sorted(set(points)), epsabs=1e-7, epsrel=1e-9)[0]
    return integral-params.K


def optimize(params, min_days=1, max_days=365):
    params.validate()
    if min_days < 1 or max_days < min_days or int(min_days) != min_days or int(max_days) != max_days:
        raise ValueError('Use whole-day bounds with 1 ≤ minimum ≤ maximum.')
    baseline = no_cleaning_cost(params)
    maximum = maximum_cleaning_benefit(params)
    if params.K >= maximum:
        return Result('no_cleaning', None, None, baseline, 0.0, baseline, baseline, None)
    # A finite optimum exists globally. Do not confuse a limited bracket with nonexistence.
    if stationarity(max_days, params) < 0:
        return Result('beyond_range', None, None, None, None, None, baseline, None)
    root = brentq(lambda T: stationarity(T, params), 0, max_days,
                  xtol=1e-8, rtol=1e-10)
    candidates = {max(int(min_days), min(int(max_days), int(math.floor(root)))),
                  max(int(min_days), min(int(max_days), int(math.ceil(root))))}
    chosen = min(candidates, key=lambda T: (cost_components(T, params)[2], T))
    cleaning, soiling, total = cost_components(chosen, params)
    second = params.p*params.E0*params.alpha*params.a/root*math.exp(
        -params.r*root-params.alpha*dust(root, params))
    status = 'below_range' if root < min_days else 'finite'
    return Result(status, root, chosen, total, cleaning, soiling, baseline, second)


def remaining_wait(params, interval, initial):
    """Threshold policy based on the selected clean-start cycle; not a fresh optimization."""
    if not math.isfinite(initial) or initial < 0:
        raise ValueError('Current dust loading must be finite and nonnegative.')
    threshold = dust(interval, params)
    if initial >= threshold:
        return 0.0, threshold
    if params.r == 0:
        return (threshold-initial)/params.a, threshold
    equilibrium = params.a/params.r
    wait = -math.log1p(-(threshold-initial)/(equilibrium-initial))/params.r
    return wait, threshold
