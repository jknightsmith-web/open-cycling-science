"""Unit tests for numerical reference examples. Does not validate physiology."""
import unittest
try:
    from .metric_oracle import Interval, aggregate, mmp, cp_two_parameter_fit
except ImportError:
    from metric_oracle import Interval, aggregate, mmp, cp_two_parameter_fit


class ReferenceTests(unittest.TestCase):
    def test_200_watts_10_seconds(self):
        ints = [Interval(i, i+1, 200) for i in range(10)]
        r = aggregate(ints)
        self.assertEqual(r['mean_power_w'], 200)
        self.assertEqual(r['mechanical_work_kj'], 2)
        self.assertEqual(mmp(ints, 5), 200)

    def test_100_then_300_watts(self):
        ints = [Interval(0, 5, 100), Interval(5, 10, 300)]
        r = aggregate(ints)
        self.assertEqual(r['mean_power_w'], 200)
        self.assertEqual(r['mechanical_work_kj'], 2)
        self.assertEqual(mmp(ints, 5), 300)

    def test_zero_is_valid(self):
        ints = [Interval(0, 5, 0), Interval(5, 10, 200)]
        self.assertEqual(aggregate(ints)['mean_power_w'], 100)
        self.assertEqual(aggregate(ints)['mechanical_work_kj'], 1)

    def test_missing_power_excluded(self):
        ints = [Interval(0, 4, 200), Interval(4, 7, None), Interval(7, 10, 200)]
        r = aggregate(ints)
        self.assertAlmostEqual(r['coverage'], 0.7)
        self.assertIsNone(r['mean_power_w'])
        # D1: 7 s at 200 W observed, reported as a lower bound
        self.assertAlmostEqual(r['mechanical_work_kj'], 1.4)
        self.assertEqual(r['work_state'], 'lower_bound')
        self.assertIsNone(mmp(ints, 5))
        self.assertEqual(mmp(ints, 3), 200)

    def test_timer_pause_excluded(self):
        ints = [Interval(0, 5, 200), Interval(5, 10, 0, False), Interval(10, 15, 200)]
        r = aggregate(ints)
        self.assertEqual(r['eligible_s'], 10)
        self.assertEqual(r['mean_power_w'], 200)
        self.assertEqual(r['mechanical_work_kj'], 2)
        self.assertIsNone(mmp(ints, 6))

    def test_cp_synthetic(self):
        cp, wp = cp_two_parameter_fit([(180,350), (360,300), (720,275)])
        self.assertAlmostEqual(cp, 250, places=8)
        self.assertAlmostEqual(wp, 18000, places=6)

    def test_cp_rejects_underdetermined(self):
        with self.assertRaises(ValueError):
            cp_two_parameter_fit([(180,350), (360,300)])

    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):
            aggregate([Interval(0,3,200), Interval(2,6,200)])


if __name__ == '__main__':
    unittest.main()
