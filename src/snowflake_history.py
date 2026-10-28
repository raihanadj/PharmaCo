"""Snowflake SQL API read-only adapter. No Snowflake Python connector required.

Requires OpenSSL on PATH for signing JWTs with the existing rsa_key.p8.
Credentials are never sent to the browser.
"""
import base64
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

TABLE = "PHARMA_DATA.PRODUCTION.BIOREACTOR_DATA"
ALIASES = {
    "TEMPERATURE": "Temperature", "PH": "PH", "RPM": "RpmSetpoint",
    "RPMSETPOINT": "RpmSetpoint", "RPM_SETPOINT": "RpmSetpoint",
    "HEATERON": "HeaterOn", "HEATER_ON": "HeaterOn",
    "HIGHTEMPALARM": "HighTempAlarm", "HIGH_TEMP_ALARM": "HighTempAlarm",
}
ASSET_KEYS = ("BIOREACTOR_ID", "ASSET", "ASSET_NAME", "DEVICE")
TIME_KEYS = ("EVENT_TIME", "TIMESTAMP", "CREATED_AT")
_cached_token = None
_token_exp = 0


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _run_openssl(*args, data=None):
    password = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSWORD")
    env = os.environ.copy()
    command = [os.getenv("OPENSSL_EXE", "openssl"), *args]
    if password:
        command.extend(["-passin", "env:SNOWFLAKE_PRIVATE_KEY_PASSWORD"])
    result = subprocess.run(command, input=data, capture_output=True, env=env, timeout=15)
    if result.returncode:
        raise RuntimeError("OpenSSL could not read or sign with your private key. Check its path and passphrase.")
    return result.stdout


def _jwt():
    global _cached_token, _token_exp
    now = int(time.time())
    if _cached_token and now + 60 < _token_exp:
        return _cached_token
    key = os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"]
    account = os.environ["SNOWFLAKE_ACCOUNT"].upper().replace(".", "-")
    user = os.environ["SNOWFLAKE_USER"].upper()
    public_der = _run_openssl("pkey", "-in", key, "-pubout", "-outform", "DER")
    fp = "SHA256:" + base64.b64encode(hashlib.sha256(public_der).digest()).decode()
    subject = account + "." + user
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iss": subject + "." + fp, "sub": subject, "iat": now, "exp": now + 3300}
    signing_input = (_b64(json.dumps(header, separators=(",", ":")).encode()) + "."
                     + _b64(json.dumps(payload, separators=(",", ":")).encode())).encode()
    signature = _run_openssl("dgst", "-sha256", "-sign", key, data=signing_input)
    _cached_token = signing_input.decode() + "." + _b64(signature)
    _token_exp = now + 3300
    return _cached_token


def _request(method, path, payload=None):
    host = os.environ["SNOWFLAKE_HOST"].strip()
    if not host.startswith("https://") or "/" in host[8:]:
        raise ValueError("SNOWFLAKE_HOST must be an HTTPS Snowflake hostname, without a path")
    headers = {"Authorization": "Bearer " + _jwt(),
               "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
               "Accept": "application/json", "Content-Type": "application/json"}
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(host + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        # Do not return raw server errors (which can reveal account details).
        raise RuntimeError("Snowflake SQL API returned HTTP " + str(exc.code)) from exc


def history(hours=24, limit=100):
    required = ("SNOWFLAKE_HOST", "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER",
                "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_PRIVATE_KEY_FILE")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        return {"status": "not_configured", "rows": [],
                "message": "Missing: " + ", ".join(missing)}
    # Table name is fixed, so callers cannot submit arbitrary SQL.
    statement = ("SELECT * FROM " + TABLE +
                 " ORDER BY EVENT_TIME DESC LIMIT " + str(max(1, min(int(limit), 500))))
    body = {"statement": statement, "timeout": 30, "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
            "database": "PHARMA_DATA", "schema": "PRODUCTION",
            "parameters": {"AUTOCOMMIT": "TRUE"}}
    if os.getenv("SNOWFLAKE_ROLE"):
        body["role"] = os.environ["SNOWFLAKE_ROLE"]
    status, response = _request("POST", "/api/v2/statements", body)
    for _ in range(10):
        if status == 200:
            break
        if status != 202 or not response.get("statementHandle"):
            raise RuntimeError("Snowflake query did not complete")
        time.sleep(1)
        status, response = _request("GET", "/api/v2/statements/" + response["statementHandle"])
    if status != 200:
        raise RuntimeError("Snowflake query timed out")
    columns = [c["name"].upper() for c in response.get("resultSetMetaData", {}).get("rowType", [])]
    if not columns:
        raise RuntimeError("Snowflake response has no column metadata")
    rows = []
    for values in response.get("data", []):
        item = dict(zip(columns, values))
        source_time = next((item[k] for k in TIME_KEYS if k in item), None)
        asset_name = next((item[k] for k in ASSET_KEYS if k in item), "Bioreactor1")
        row = {"time": source_time, "asset": asset_name}
        for original, mapped in ALIASES.items():
            if original in item and mapped not in row:
                value = item[original]
                if mapped in ("HeaterOn", "HighTempAlarm"):
                    if isinstance(value, str):
                        value = value.strip().lower() in ("true", "1")
                    else:
                        value = bool(value)
                elif value is not None:
                    value = float(value)
                row[mapped] = value
        rows.append(row)
    return {"status": "ok", "rows": rows[::-1], "count": len(rows), "table": TABLE}
