"""Deterministic checks of scaling, thresholds, commands and device isolation."""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import bioreactor_sim as bio
import bioreactor2_sim as bio2
import chiller_sim as chiller


class RegisterTests(unittest.TestCase):
    def update_bio(self, temperature):
        bio.temperature, bio.ph = temperature, 7.0
        with patch.object(bio.random, 'uniform', return_value=0), contextlib.redirect_stdout(io.StringIO()):
            bio.update_registers()

    def test_scaling(self):
        self.update_bio(37.2)
        self.assertEqual(bio.store.getValues(4, 0, count=2), [372, 700])

    def test_thresholds_and_boundaries(self):
        for temperature, heater, alarm in [(36.4, 1, 0), (36.5, 0, 0),
                                            (38.0, 0, 0), (38.1, 0, 1)]:
            with self.subTest(temperature=temperature):
                self.update_bio(temperature)
                self.assertEqual(bio.store.getValues(1, 0, count=1), [heater])
                self.assertEqual(bio.store.getValues(2, 0, count=1), [alarm])

    def test_rpm_write_persists_and_is_logged(self):
        bio.store.setValues(3, 0, [150])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bio.update_registers()
        self.assertIn('RPM Setpoint=150', output.getvalue())
        self.assertEqual(bio.store.getValues(3, 0, count=1), [150])

    def test_device_isolation(self):
        original = bio2.store.getValues(3, 0, count=1)
        bio.store.setValues(3, 0, [151])
        self.assertEqual(bio2.store.getValues(3, 0, count=1), original)

    def test_chiller_run_stop_and_setpoint_clamp(self):
        chiller.supply_temp, chiller.return_temp = 15.0, 20.0
        chiller.store.setValues(1, 0, [1])
        chiller.store.setValues(3, 0, [0])
        with contextlib.redirect_stdout(io.StringIO()):
            chiller.update_chiller()
        self.assertAlmostEqual(chiller.supply_temp, 12.8)
        self.assertEqual(chiller.store.getValues(4, 2, count=1), [45])
        self.assertEqual(chiller.store.getValues(2, 0, count=2), [1, 0])
        chiller.store.setValues(1, 0, [0])
        with contextlib.redirect_stdout(io.StringIO()):
            chiller.update_chiller()
        self.assertEqual(chiller.store.getValues(4, 2, count=1), [0])
        self.assertEqual(chiller.store.getValues(2, 0, count=2), [0, 0])

    def test_alarm_transition_logging(self):
        # Force a transition to exercise the uploaded code's undefined-variable bug.
        chiller.previous_low_flow = True
        with contextlib.redirect_stdout(io.StringIO()):
            chiller.update_chiller()
        self.assertFalse(chiller.previous_low_flow)


if __name__ == '__main__':
    unittest.main()
