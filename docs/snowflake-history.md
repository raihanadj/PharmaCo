# PharmaCo Snowflake Live via SQL API (Python 3.15 compatible)

This branch uses Python's standard HTTP library and the `openssl` executable to generate an RSA-signed JWT from your existing `rsa_key.p8`. It **does not install snowflake-connector-python**. The key never leaves your Windows PC. The bridge queries the Snowflake SQL API every 10 seconds. The browser displays the newly ingested readings.

## 1. Install dashboard requirements

From your local PharmaCo folder in PowerShell:

```powershell
git fetch origin
git switch feat/snowflake-history
py -m pip install -r requirements-dashboard.txt
openssl version
```

If `openssl` isn't available, install a trusted OpenSSL for Windows or point `OPENSSL_EXE` to your existing openssl.exe. Do not upload your private key or JWT to GitHub/ChatGPT.

## 2. Set connection details in the SAME PowerShell window

```powershell
$env:SNOWFLAKE_HOST="https://YOUR-ORGANIZATION-YOUR-ACCOUNT.snowflakecomputing.com"
$env:SNOWFLAKE_ACCOUNT="YOUR-ORGANIZATION-YOUR-ACCOUNT"
$env:SNOWFLAKE_USER="YOUR_SNOWFLAKE_USERNAME"
$env:SNOWFLAKE_WAREHOUSE="YOUR_EXISTING_WAREHOUSE"
$env:SNOWFLAKE_PRIVATE_KEY_FILE="C:\full\path\to\rsa_key.p8"
# Optional if your RSA private key is encrypted:
# $env:SNOWFLAKE_PRIVATE_KEY_PASSWORD="YOUR_PASSPHRASE"
# Optional:
# $env:SNOWFLAKE_ROLE="YOUR_READ_ONLY_ROLE"
```

The host is the account's `*.snowflakecomputing.com` URL, not the Snowsight `app.snowflake.com` URL. You can find the account identifier via Snowflake UI/account details or `SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME(), CURRENT_USER(), CURRENT_WAREHOUSE();`. The account identifier used for JWT must match the identity of the assigned RSA key. Your Snowflake user must have its RSA public key registered. Use read-only Snowflake permissions for this dashboard.

## 3. Start the dashboard

```powershell
py src/dashboard_server.py --source snowflake
```

If `py` points to another Python, run the Python you normally use. Open http://127.0.0.1:8050 and optionally inspect http://127.0.0.1:8050/api/snapshot. The first query establishes a baseline. New rows inserted *after* that query are added to the charts when observed; the bridge does not manufacture new readings on repeated polls. Snowflake dashboard snapshots are polled by the browser every five seconds.

## Query

```sql
SELECT *
FROM PHARMA_DATA.PRODUCTION.BIOREACTOR_DATA
ORDER BY EVENT_TIME DESC
LIMIT 100;
```

Recognized columns include EVENT_TIME, BIOREACTOR_ID, TEMPERATURE, PH, RPM, HEATER_ON/HEATERON and HIGH_TEMP_ALARM/HIGHTEMPALARM. Bioreactor1 and Bioreactor2 are supported when the corresponding IDs exist. Chiller has no corresponding Snowflake table configured. If your actual heater/alarm columns are named differently, extend `ALIASES` in `src/snowflake_history.py`.

The connection is near-real-time polling, not streaming. Every 10 seconds it submits a Snowflake SELECT (warehouse cost may apply). Errors mean no new readings and the UI eventually reports stale data. The backend intentionally does not use source timestamps to decide whether a newly observed row counts as a new sample; the plotted time marks when the dashboard first observed the row. Historical section queries the newest rows as well, regardless of lookback option.

## Known boundaries

- This code has not been tested against your Snowflake credentials or local environment.
- OpenSSL must be installed; encrypted keys require a passphrase environment variable.
- The SQL API may return HTTP 202 while processing; the bridge waits for completion for up to ten status checks.
- SQL API first-result partitions are used, with a maximum of 100 rows for the live poll.
- Avoid exposing port 8050 publicly; bridge and private key should stay local.
