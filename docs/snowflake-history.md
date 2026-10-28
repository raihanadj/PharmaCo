# Snowflake Historical Data — Local setup

This is a **read-only** extension to the existing PharmaCo live dashboard. The dashboard keeps acquiring live Modbus or MQTT data as before. The history table queries the independent `PHARMA_DATA.PRODUCTION.BIOREACTOR_DATA` table; it does not replace the live feed.

## Setup (Windows PowerShell)

```powershell
git fetch origin
git switch feat/snowflake-history
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt
```

Set these environment variables **in the terminal running the bridge**, using your own values:

```powershell
$env:SNOWFLAKE_ACCOUNT="YOUR_ACCOUNT_IDENTIFIER"
$env:SNOWFLAKE_USER="YOUR_SNOWFLAKE_USERNAME"
$env:SNOWFLAKE_WAREHOUSE="YOUR_WAREHOUSE"
$env:SNOWFLAKE_PRIVATE_KEY_FILE="C:\\secure\\path\\rsa_key.p8"
# Optional:
$env:SNOWFLAKE_ROLE="YOUR_READ_ONLY_ROLE"
# $env:SNOWFLAKE_PRIVATE_KEY_PASSWORD="YOUR_KEY_PASSPHRASE"
.\.venv\Scripts\python.exe src/dashboard_server.py
```

Start your existing simulators in another terminal, or pass `--with-simulator` if not already running. Open http://127.0.0.1:8050, scroll to **Historical process readings**, and click **Refresh history**. The bridge exposes `/api/history?hours=24`; only the server connects to Snowflake.

## Connection and schema checks

- Snowflake role needs **USAGE** on database, schema, and warehouse, plus **SELECT** on the table.
- Adapter expects a timestamp column named TIMESTAMP, EVENT_TIME, TIME, TS or CREATED_AT. Asset column may be BIOREACTOR1, ASSET, ASSET_NAME or DEVICE; otherwise it defaults to Bioreactor1. Metrics are TEMPERATURE, PH, RPMSETPOINT, HEATERON and HIGHTEMPALARM. Check actual schema before trusting rows.
- Run `DESCRIBE TABLE PHARMA_DATA.PRODUCTION.BIOREACTOR_DATA;` in Snowflake to confirm names and types. You may need to adjust adapter aliases.
- If timestamps are stored as timezone-less local values, validate timezone assumptions before interpreting the 24-hour filter.
- The dashboard displays up to 500 latest rows for the chosen time window, not the entire table.
- No browser or JavaScript code contains credentials. Do not put private keys or passwords in GitHub, screenshots, or shared CSVs.
- This has not been tested against the user's live Snowflake account; first test connection and schema with safe read-only privileges.

## Near-real-time Snowflake mode

Use this mode to display new Snowflake rows on the existing overview cards and charts, without a separate historical-table refresh:

```powershell
.\.venv\Scripts\python.exe src/dashboard_server.py --source snowflake
```

Restart the bridge if it is already running on port 8050. No simulator process is started by this command; keep the simulator and HighByte Snowflake output running independently. The backend polls the last hour of Snowflake records every 10 seconds (maximum 500 rows per query), and the browser fetches the snapshot every 5 seconds. Freshness is derived from row timestamps, and readings older than 30 seconds are stale. This is near-real-time polling, not Snowflake change streaming. Continuous queries may incur warehouse usage charges.

**Important schema prerequisites:** Each row must have a recognized timestamp, asset name (or it will be treated as Bioreactor1), and complete Bioreactor fields Temperature, PH, RpmSetpoint, HeaterOn, HighTempAlarm. Chiller requires separate named metrics and matching adapter mappings and is not supported by the current Snowflake adapter. Inspect DESCRIBE TABLE and adjust aliases as needed. Verify event timestamps are in UTC when Snowflake columns are timezone-less.

**Quick check:** open http://127.0.0.1:8050/api/snapshot and verify `source` is `snowflake`, then compare displayed times and values against `SELECT * FROM PHARMA_DATA.PRODUCTION.BIOREACTOR_DATA ORDER BY TIMESTAMP DESC LIMIT 5` (replace timestamp identifier if necessary). If no records appear, inspect permissions, the timestamp column, source data quality and whether HighByte is continuing to ingest. Stop the bridge before switching to Modbus or MQTT mode.
