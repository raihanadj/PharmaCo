"""Read-only dashboard bridge. No Modbus writes or simulator commands are exposed."""
import argparse
from collections import deque
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

ASSETS = {'Bioreactor1': (5020, 1), 'Bioreactor2': (5022, 3), 'Chiller1': (5020, 2)}
FIELDS = {
    'Bioreactor1': {'Temperature': float, 'PH': float, 'RpmSetpoint': float, 'HeaterOn': bool, 'HighTempAlarm': bool},
    'Chiller1': {'SupplyTemp': float, 'ReturnTemp': float, 'Flow': float, 'SupplySetpoint': float, 'Running': bool, 'LowFlowAlarm': bool},
}
FIELDS['Bioreactor2'] = FIELDS['Bioreactor1']


def normalize(asset, payload):
    """Require a complete, scaled asset message; never coerce text to a boolean."""
    if not isinstance(payload, dict):
        raise ValueError('Expected an asset JSON object')
    result = {}
    for key, kind in FIELDS[asset].items():
        value = payload.get(key)
        if kind is bool:
            if type(value) is not bool and not (type(value) is int and value in (0, 1)):
                raise ValueError(f'{key} must be boolean or 0/1')
            result[key] = bool(value)
        else:
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f'{key} must be a finite number')
            result[key] = float(value)
    return result


class State:
    def __init__(self, source):
        self.source = source
        self.lock = threading.Lock()
        self.history = {a: deque(maxlen=600) for a in ASSETS}
        self.errors = {}
        self.messages = 0
        self.broker = False

    def add(self, asset, values):
        values = normalize(asset, values)
        with self.lock:
            self.history[asset].append({'time': time.time() * 1000, **values})
            self.errors.pop(asset, None)
            self.messages += 1

    def set_snowflake_rows(self, rows):
        """Use source timestamps, not polling time, for freshness."""
        import datetime
        with self.lock:
            counts = 0
            for asset in ASSETS:
                selected = []
                for row in rows:
                    if str(row.get('asset', '')).lower() != asset.lower():
                        continue
                    try:
                        raw = {k: row[k] for k in FIELDS[asset] if k in row}
                        if len(raw) != len(FIELDS[asset]):
                            continue
                        values = normalize(asset, raw)
                        t = datetime.datetime.fromisoformat(str(row['time']).replace('Z', '+00:00'))
                        if t.tzinfo is None:
                            t = t.replace(tzinfo=datetime.timezone.utc)
                        selected.append({'time': t.timestamp() * 1000, **values})
                    except (KeyError, ValueError, TypeError, OverflowError):
                        continue
                selected.sort(key=lambda r: r['time'])
                self.history[asset] = deque(selected[-600:], maxlen=600)
                if selected:
                    self.errors.pop(asset, None)
                    counts += len(selected)
                else:
                    self.errors[asset] = 'No complete Snowflake records found for this asset.'
            self.messages = counts

    def error(self, asset, message):
        with self.lock:
            self.errors[asset] = message

    def snapshot(self):
        with self.lock:
            return {'source': self.source, 'serverTime': time.time() * 1000,
                    'messages': self.messages, 'brokerConnected': self.broker,
                    'errors': dict(self.errors), 'assets': {a: list(h) for a, h in self.history.items()}}


def read_device(client, asset, unit):
    def check(response):
        if response.isError():
            raise RuntimeError('Modbus device returned an error')
        return response
    ir = check(client.read_input_registers(0, count=3 if unit == 2 else 2, device_id=unit)).registers
    hr = check(client.read_holding_registers(0, count=1, device_id=unit)).registers
    di = check(client.read_discrete_inputs(0, count=2 if unit == 2 else 1, device_id=unit)).bits
    if asset == 'Chiller1':
        return dict(SupplyTemp=ir[0]/10, ReturnTemp=ir[1]/10, Flow=ir[2], SupplySetpoint=hr[0]/10,
                    Running=bool(di[0]), LowFlowAlarm=bool(di[1]))
    co = check(client.read_coils(0, count=1, device_id=unit)).bits
    return dict(Temperature=ir[0]/10, PH=ir[1]/100, RpmSetpoint=hr[0], HeaterOn=bool(co[0]), HighTempAlarm=bool(di[0]))


