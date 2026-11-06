from fractions import Fraction as Q
from pathlib import Path
from random import Random
from subprocess import run
import sys
from tempfile import TemporaryDirectory
import unittest

from roi import Case, Year, ledger, payback, read_case

ROOT = Path(__file__).resolve().parents[1]


class ROITests(unittest.TestCase):
    def scenario(self, name):
        return list(ledger(read_case(ROOT / "examples" / (name + ".json"))))

    def test_year_zero_and_one_year_discount(self):
        case = Case(Q(90), Q(10), Q(0), (Year(Q(110), Q(0), Q(0), Q(0)),))
        start, end = ledger(case)
        self.assertEqual((start.cash, start.present_value, start.cumulative_present),
                         (-90, -90, -90))
        self.assertEqual((end.cash, end.present_value, end.cumulative_cash,
                          end.cumulative_present), (110, 100, 20, 10))

    def test_terminal_resale_minus_removal_only_in_final_year(self):
        rows = self.scenario("steady")
        self.assertEqual([r.cash for r in rows], [-100000, 35000, 35000, 35000, 40000])
        self.assertEqual(rows[-1].cumulative_cash, 45000)

    def test_removal_can_outweigh_resale(self):
        case = Case(Q(30), Q(0), Q(-12), (Year(Q(30), Q(0), Q(0), Q(0)),))
        rows = list(ledger(case))
        self.assertEqual(rows[-1].cash, 18)
        self.assertEqual(rows[-1].cumulative_cash, -12)
        self.assertEqual(rows[-1].cumulative_present, -12)

    def test_exact_zero_is_payback_even_if_no_profit(self):
        case = Case(Q(100), Q(10), Q(0), (Year(Q(110), Q(0), Q(0), Q(0)),))
        rows = list(ledger(case))
        self.assertEqual(rows[-1].cumulative_present, 0)
        self.assertEqual(payback(rows, "cumulative_present"), (1, 1))

    def test_rebuild_reverses_crossing(self):
        rows = self.scenario("late-rebuild")
        self.assertEqual([r.cumulative_cash for r in rows], [-40000,-10000,15000,-5000,10000])
        self.assertEqual(payback(rows, "cumulative_cash"), (2, 4))
        self.assertEqual(payback(rows, "cumulative_present"), (2, None))

    def test_rounding_does_not_create_payback(self):
        # 1 unit due after two years is slightly short of the present outlay.
        case = Case(Q("0.83"), Q(10), Q(0), (Year(Q(0), Q(0), Q(0), Q(0)),
                    Year(Q(1), Q(0), Q(0), Q(0))))
        rows = list(ledger(case))
        self.assertTrue(-Q("0.005") < rows[-1].cumulative_present < 0)
        self.assertEqual(payback(rows, "cumulative_present"), (None, None))

    def test_common_denominator_oracle_and_brute_suffix(self):
        rng = Random(432)
        for _ in range(500):
            initial = rng.randint(10, 500)
            percent = rng.randint(0, 30)
            nets = [rng.randint(-150, 220) for _ in range(rng.randint(1, 10))]
            terminal = rng.randint(-90, 90)
            years = tuple(Year(Q(max(v, 0)), Q(0), Q(max(-v, 0)), Q(0)) for v in nets)
            rows = list(ledger(Case(Q(initial), Q(percent), Q(terminal), years)))
            final_nets = [-initial, *nets]
            final_nets[-1] += terminal
            present = []
            growth = 100 + percent
            for k in range(len(final_nets)):
                numerator = sum(final_nets[j] * 100**j * growth**(k-j) for j in range(k+1))
                present.append(Q(numerator, growth**k))
            self.assertEqual([row.cumulative_present for row in rows], present)
            first = next((i for i, v in enumerate(present) if v >= 0), None)
            sustained = next((i for i in range(len(present)) if all(x >= 0 for x in present[i:])), None)
            self.assertEqual(payback(rows, "cumulative_present"), (first, sustained))

    def test_cli_expected_results(self):
        for name, npv, roi in (("steady","19,599.59","45.00%"),
                               ("capacity-only","-76,452.09","-71.00%"),
                               ("late-rebuild","-1,979.17","25.00%")):
            with self.subTest(name=name):
                result = run([sys.executable, "roi.py", "examples/"+name+".json"],
                             cwd=ROOT, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Net present value: " + npv, result.stdout)
                self.assertIn("Simple ROI on initial cost: " + roi, result.stdout)

    def test_rejects_bad_input_and_unknown_non_cash_keys(self):
        base = (ROOT/"examples/steady.json").read_text()
        with TemporaryDirectory() as tmp:
            bad = Path(tmp)/"bad.json"
            for data in (base.replace("100000","0"), base.replace("100000","true"),
                         base.replace("36000","-1"), base.replace("36000","0.001"),
                         base.replace("8,","101,",1), base.replace("36000",'"36000"'),
                         base.replace('"initial_cost":', '"capacity_hours": 100, "initial_cost":'),
                         base.replace('"initial_cost":', '"initial_cost": 99, "initial_cost":'),
                         base.replace("100000","NaN")):
                bad.write_text(data)
                with self.subTest(data=data[:100]), self.assertRaises(ValueError):
                    read_case(bad)


if __name__ == "__main__":
    unittest.main()
