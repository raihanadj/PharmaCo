"""Read-only Snowflake historian, isolated from live acquisition."""
import os
from datetime import datetime, timezone

TABLE = "PHARMA_DATA.PRODUCTION.BIOREACTOR_DATA"
TIMES = ("TIMESTAMP", "EVENT_TIME", "TIME", "TS", "CREATED_AT")
ASSETS = ("BIOREACTOR_ID", "BIOREACTOR1", "ASSET", "ASSET_NAME", "DEVICE")
METRICS = {"TEMPERATURE": "Temperature", "PH": "PH", "RPMSETPOINT": "RpmSetpoint", "RPM_SETPOINT": "RpmSetpoint", "RPM": "RpmSetpoint", "HEATERON": "HeaterOn", "HEATER_ON": "HeaterOn", "HIGHTEMPALARM": "HighTempAlarm", "HIGH_TEMP_ALARM": "HighTempAlarm"}

def history(hours=24, limit=500):
    """Server-side Snowflake query; never expose connection credentials."""
    import snowflake.connector
    required = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_PRIVATE_KEY_FILE")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        return {"status": "not_configured", "rows": [], "message": "Missing environment variables: " + ", ".join(missing)}
    options = dict(account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
                   warehouse=os.environ["SNOWFLAKE_WAREHOUSE"], authenticator="SNOWFLAKE_JWT",
                   private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"],
                   login_timeout=12, network_timeout=15, session_parameters={"QUERY_TAG": "PharmaCo_dashboard_history"})
    if os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSWORD"):
        options["private_key_password"] = os.environ["SNOWFLAKE_PRIVATE_KEY_PASSWORD"]
    if os.getenv("SNOWFLAKE_ROLE"):
        options["role"] = os.environ["SNOWFLAKE_ROLE"]
    with snowflake.connector.connect(**options) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM " + TABLE + " LIMIT 0")
            columns = {col[0].upper(): col[0] for col in cursor.description}
            t = next((columns[c] for c in TIMES if c in columns), None)
            if not t:
                return {"status": "schema_error", "rows": [], "message": "No recognized timestamp column", "columns": list(columns)}
            asset = next((columns[c] for c in ASSETS if c in columns), None)
            def quote(name):
                return '"' + name.replace('"', '""') + '"'
            wanted = [t] + ([asset] if asset else []) + [columns[c] for c in METRICS if c in columns]
            query = "SELECT " + ", ".join(quote(c) for c in wanted) + " FROM " + TABLE
            query += " ORDER BY " + quote(t) + " DESC LIMIT %s"
            cursor.execute(query, (int(limit),))
            result = []
            for values in cursor.fetchall():
                item = dict(zip(wanted, values))
                when = item.pop(t)
                if isinstance(when, datetime):
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                    when = when.isoformat()
                row = {"time": str(when), "asset": str(item.pop(asset)) if asset else "Bioreactor1"}
                for key, value in item.items():
                    row[METRICS.get(key.upper(), key)] = value
                result.append(row)
            return {"status": "ok", "table": TABLE, "rows": result[::-1], "count": len(result)}