def modbus_loop(state, stop):
    from pymodbus.client import ModbusTcpClient
    def poll_asset(asset, default_port, unit):
        key = {'Bioreactor1': 'BIOREACTOR1_PORT', 'Bioreactor2': 'BIOREACTOR2_PORT', 'Chiller1': 'CHILLER_PORT'}[asset]
        with ModbusTcpClient(os.getenv('SIM_CONNECT_HOST', '127.0.0.1'), port=int(os.getenv(key, default_port)), timeout=1, retries=0) as client:
            while not stop.is_set():
                try:
                    if not client.connect():
                        raise ConnectionError('Simulator unavailable')
                    state.add(asset, read_device(client, asset, unit))
                except Exception:
                    state.error(asset, 'No device response; check simulator and port settings.')
                    client.close()
                stop.wait(1)
    for asset, (port, unit) in ASSETS.items():
        threading.Thread(target=poll_asset, args=(asset, port, unit), daemon=True).start()


def mqtt_start(state):
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if os.getenv('MQTT_USERNAME'):
        client.username_pw_set(os.environ['MQTT_USERNAME'], os.getenv('MQTT_PASSWORD'))
    if os.getenv('MQTT_TLS', 'false').lower() == 'true':
        client.tls_set()
    topics = {os.getenv('MQTT_TOPIC_' + a.upper(), 'PharmaCo/Dublin/' + ('Utilities' if a == 'Chiller1' else 'Upstream') + '/Line1/' + a): a for a in ASSETS}
    def connect(c, userdata, flags, reason_code, properties):
        state.broker = not reason_code.is_failure
        if state.broker:
            for topic in topics:
                c.subscribe(topic)
    def disconnect(c, userdata, flags, reason_code, properties):
        state.broker = False
    def message(c, userdata, msg):
        asset = topics.get(msg.topic)
        # Retained messages may be old; only fresh publications prove live flow.
        if not asset or msg.retain:
            return
        try:
            if len(msg.payload) > 65536:
                raise ValueError('Message exceeds 64 KB')
            state.add(asset, json.loads(msg.payload))
        except (ValueError, TypeError, UnicodeError):
            state.error(asset, 'Invalid MQTT JSON; use the documented scaled asset schema.')
    client.on_connect, client.on_disconnect, client.on_message = connect, disconnect, message
    client.connect_async(os.getenv('MQTT_HOST', '127.0.0.1'), int(os.getenv('MQTT_PORT', '1884')), 30)
    client.loop_start()
    return client


def snowflake_loop(state, stop):
    """Bounded 10-second poll; failures keep old readings stale."""
    from snowflake_history import history
    def run():
        while not stop.is_set():
            try:
                result = history(hours=1, limit=500)
                if result.get('status') == 'ok':
                    state.set_snowflake_rows(result['rows'])
                else:
                    for asset in ASSETS:
                        state.error(asset, result.get('message', 'Snowflake unavailable'))
            except Exception:
                for asset in ASSETS:
                    state.error(asset, 'Snowflake query failed; inspect local credentials and schema.')
            stop.wait(10)
    threading.Thread(target=run, daemon=True).start()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, state, **kwargs):
        self.state = state
        super().__init__(*args, directory=str(Path(__file__).resolve().parents[1] / 'dashboard'), **kwargs)

    def do_GET(self):
        if self.path.split('?')[0] == '/api/history':
            from snowflake_history import history
            args = parse_qs(urlsplit(self.path).query)
            try:
                hours = int(args.get('hours', ['24'])[0])
                if hours not in (1, 6, 24, 168):
                    raise ValueError('Invalid hours')
                result = history(hours=hours)
            except ValueError:
                self.send_error(400, 'Invalid hours'); return
            except Exception:
                result = {'status': 'connection_error', 'rows': [], 'message': 'Snowflake query failed; check local bridge logs and credentials.'}
            body = json.dumps(result, default=str).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.split('?')[0] == '/api/snapshot':
            body = json.dumps(self.state.snapshot(), allow_nan=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.split('?')[0] in ('/', '/index.html', '/app.js', '/style.css'):
            super().do_GET()
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['modbus', 'mqtt', 'snowflake'], default='modbus')
    parser.add_argument('--with-simulator', action='store_true', help='Start existing simulators too; do not use if already running')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8050)
    args = parser.parse_args()
    state, stop = State(args.source), threading.Event()
    server = ThreadingHTTPServer((args.host, args.port), partial(Handler, state=state))
    process = None
    mqtt_client = None
    try:
        if args.with_simulator:
            process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('run_simulators.py'))])
        if args.source == 'modbus':
            modbus_loop(state, stop)
        elif args.source == 'mqtt':
            mqtt_client = mqtt_start(state)
        else:
            snowflake_loop(state, stop)
        print(f'Dashboard: http://{args.host}:{args.port} | source: {args.source}', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        if mqtt_client:
            mqtt_client.disconnect()
            mqtt_client.loop_stop()
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
