# Live process dashboard

A responsive website for Bioreactor1, Bioreactor2 and Chiller1: live charts, asset switching, alarms, freshness, CSV export, pipeline explanation and project details. No external frontend dependencies. All telemetry and event history are in memory, not a persistent historian.

## Run with actual simulator data

In your checked-out dashboard branch, with Python 3.10+:

```sh
python -m pip install -r requirements-dashboard.txt
python src/dashboard_server.py --with-simulator
```

Open **http://127.0.0.1:8050**. The launcher starts the existing Modbus simulators as a child process. Ctrl+C stops the bridge and its child. If the simulator is already running, use `python src/dashboard_server.py` instead. Do not launch a second simulator on occupied ports. On Windows, `py` can replace `python`; with the README's virtual environment use `.\.venv\Scripts\python.exe`. On macOS/Linux use `.venv/bin/python`.

The default `modbus` mode reads unit 1 and 2 on 5020 and unit 3 on 5022. It divides raw temperature by 10 and raw pH by 100. It performs no writes. Configure `SIM_CONNECT_HOST`, `BIOREACTOR1_PORT`, `BIOREACTOR2_PORT` and `CHILLER_PORT` for other simulator addresses. `SIM_CONNECT_HOST` is the client destination; `SIM_HOST` remains the simulator bind address.

The bridge reconnects automatically. Starting the simulator later makes data flow without refreshing the page. Failed device reads or samples older than 5 seconds are marked stale. Last readings remain visible; missing data is never replaced with demo values.

## Use HighByte → HiveMQ

Start your simulator, HighByte publication and HiveMQ, then:

```sh
python src/dashboard_server.py --source mqtt
```

Defaults are `MQTT_HOST=127.0.0.1`, `MQTT_PORT=1884`. Optional variables: `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TLS=true` (system-trusted TLS certificates). `.env.example` is documentation, not automatically loaded. Keep credentials in the process environment, never frontend code or Git.

The bridge subscribes to these exact asset topics:

| Asset | Topic | Optional override variable |
|---|---|---|
| Bioreactor1 | `PharmaCo/Dublin/Upstream/Line1/Bioreactor1` | `MQTT_TOPIC_BIOREACTOR1` |
| Bioreactor2 | `PharmaCo/Dublin/Upstream/Line1/Bioreactor2` | `MQTT_TOPIC_BIOREACTOR2` |
| Chiller1 | `PharmaCo/Dublin/Utilities/Line1/Chiller1` | `MQTT_TOPIC_CHILLER1` |

Publish a complete JSON object with **already scaled numeric values**. Field names are case-sensitive:

```json
{"Temperature":37.2,"PH":7.01,"RpmSetpoint":100,"HeaterOn":false,"HighTempAlarm":false}
```

```json
{"SupplyTemp":7.0,"ReturnTemp":12.0,"Flow":45,"SupplySetpoint":7.0,"Running":true,"LowFlowAlarm":false}
```

Booleans may also be numeric 0/1. Nested objects, string numbers and per-tag topics require an adapter or changes to the HighByte output. Extra fields are ignored. Missing fields and non-finite numbers are rejected. Retained messages are ignored because they do not prove fresh publications. Freshness measures arrival at the bridge, not the time of acquisition in HighByte; configure HighByte to suppress publication when source quality is bad. The real HighByte export is not in this repository, so compatibility with the user's current payload is not yet verified.

## Browser demo and hosting

`dashboard/` can be served as static files. Click **Start demo** for explicitly labelled synthetic browser signals. The demo runs only while the page is open; it is not the Python process. Pause/resume, asset selection, time windows and CSV export work without a backend. Demo chiller is shown running for illustration, whereas the real simulator starts it stopped.

For actual data use the local bridge URL above. The hosted static showcase **does not connect to localhost or a laptop's Modbus ports**. To make actual data available remotely, deploy this bridge on a host that can reach your broker, serve it behind authenticated HTTPS, and serve the dashboard from that same origin. The supplied HTTP server is for local development; it has no login, TLS or production hardening. Do not expose it directly to the internet. A cloud MQTT endpoint or an outbound local relay is needed when the simulator/broker remains on a private laptop. This deployment is not configured by the showcase.

`GET /api/snapshot` returns the last 600 samples per asset, per-asset errors, source and sample counts. History resets on server restart. The frontend refreshes once per second and displays gaps longer than five seconds as separate chart segments. CSV includes source mode and UTC timestamps. Snowflake and Power BI are not connected by this change.

## Validation

```sh
python -m unittest discover -s tests -v
node --check dashboard/app.js
```

Ten unit tests cover existing register behavior plus dashboard decoding, invalid MQTT payloads, retained-message handling and bounded buffers. An integration smoke check started the actual three-device simulator and HTTP bridge, verified decoded readings, then stopped the simulator and verified unavailable-device errors and unchanged sample timestamps. Browser QA checks demo start/pause, asset switching and the local-connection guide. No live HiveMQ/HighByte installation was available in the development environment.
