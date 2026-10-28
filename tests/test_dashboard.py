"""Validate decoding, payload rejection and bounded dashboard buffering."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('dashboard', Path(__file__).resolve().parents[1] / 'src/dashboard_server.py')
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    def payload(self):
        return dict(Temperature=37.2, PH=7.01, RpmSetpoint=150, HeaterOn=False, HighTempAlarm=False)

    def test_reject_missing_and_invalid_values(self):
        for change in ({'PH': None}, {'Temperature': float('nan')}, {'HeaterOn': 'false'}, {'HighTempAlarm': 2}, {'RpmSetpoint': True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                dashboard.normalize('Bioreactor1', {**self.payload(), **change})
        with self.assertRaises(ValueError):
            dashboard.normalize('Bioreactor1', {})

    def test_bounded_and_independent_buffers(self):
        state = dashboard.State('mqtt')
        for _ in range(605):
            state.add('Bioreactor1', self.payload())
        state.error('Bioreactor1', 'Offline')
        snap = state.snapshot()
        self.assertEqual(len(snap['assets']['Bioreactor1']), 600)
        self.assertEqual(snap['assets']['Bioreactor2'], [])
        self.assertEqual(snap['messages'], 605)
        self.assertEqual(snap['errors']['Bioreactor1'], 'Offline')
        state.add('Bioreactor1', self.payload())
        self.assertNotIn('Bioreactor1', state.snapshot()['errors'])

    def test_register_scaling_and_flags(self):
        client = Mock()
        for name, attr, values in [('read_input_registers', 'registers', [372, 701]), ('read_holding_registers', 'registers', [150]), ('read_discrete_inputs', 'bits', [False]), ('read_coils', 'bits', [False])]:
            response = getattr(client, name).return_value
            response.isError.return_value = False
            setattr(response, attr, values)
        self.assertEqual(dashboard.read_device(client, 'Bioreactor1', 1), self.payload())
        client.read_input_registers.return_value.isError.return_value = True
        with self.assertRaises(RuntimeError):
            dashboard.read_device(client, 'Bioreactor1', 1)

    def test_mqtt_rejects_retained_and_bad_messages(self):
        from unittest.mock import patch
        state = dashboard.State('mqtt')
        with patch('paho.mqtt.client.Client') as factory:
            client = dashboard.mqtt_start(state)
            msg = Mock(topic='PharmaCo/Dublin/Upstream/Line1/Bioreactor1', retain=True,
                       payload=dashboard.json.dumps(self.payload()).encode())
            client.on_message(client, None, msg)
            self.assertEqual(state.messages, 0)
            msg.retain = False
            client.on_message(client, None, msg)
            self.assertEqual(state.messages, 1)
            msg.payload = b'{"Temperature": 370}'
            client.on_message(client, None, msg)
            self.assertEqual(state.messages, 1)
            self.assertIn('Bioreactor1', state.errors)


if __name__ == '__main__':
    unittest.main()
