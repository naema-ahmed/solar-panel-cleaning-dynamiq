"""Regression against independently calculated report results and model invariants."""
import math
import unittest
from dataclasses import replace

import numpy as np
from scipy.integrate import solve_ivp

from model import (Parameters, SCENARIOS, cost_components, dust, loss_integral,
                   maximum_cleaning_benefit, optimize, remaining_wait, stationarity)


class ModelTests(unittest.TestCase):
    def preset(self, name):
        row = SCENARIOS[name]
        return Parameters(a=row['a'], r=row['r'], E0=row['E0'])

    def test_all_report_cases(self):
        expected = {'S01':122.75393,'S02':66.65358,'S03':97.79546,'S04':59.22040,
                    'S05':49.13327,'S06':29.68506,'S07':45.10255,'S08':28.21345,
                    'S12':96.85994,'S14':78.81372,'S15':61.73903,'S16':33.41780}
        for name in SCENARIOS:
            with self.subTest(name=name):
                params = self.preset(name)
                result = optimize(params)
                if name in expected:
                    self.assertEqual(result.status,'finite')
                    self.assertAlmostEqual(result.continuous_days, expected[name], places=4)
                    self.assertGreater(result.second_derivative,0)
                    self.assertLess(abs(stationarity(result.continuous_days,params)),1e-4)
                    for nearby in [math.floor(result.continuous_days),math.ceil(result.continuous_days)]:
                        self.assertLessEqual(result.daily_cost,cost_components(nearby,params)[2]+1e-9)
                else:
                    self.assertEqual(result.status,'no_cleaning')
                    self.assertGreater(result.daily_cost,0)

    def test_search_range_is_not_nonexistence(self):
        result = optimize(self.preset('S01'),1,100)
        self.assertEqual(result.status,'beyond_range')
        self.assertIsNone(result.recommended_days)

    def test_minimum_allowed_interval(self):
        result = optimize(self.preset('S06'),40,365)
        self.assertEqual(result.status,'below_range')
        self.assertEqual(result.recommended_days,40)

    def test_independent_ode_integration(self):
        p=self.preset('S08'); T=123.4
        sol=solve_ivp(lambda t,y:[p.a-p.r*y[0],-math.expm1(-p.alpha*y[0])],
                      (0,T),[0,0],rtol=1e-10,atol=1e-12)
        self.assertAlmostEqual(dust(T,p),sol.y[0,-1],places=8)
        self.assertAlmostEqual(loss_integral(T,p),sol.y[1,-1],places=7)

    def test_zero_removal(self):
        p=replace(self.preset('S06'),r=0)
        result=optimize(p)
        self.assertEqual(result.status,'finite')
        self.assertAlmostEqual(dust(10,p),10*p.a)

    def test_zero_deposition(self):
        result=optimize(replace(self.preset('S06'),a=0))
        self.assertEqual(result.status,'no_cleaning')
        self.assertEqual(result.daily_cost,0)

    def test_current_dust_policy(self):
        p=self.preset('S06')
        wait, threshold=remaining_wait(p,30,0.8)
        self.assertGreater(wait,0);self.assertLess(wait,30)
        self.assertAlmostEqual(dust(wait,p,initial=.8),threshold,places=9)
        self.assertAlmostEqual(remaining_wait(p,30,0)[0],30)
        self.assertEqual(remaining_wait(p,30,threshold)[0],0)

    def test_asymptotic_existence_check(self):
        p=self.preset('S06'); M=maximum_cleaning_benefit(p)
        self.assertAlmostEqual(stationarity(20000,p)+p.K,M,places=5)
        self.assertEqual(optimize(replace(p,K=M*1.01)).status,'no_cleaning')

    def test_strong_attenuation_does_not_overflow(self):
        p=Parameters(a=1,r=.001,alpha=1,E0=60000)
        self.assertTrue(math.isfinite(maximum_cleaning_benefit(p)))
        self.assertEqual(optimize(p).status,'finite')

    def test_invalid_parameters(self):
        for params in [Parameters(a=-1),Parameters(r=-1),Parameters(p=0),Parameters(K=0)]:
            with self.assertRaises(ValueError):optimize(params)
        with self.assertRaises(ValueError):optimize(Parameters(),20,10)


if __name__=='__main__':
    unittest.main()
