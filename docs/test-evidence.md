# Test record — 24 October 2026
Executed here on Linux with Python 3.12.14 and pymodbus 3.12.0. Windows and HighByte/MQTT execution remain pending. Text logs are evidence of local checks, not screenshots of the user's installation.

| ID | What | Steps | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|
| T01 | Listen 5020 | Start launcher; read units 1/2 | TCP responses | Both replied | PASS (Linux) | tcp-check.log, server-check.log |
| T02 | Scaling | Fix temp 37.2; update; read IR0 | 372 / 10 = 37.2 | Raw 372 | PASS (unit) | automated-checks.log |
| T03 | Heater | Set 36.4 and 36.5; update | ON then OFF | As expected | PASS (unit) | automated-checks.log |
| T04 | Alarm | Set 38.1 and 38.0; update | ON then OFF | As expected | PASS (unit) | automated-checks.log |
| T05 | RPM | Write 150; read back; check logging; restore live value | Accepted and logged | As expected | PASS | tcp-check.log; automated-checks.log |
| T06 | HighByte connection | Start simulator; inspect connection | Connected | Not run here | PENDING | screenshot required |
| T07 | HighByte scaling | Read known raw 372 | Display 37.2 | Not run here | PENDING | screenshot required |
| T08 | MQTT changes | Observe changing asset JSON | Changing values | Not run here | PENDING | screenshot required |
| T09 | Chiller cools bioreactor | Enable chiller; observe bioreactor | Temperature falls due to cooling | No coupling in source | NOT IMPLEMENTED | src modules |
| T10 | Wildcard | Subscribe PharmaCo/Dublin/# | All intended topics | Not run here | PENDING | screenshot required |

Additional automated checks cover chiller run/stop, effective setpoint clamping, device isolation and alarm-transition logging. No full regulated validation is claimed. Capture actual values, timestamps and named screenshots when completing integration tests.
