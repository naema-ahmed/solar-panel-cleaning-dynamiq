"""Checks for the report-aligned implementation."""
from dataclasses import replace
import math
import unittest

import numpy as np
from scipy.integrate import solve_ivp

from model import Parameters,SCENARIOS,average_cost,dust,optimize,symbolic_cost


class ModelTests(unittest.TestCase):
    def preset(self,name):
        row=SCENARIOS[name]
        return Parameters(a=row['a'],r=row['r'],E0=row['E0'])

    def test_report_cases(self):
        roots={'S01':122.75393,'S02':66.65358,'S03':97.79546,'S04':59.22040,
               'S05':49.13327,'S06':29.68506,'S07':45.10255,'S08':28.21345,
               'S12':96.85994,'S14':78.81372,'S15':61.73903,'S16':33.41780}
        for name in SCENARIOS:
            with self.subTest(name=name):
                params=self.preset(name)
                result=optimize(params)
                if name not in roots:
                    self.assertEqual(result.status,'not_bracketed')
                    self.assertIsNone(result.daily_cost)
                    continue
                self.assertEqual(result.status,'minimum')
                self.assertAlmostEqual(result.continuous_days,roots[name],places=4)
                self.assertGreater(result.second_derivative,0)
                for T in (math.floor(result.continuous_days),math.ceil(result.continuous_days)):
                    self.assertLessEqual(result.daily_cost,average_cost(T,params)+1e-9)

    def test_search_bound_does_not_prove_nonexistence(self):
        self.assertEqual(optimize(self.preset('S01'),100).status,'not_bracketed')
        self.assertEqual(optimize(self.preset('S01'),365).status,'minimum')

    def test_whole_day_choice(self):
        result=optimize(self.preset('S06'))
        self.assertEqual(result.recommended_days,30)
        self.assertAlmostEqual(result.daily_cost,71.1268242539,places=7)

    def test_independent_ode(self):
        params=self.preset('S08');T=123.4
        sol=solve_ivp(lambda t,y:[params.a-params.r*y[0]],(0,T),[0],rtol=1e-10,atol=1e-12)
        self.assertAlmostEqual(dust(T,params),sol.y[0,-1],places=8)

    def test_symbolic_first_derivative(self):
        params=self.preset('S04');T,c,c1,c2=symbolic_cost(params)
        h=.001;t=45
        numerical=(average_cost(t+h,params)-average_cost(t-h,params))/(2*h)
        self.assertAlmostEqual(float(c1.subs(T,t).evalf()),numerical,places=7)

    def test_validity_domain(self):
        for params in [Parameters(a=0),Parameters(r=0),Parameters(K=0)]:
            with self.assertRaises(ValueError):optimize(params)
        with self.assertRaises(ValueError):optimize(Parameters(),1)


if __name__=='__main__':
    unittest.main()
