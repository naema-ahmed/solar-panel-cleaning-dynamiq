"""Report-aligned model adapted from the uploaded dynamiq_code.py.

Only the constant-scenario, fully effective cleaning calculation is implemented.
The numerical bracket is [lower, H]; H does not turn C(T) into an annual objective.
"""
from dataclasses import dataclass
from functools import lru_cache
import math

import numpy as np
import sympy as sp
from scipy.integrate import quad
from scipy.optimize import brentq


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
            if not math.isfinite(getattr(self,name)) or getattr(self,name)<=0:
                raise ValueError(f'{name} must be finite and positive for this implementation.')


@dataclass(frozen=True)
class Result:
    status: str
    continuous_days: float | None
    recommended_days: int | None
    daily_cost: float | None
    second_derivative: float | None


def scenarios():
    rows = {}
    removal = {(3,20):0.010,(3,80):0.005,(6,20):0.050,(6,80):0.020}
    for wind in (3,6):
        for dust_level in ('Low','High'):
            for rh in (20,80):
                for solar in ('Low','High'):
                    rows[f'S{len(rows)+1:02d}'] = {
                        'dust':dust_level,'rh':rh,'wind':wind,'solar':solar,
                        'a':0.0114 if dust_level=='Low' else 0.0457,
                        'r':removal[wind,rh],
                        'E0':25000.0 if solar=='Low' else 60000.0,
                    }
    return rows


SCENARIOS = scenarios()


def dust(t, params):
    """Report solution for D(0)=0, with a,r constant and r>0."""
    return (params.a/params.r)*(1-np.exp(-params.r*np.asarray(t)))


def average_cost(T, params):
    """Same numerical cost expression as cost() in the uploaded script, AED/day."""
    if T<=0:
        raise ValueError('The cleaning interval must be positive.')
    f=lambda t: 1-np.exp(-params.alpha*(params.a/params.r)*(1-np.exp(-params.r*t)))
    integral,_=quad(f,0,T)
    return params.K/T+params.p*params.E0*integral/T


@lru_cache(maxsize=128)
def symbolic_cost(params):
    """Keep the report/script's symbolic integration and differentiation."""
    t,T=sp.symbols('t T')
    f=1-sp.exp(-params.alpha*((params.a/params.r)*(1-sp.exp(-params.r*t))))
    integral=sp.integrate(f,(t,0,T))
    c=params.K/T+(params.p*params.E0/T)*integral
    c1=sp.diff(c,T)
    c2=sp.diff(c1,T)
    return T,c,c1,c2


def optimize(params, H=365, lower=1):
    """Brent root search + SOSC + whole-day floor/ceiling cost comparison.

    A missing bracket is reported only as a search-range result. It is not
    mislabelled as proof that no finite optimum exists over all positive T.
    """
    params.validate()
    if (not math.isfinite(H) or not math.isfinite(lower)
        or int(H)!=H or int(lower)!=lower or lower<1 or H<=lower):
        raise ValueError('Use whole-day bounds with 1 ≤ lower bound < upper bound.')
    T,_,c1,c2=symbolic_cost(params)
    derivative=lambda value:float(c1.subs(T,value).evalf())
    low,high=derivative(lower),derivative(H)
    if not math.isfinite(low) or not math.isfinite(high):
        raise ValueError('The derivative could not be evaluated for these inputs.')
    if low==0:
        root=float(lower)
    elif high==0:
        root=float(H)
    elif (low>0)==(high>0):
        return Result('not_bracketed',None,None,None,None)
    else:
        root=float(brentq(derivative,lower,H))
    # The SOSC belongs at the stationary point, before rounding it.
    curvature=float(c2.subs(T,root).evalf())
    if curvature<=0:
        return Result('sosc_not_positive',root,None,None,curvature)
    floor=max(int(lower),int(np.floor(root)))
    ceil=min(int(H),int(np.ceil(root)))
    cost_floor=average_cost(floor,params)
    cost_ceil=average_cost(ceil,params)
    # Preserve the original script's rule (ties choose the ceiling).
    chosen=floor if cost_floor<cost_ceil else ceil
    cost=cost_floor if cost_floor<cost_ceil else cost_ceil
    return Result('minimum',root,chosen,cost,curvature)
